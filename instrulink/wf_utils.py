# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-08-15 09:29:37
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-08-03 15:42:40

import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt


def sigmoid_ramp(t, tramp=1, t0=0, dy=0.01):
    ''' 
    Sigmoidal ramp-up function with a specific ramp time and half-ramp point
    
    :param t: time vector
    :param tramp: ramp time
    :param t0: half-ramp point
    :param dy: vertical offset for ramp time (default = 0.01)
    :return: horizontally and vertically scaled sigmoid ramp-up vector
    '''
    # Get sigmoid scaling factor from analytical solution of sigmoid function
    if dy <= 0 or dy >= 1:
        raise ValueError('dy must be between 0 and 1')
    k = 2 * np.log((1 - dy) / dy) / tramp
    # Get sigmoid vector
    y = 1 / (1 + np.exp(-k * (t - t0)))
    # Rescale sigmoid vector to [0 - 1] range
    y = (y - dy) / (1 - 2 * dy)
    # Return sigmoid vector
    return y


def sine_ramp(t, tramp=1, t0=0):
    ''' 
    Sine ramp-up function with a specific ramp time and half-ramp point

    :param t: time vector
    :param tramp: ramp time
    :param t0: half-ramp point
    :return: horizontally and vertically scaled sinusoidal ramp-up vector
    '''
    return (np.sin(2 * np.pi * (t - t0) / (2 * tramp)) + 1) / 2


def halfsine_ramp(t, tramp=1, t0=0):
    ''' 
    Half-sine ramp-up function with a specific ramp time and half-ramp point

    :param t: time vector
    :param tramp: ramp time
    :param t0: half-ramp point
    :return: horizontally and vertically scaled sinusoidal ramp-up vector
    '''
    return np.sin(2 * np.pi * (t - t0) / (4 * tramp) + np.pi / 4)


def get_smooth_ramp(n, tramp=1, t0=0, kind='sine', direction='up', **kwargs):
    '''
    Get a smooth ramp vector to transition from 0 to 1 within a specific ramp time and half-ramp point
    
    :param n: number of points in the ramp vector
    :param tramp: ramp time
    :param t0: half-ramp point
    :param kind: ramp-up function type ('sigmoid' or 'sine')
    :param direction: ramp direction ('up' or 'down')
    :return: time and sigmoid vectors
    '''
    # Get time vector
    t = np.linspace(0, tramp, n) + t0 - tramp / 2
    # Get ramp-up vector
    if kind == 'sigmoid':
        y = sigmoid_ramp(t, t0=t0, tramp=tramp, **kwargs)
    elif kind == 'sine':
        y = sine_ramp(t, t0=t0, tramp=tramp)
    elif kind == 'halfsine':
        y = halfsine_ramp(t, t0=t0, tramp=tramp)
    else:
        raise ValueError(f'Invalid ramping function type: {kind}')
    # Invert ramping vector if "down" direction is specified
    if direction == 'down':
        y = y[::-1]
    # Return time and ramp vectors
    return t, y


