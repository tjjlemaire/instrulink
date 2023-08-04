# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-08-15 09:29:37
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-08-04 16:01:52

import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

from .si_utils import si_prefixes, si_format


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


def get_smoothed_pulse_envelope(n, tramp, thigh, tlow=0, plot=None, Fdrive=None, nreps=1, **kwargs):
    '''
    Get a smoothed rectangular pulse envelope with a specific ramp-up (and down) time,
    plateau duration and base duration.
    
    :param n: number of points in envelope vector
    :param tramp: pulse ramp-up (and down) time
    :param thigh: pulse plateau duration
    :param tbase: post-pulse baseline duration
    :param plot: flag indicating whether/what to plot:
        - None: nothing (default)
        - "wf": the waveform envelope
        - "fft": the waveform frequency spectrum
        - "all": both envelope and spectrum
    :param Fdrive: carrier frequency (Hz) used for plotting purposes.
        Defaults to 25 / thigh if not specified.
    :param nreps: number of nominal envelope repetitions for plotting (default = 1)
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
    tenv = np.hstack([tr, th, tf, tl])
    yenv = np.hstack([yr, yh, yf, yl])

    # Interpolate vectors to ensure that they match the requested number of points
    tnew = np.linspace(tenv[0], tenv[-1], n)
    yenv = np.interp(tnew, tenv, yenv)
    tenv = tnew

    # If plot requested
    if plot is not None:
        # Check validity of plot option
        pltchoices = ('wf', 'fft', 'all')
        if plot not in pltchoices:
            raise ValueError(f'Invalid plot option: "{plot}". Valid options are: {pltchoices}')

        # Determine what to plot and generate figure and axes
        pltwf = plot in ('wf', 'all')
        pltfft = plot in ('fft', 'all')
        naxes = int(pltwf) + int(pltfft)
        _, axes = plt.subplots(naxes, 1, figsize=(6, 3 * naxes))
        axes = np.atleast_1d(axes)
        iax = 0

        # Compute carrier frequency if not specified
        if Fdrive is None:
            Fdrive = 25 / thigh  # Hz
        
        # If requested, plot waveform and its envelope
        if pltwf:
            plot_smoothed_waveform(tenv, yenv, Fdrive, ax=axes[iax], nreps=nreps)
            iax += 1
        
        # If requested, plot waveform spectrum
        if pltfft:
            plot_waveform_spectrum(tenv, yenv, Fdrive, ax=axes[iax], nreps=nreps)

    # Return time and envelope vectors
    return tenv, yenv


def get_DC_smoothed_pulse_envelope(n, PRF, DC, tramp=0, **kwargs):
    '''
    Wrapper around get_smoothed_pulse_envelope to get a smoothed rectangular 
    pulse envelope based on a specific pulsing rate and duty cycle.

    :param n: number of points in envelope vector
    :param PRF: pulse repetition frequency (Hz)
    :param DC: duty cycle (%)
    :param tramp: ramp-up (and down) time (s)
    '''
    # Normalize duty cycle to [0 - 1] range
    DC /= 100  # (0 - 1)

    # Compute ON, OFF and total envelope duration
    PRI = 1 / PRF  # s
    ton = DC * PRI  # s
    toff = PRI - ton  # s
    
    # Compute plateau duration and post-pulse baseline duration
    thigh = ton - tramp  # ON time minus half ramp-up and half ramp-down time (ms)
    tlow = toff - tramp  # OFF time minus ramp-down time (ms)

    # Check validity of resulting high and low times
    if thigh < 0:
        raise ValueError(f'ON duration ({si_format(ton, 2)}s) is too short for the specified ramp time ({si_format(tramp, 2)}s)')
    if tlow < 0:
        raise ValueError(f'OFF duration ({si_format(toff, 2)} ms) is too short for the specified ramp time ({si_format(tramp, 2)}s)')

    # Check that total envelope duration does not exceed the PRI
    tenv = thigh + tlow + 2 * tramp
    if tenv > PRI + 1e-12:
        raise ValueError(f'smoothed pulse duration ({si_format(tenv, 5)}s) exceeds pulse repetition interval ({si_format(PRI, 2)}s)')

    # Assemble and return smoothed pulse envelope
    return get_smoothed_pulse_envelope(n, tramp, thigh, tlow=tlow, **kwargs)


def get_full_waveform(t, yenv, Fdrive, npc=25, nreps=1):
    ''' 
    Get a full waveform from a time vector, an envelope vector and a carrier frequency.

    :param t: time vector (s)
    :param yenv: envelope vector
    :param Fdrive: carrier frequency (Hz)
    :param npc: number of points per cycle (default = 25)
    :param nreps: number of nominal waveform repetitions (default = 1)
    :return: dense time, waveform and envelope vectors
    '''
    # Determine sampling frequency and number of points in full waveform
    fs = Fdrive * npc  # Hz
    npts = int(np.round(t[-1] * fs))
    # Generate dense time vector 
    tdense = np.linspace(0, t[-1], npts)  # s
    # Interpolate envelope vector
    yenvdense = np.interp(tdense, t, yenv)
    # Generate carrier vector
    ycarrier = np.sin(2 * np.pi * Fdrive * tdense)
    # Generate waveform vector
    ydense = yenvdense * ycarrier
    # Repeat vectors if needed
    if nreps > 1:
        tdenseexp = tdense.copy()
        ydenseexp = ydense.copy()
        yenvdenseexp = yenvdense.copy()
        for _ in range(2, nreps + 1):
            tdenseexp = np.hstack([tdenseexp, tdenseexp[-1] + tdense[1:]])
            ydenseexp = np.hstack([ydenseexp, ydense[1:]])
            yenvdenseexp = np.hstack([yenvdenseexp, yenvdense[1:]])
        tdense = tdenseexp
        ydense = ydenseexp
        yenvdense = yenvdenseexp
    # Return dense time, waveform and envelope vectors
    return tdense, ydense, yenvdense


def get_power_spectrum(t, y):
    '''
    Get the power spectrum of a waveform.

    :param t: time vector (s)
    :param y: waveform vector
    :return: frequency (Hz) and power vectors
    '''
    dt = np.diff(t)[0]  # s
    freqs = np.fft.rfftfreq(y.size, dt)  # Hz
    ps = np.abs(np.fft.rfft(y))**2  # power
    return freqs, ps


def get_continous_intervals(t):
    '''
    Identify intervals of continuity in time vector.

    :param t: time vector (s)
    :return: list of (start, end) pairs for each identified continuous time interval
    '''
    dt2 = np.diff(t, 2)
    iscontdt = np.isclose(dt2, 0)
    idiscont = np.where(~iscontdt)[0]
    istarts, iends = [0], []
    for i1, i2 in zip(idiscont[::2], idiscont[1::2]):
        if i2 != i1 + 1:
            raise ValueError('Discontinuity detected in baseline')
        iends.append(i2)
        istarts.append(i2 + 1)
    iends.append(t.size - 1)
    tstarts, tends = t[istarts], t[iends]
    return np.array(list(zip(tstarts, tends)))


def plot_smoothed_waveform(tenv, yenv, Fdrive, unit='ms', ax=None, **kwargs):
    ''' 
    Plot a smoothed waveform from a time vector, an envelope vector and a carrier frequency.

    :param t: time vector (s)
    :param yenv: envelope vector
    :param Fdrive: carrier frequency (Hz)
    :param unit: time unit for plotting (default = 'ms')
    :param ax: axis handle (default = None)
    :return: figure handle
    '''
    # Get figure and axis handles
    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.get_figure()
    sns.despine(ax=ax)

    # Get dense time, waveform and envelope vectors
    tdense, ydense, yenvdense = get_full_waveform(tenv, yenv, Fdrive, **kwargs)
    tfactor = si_prefixes[unit[:-1]]
    tdense /= tfactor

    # Plot waveform and its envelope
    ax.plot(tdense, ydense, label='waveform')
    ax.plot(tdense, yenvdense, label='envelope')
    ax.set_xlabel(f'time ({unit})')
    ax.set_ylabel('amplitude')
    ax.axhline(0, c='k', ls='--')

    # Identify ramp-up, plateau, ramp-down, and baseline regions
    thigh = get_continous_intervals(tdense[np.where(yenvdense == 1)])
    tlow = get_continous_intervals(tdense[np.where(yenvdense == 0)][1:])
    assert thigh.shape[0] == tlow.shape[0], 'Number of plateau and baseline windows must be equal'
    npulses = thigh.shape[0]
    trampup, trampdown = [], []
    tref = 0
    for iw in range(npulses):
        trampup.append((tref, thigh[iw, 0]))
        trampdown.append((thigh[iw, 1], tlow[iw, 0]))
        tref = tlow[iw, 1]
    trampup, trampdown = np.array(trampup), np.array(trampdown)

    # Add title with breakdown of characteristic waveform phases
    tramp = np.diff(trampup[0])[0]
    tplateau = np.diff(thigh[0])[0]
    tbase = np.diff(tlow[0])[0]
    title = f'tramp = {tramp:.2f} {unit}, tplateau = {tplateau:.2f} {unit}, tbase = {tbase:.2f} {unit}'
    if npulses > 1:
        title = f'{title}, {npulses} pulses'
    ax.set_title(title)

    # Mark ramp-up, plateau, ramp-down, and baseline regions
    for phase, (color, tvec) in {
        'ramp-up': ('g', trampup), 
        'plateau': ('k', thigh),
        'ramp-down': ('r', trampdown),
        'baseline': ('dimgray', tlow)
        }.items():
        for i, (tstart, tend) in enumerate(tvec):
            ax.axvspan(
                tstart, tend, color=color, alpha=0.1, label=phase if i == 0 else None)

    # Add legend
    ax.legend()

    # Return figure handle
    return fig


def plot_waveform_spectrum(tenv, yenv, Fdrive, ax=None, **kwargs):
    ''' 
    Plot a smoothed waveform from a time vector, an envelope vector and a carrier frequency.

    :param t: time vector (s)
    :param yenv: envelope vector
    :param Fdrive: carrier frequency (Hz)
    :param ax: axis handle (default = None)
    :return: figure handle
    '''
    # Get figure and axis handles
    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.get_figure()
    sns.despine(ax=ax)

    # Get dense time, waveform and envelope vectors
    tdense, ydense, yenvdense = get_full_waveform(tenv, yenv, Fdrive, **kwargs)

    # Extract and waveform frequency spectrum
    freqs, ps = get_power_spectrum(tdense, ydense)
    ps_decibel = 10 * np.log10(ps / ps.max())
    ax.plot(freqs, ps_decibel)
    ax.set_xlabel('frequency (Hz)')
    ax.set_ylabel('relative power (dB)')
    ax.set_xscale('log')

    # Mark carrier frequency
    ax.axvline(Fdrive, c='k', ls='--', label='carrier')

    # In cases of multiple pulses, extract and mark PRF
    thigh = get_continous_intervals(tdense[np.where(yenvdense == 1)])
    if thigh.shape[0] > 1:
        PRF = np.round(1 / (thigh[1, 0] - thigh[0, 0]), 2)  # Hz
        ax.axvline(PRF, c='r', ls='--', label='PRF')
    
    # Add legend
    ax.legend()

    # Return figure handle
    return fig