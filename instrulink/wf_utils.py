# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-08-15 09:29:37
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2022-08-15 09:30:46

import numpy as np


def get_sigmoid(dt, tau_rise, dy=.001):
    '''
    Get a sigmoid vector to achieve a specific rise time with a time step
    
    :param dt: time step (ms)
    :param tau_rise: rise time, i.e. time between dy and 1 - dy (ms)
    :param dy: vertical offset for rise time 
    :return: time and sigmoid vectors
    '''
    k = 2 * np.log((1 - dy) / dy) / tau_rise  # coefficient needed to get appropriate rise time
    nsamples = int(np.round(tau_rise / dt) + 1)  # number of samples to achieve full rise with given time step
    t = np.linspace(0, tau_rise, nsamples)  # time vector
    s = 1 / (1 + np.exp(-k * (t - tau_rise / 2)))  # sigmoid vector
    return t, s


def get_smoothed_envelope(dt, tpulse, tsmooth, **kwargs):
    '''
    Get a smoothed envelope with a specific duration, rise time and time step
    
    :param dt: time step (ms)
    :param tpulse: pulse duration (ms)
    :param tsmooth: smoothing window for rise and fall (ms)
    :return: time and envelope vectors
    '''
    _, s = get_sigmoid(dt, tsmooth, **kwargs)  # rising sigmoid vector
    ns = s.size
    nsamples = int(np.round(tpulse / dt) + 1)  # number of samples to achieve full pulse duration with given time step
    t = np.linspace(0, tpulse, nsamples)  # time vector
    y = np.ones(nsamples)
    y[:ns] = s
    y[-ns:] = s[::-1]
    return t, y


def get_smoothed_waveform(f, tpulse, tsmooth, npercycle=25, **kwargs):
    '''
    Get a smoothed envelope sinusoidal waveform with a specific duration, rise time and
    number of points per cycle
    
    :param f: carrier frequency of the sinusoid (kHz)
    :param tpulse: pulse duration (ms)
    :param tsmooth: smoothing window for rise and fall (ms)
    :param npercycle: number of points per cycle
    :return: time and waveform vectors
    '''
    dt = 1 / (npercycle * f)  # time step (ms)
    t, yenv = get_smoothed_envelope(dt, tpulse, tsmooth, **kwargs)
    ycarrier = np.sin(2 * np.pi * f * t)  # carrier wave  (a.u.)
    y = yenv * ycarrier
    return t, y