def get_smoothed_pulse_envelope(n, tramp, thigh, tlow=0, plot=False, unit='ms', **kwargs):
    '''
    Get a smoothed rectangular pulse envelope with a specific ramp-up (and down) time,
    plateau duration and base duration.
    
    :param n: number of points in envelope vector
    :param tramp: pulse ramp-up (and down) time
    :param thigh: pulse plateau duration
    :param tbase: post-pulse baseline duration
    :param plot: boolean indicating whether to plot the envelope
    :param unit: time unit for plotting
    :return: time and envelope vectors
    '''
    # Compute characteristic times and total duration 
    tonset = 0
    toffset = tramp + thigh
    ttot = 2 * tramp + thigh + tlow

    # Derive number of points in ramp-up (and down) phases
    nramp = int(np.round(n * tramp / ttot)) + 1

    # Get data points for rising and falling edges
    tr, yr = get_smooth_ramp(
        nramp, tramp=tramp, t0=tonset + tramp / 2, direction='up', **kwargs)
    tf, yf = get_smooth_ramp(
        nramp, tramp=tramp, t0=toffset + tramp / 2, direction='down', **kwargs)
    
    # Get data points for pulse "high" plateau
    dt = np.diff(tr)[0]
    th = np.arange(tr[-1] + dt, toffset - dt / 2, dt)
    yh = np.ones(th.size)

    # If plateau is empty, remove first ramp-down point
    if th.size == 0:
        tf = tf[1:]
        yf = yf[1:]

    # Get data points for pulse "low" baseline
    tl = np.arange(tf[-1] + dt, ttot + dt / 2, dt)
    yl = np.zeros(tl.size)

    # Concatenate data points
    t = np.hstack([tr, th, tf, tl])
    y = np.hstack([yr, yh, yf, yl])

    # Interpolate vectors to ensure that they match the requested number of points
    tnew = np.linspace(t[0], t[-1], n)
    y = np.interp(tnew, t, y)
    t = tnew

    # Plot if requested 
    if plot:
        fig, ax = plt.subplots()
        sns.despine(ax=ax)
        ax.plot(t, y, label='envelope')
        ax.set_xlabel(f'time ({unit})')
        ax.set_ylabel('amplitude')
        ax.set_title(f'tramp = {tramp} {unit}, thigh = {thigh} {unit}, tlow = {tlow} {unit}')
        for yc in (0, 0.5, 1):
            ax.axhline(yc, c='k', ls='--')
        ax.axvspan(0, tramp, color='g', alpha=0.1, label='ramp-up')
        if thigh > 0:
            ax.axvspan(tramp, thigh + tramp, color='y', alpha=0.1, label='plateau')
        ax.axvspan(thigh + tramp, thigh + 2 * tramp, color='r', alpha=0.1, label='ramp-down')
        if tlow > 0:
            ax.axvspan(thigh + 2 * tramp, t[-1], color='k', alpha=0.1, label='baseline')
        ax.legend()

    # Return time and envelope vectors
    return t, y


def get_DC_smoothed_pulse_envelope(n, PRF, DC, tramp=0, **kwargs):
    '''
    Wrapper around get_smoothed_pulse_envelope to get a smoothed rectangular 
    pulse envelope based on a specific pulsing rate and duty cycle.

    :param n: number of points in envelope vector
    :param PRF: pulse repetition frequency (Hz)
    :param DC: duty cycle (%)
    :param tramp: ramp-up (and down) time (s)
    '''
    # Normalize duty cycle to [0 - 1] range and ramp time to ms
    DC /= 100  # (0 - 1)
    tramp *= 1e3  # (ms)

    # Compute ON, OFF and total envelope duration
    PRI = 1 / PRF * 1e3  # ms
    ton = DC * PRI  # ms
    toff = PRI - ton  # ms
    
    # Compute plateau duration and post-pulse baseline duration
    thigh = ton - tramp  # ON time minus half ramp-up and half ramp-down time (ms)
    tlow = toff - tramp  # OFF time minus ramp-down time (ms)

    # Check validity of resulting high and low times
    if thigh < 0:
        raise ValueError(f'ON duration ({ton:.2f} ms) is too short for the specified ramp time ({tramp:.2f} ms)')
    if tlow < 0:
        raise ValueError(f'OFF duration ({toff:.2f} ms) is too short for the specified ramp time ({tramp:.2f} ms)')

    # Check that total envelope duration does not exceed the PRI
    tenv = thigh + tlow + 2 * tramp
    if tenv > PRI:
        raise ValueError(f'ramped pulse duration ({tenv:.2f} ms) exceeds pulse repetition interval ({PRI:.2f} ms)')

    # Assemble and return smoothed pulse envelope
    return get_smoothed_pulse_envelope(n, tramp, thigh, tlow=tlow, **kwargs)