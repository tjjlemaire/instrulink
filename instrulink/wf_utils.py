# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-08-15 09:29:37
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-08-07 14:50:28

import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
from scipy.signal import welch

from .logger import logger
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
    if tramp <= 0:
        raise ValueError('tramp must be positive')
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
    dt = ttot / (n - 1)

    # Get data points for rising and falling edges
    try:
        tr, yr = get_smooth_ramp(
            nramp, tramp=tramp, t0=tonset + tramp / 2, direction='up', **kwargs)
        tf, yf = get_smooth_ramp(
            nramp, tramp=tramp, t0=toffset + tramp / 2, direction='down', **kwargs)
    except ValueError as e:
        tr, yr = np.array([0.]), np.array([0.])
        tf, yf = np.array([0.]), np.array([1.])
    
    # Check that ramp time is long enough to be resolved by the requested time step
    if tr.size > 1:
        dt = np.diff(tr)[0]
    else:
        logger.warning(
            f'ramping time ({si_format(tramp, 2)}s) is too short to be resolved by the requested time step ({si_format(dt, 2)}s) -> switching to discrete transition')
    
    # Get data points for pulse "high" plateau
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


def get_continous_intervals(t, refdt):
    '''
    Identify intervals of continuity in time vector.

    :param t: time vector (s)
    :param refdt: expected time step in continous time vector (s)
    :return: list of (start, end) pairs for each identified continuous time interval
    '''
    # Check that time vector contains at least 2 elements
    if t.size < 2:
        raise ValueError('Time vector must contain at least 2 elements')
    # Check that time contains at least 1 continous segment
    if not np.isclose(np.diff(t), refdt).any():
        raise ValueError('No continuity detected in time vector')
    
    # Identify discontinuities
    dt2 = np.diff(t, 2)
    iscontdt = np.isclose(dt2, 0)
    idiscont = np.where(~iscontdt)[0]

    # Identify index boundaries of continuous intervals
    istarts, iends = [0], []
    for i1, i2 in zip(idiscont[::2], idiscont[1::2]):
        if i2 != i1 + 1:
            raise ValueError(f'invalid discontinuity indices: {i1}, {i2}')
        iends.append(i2)
        istarts.append(i2 + 1)
    iends.append(t.size - 1)

    # Extract corresponding start and end times for each continuity region
    tstarts, tends = t[istarts], t[iends]

    # Return list of (start time, end time) pairs
    return np.array(list(zip(tstarts, tends)))


def get_bounds_per_region(t, y):
    ''' 
    Identify ramp-up, plateau, ramp-down, and baseline regions in waveform vector
    
    :param t: time vector (s)
    :param y: waveform vector
    :return: dictionary of (start, end) pairs for each identified region
    '''
    # Check that time step is consistent
    dt = np.unique(np.round(np.diff(t), 10))
    if dt.size > 1:
        raise ValueError(f'Inconsistent time step detected: {dt}')
    dt = dt[0]

    # Identify ramp-up, plateau, ramp-down, and baseline regions
    tregions = {
        'ramp-up': t[np.where(np.diff(y) > 0)],
        'plateau': t[np.where(y == 1)],
        'ramp-down': t[np.where(np.diff(y) < 0)],
        'baseline': t[np.where(y == 0)][1:],
    }

    # Identify time bounds for each valid region
    tbounds = {}
    for key, tvec in tregions.items():
        try:
            tbounds[key] = get_continous_intervals(tvec, dt)
        except ValueError as e:
            logger.warning(f'{key}: {e}')
    
    # Return dictionary of time bounds for each identified region
    return tbounds


def plot_smoothed_waveform(tenv, yenv, Fdrive, unit='ms', ax=None, title=None, 
                           label=None, mark_regs=True, **kwargs):
    ''' 
    Plot a smoothed waveform from a time vector, an envelope vector and a carrier frequency.

    :param t: time vector (s)
    :param yenv: envelope vector
    :param Fdrive: carrier frequency (Hz)
    :param unit: time unit for plotting (default = 'ms')
    :param ax: axis handle (default = None)
    :param title: title for the plot (default = None)
    :param label: label for the plotted waveform (default = None)
    :param mark_regs: flag indicating whether to mark identified regions (default = True)
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
    lh, *_ = ax.plot(tdense, yenvdense, label=label if label is not None else 'envelope')
    ax.plot(tdense, ydense, c=lh.get_color(), alpha=0.5, label='waveform' if label is None else None)
    ax.set_xlabel(f'time ({unit})')
    ax.set_ylabel('amplitude')
    ax.axhline(0, c='k', ls='--')

    # Identify ramp-up, plateau, ramp-down, and baseline regions
    tbounds = get_bounds_per_region(tdense, yenvdense)
    
    # Get number of pulses
    npulses = max(v.shape[0] for v in tbounds.values())

    # Generate title with breakdown of characteristic waveform phases if not provided
    if title is None:
        l = []
        if 'ramp-up' in tbounds:
            l.append(f'tramp = {np.diff(tbounds["ramp-up"][0])[0]:.2f} {unit}')
        elif 'ramp-down' in tbounds:
            l.append(f'tramp = {np.diff(tbounds["ramp-down"][0])[0]:.2f} {unit}')
        if 'plateau' in tbounds:
            l.append(f'tplateau = {np.diff(tbounds["plateau"][0])[0]:.2f} {unit}')
        if 'baseline' in tbounds:
            l.append(f'tbase = {np.diff(tbounds["baseline"][0])[0]:.2f} {unit}')
        if npulses > 1:
            l.append(f'{npulses} pulses')
        title = ', '.join(l)

    # Add title 
    ax.set_title(title)

    # Mark identified regions, if specified
    if mark_regs:
        colors_per_reg = {
            'ramp-up': 'g',
            'plateau': 'k',
            'ramp-down': 'r',
            'baseline': 'dimgray'
        }
        for reg, tvec in tbounds.items():
            for i, (tstart, tend) in enumerate(tvec):
                ax.axvspan(
                    tstart, tend, color=colors_per_reg[reg], alpha=0.1, 
                    label=reg if i == 0 else None)

    # Add legend
    ax.legend()

    # Return figure handle
    return fig


def plot_waveform_spectrum(tenv, yenv, Fdrive, ax=None, label=None, mark_freqs=True, 
                           title=None, get_PRF_val=False, color=None, plot=True, **kwargs):
    ''' 
    Plot a smoothed waveform from a time vector, an envelope vector and a carrier frequency.

    :param t: time vector (s)
    :param yenv: envelope vector
    :param Fdrive: carrier frequency (Hz)
    :param ax: axis handle (default = None)
    :param label: label for the plotted spectrum (default = None)
    :param mark_freqs: flag indicating whether to mark carrier and PRF frequencies (default = True)
    :param title: title for the plot (default = None)
    :param get_PRF_val: flag indicating whether to compute and return the log-spectrum value (in dB) at the waveform PRF (default = False)
    :return: figure handle (and log-spectrum value if requested)
    '''
    # Get figure and axis handles
    if ax is None:
        fig, ax = plt.subplots()
    else:
        fig = ax.get_figure()
    sns.despine(ax=ax)

    # Generate label if not provided
    if label is None:
        label = 'spectrum'
    
    # Add title
    ax.set_title('waveform spectrum' if title is None else title)

    # Get dense time, waveform and envelope vectors
    tdense, ydense, yenvdense = get_full_waveform(tenv, yenv, Fdrive, **kwargs)

    # Extract and waveform frequency spectrum
    freqs, ps = get_power_spectrum(tdense, ydense)
    ps_decibel = 10 * np.log10(ps / ps.max())
    if plot:
        ax.plot(freqs, ps_decibel, label=label, c=color)
    ax.set_xlabel('frequency (Hz)')
    ax.set_ylabel('relative power (dB)')
    ax.set_xscale('log')

    # Get number of pulses
    tbounds = get_bounds_per_region(tdense, yenvdense)
    nws = {k: v.shape[0] for k, v in tbounds.items()}
    k, npulses = max(nws, key=nws.get), max(nws.values())

    # In cases of multiple pulses, extract PRF and log-spectrum value at PRF
    if npulses > 1:
        logger.debug(f'identifying PRF from time difference between first 2 {k} onsets')
        PRF = np.round(1 / (tbounds[k][1, 0] - tbounds[k][0, 0]), 2)
        PRF_val = np.interp(PRF, freqs, ps_decibel)
    else:
        if get_PRF_val:
            raise ValueError('Cannot compute PRF log-spectrum value for single-pulse waveform')
        PRF = None

    # Mark carrier and PRF frequencies, if specified
    if mark_freqs:
        ax.axvline(Fdrive, c='k', ls='--', label='carrier')
        if PRF is not None:
            ax.axvline(PRF, c='r', ls='--', label='PRF')
    
    # Add legend
    if plot:
        ax.legend()

    # Return figure handle (and log-spectrum value if requested)
    if get_PRF_val:
        return fig, PRF_val
    else:
        return fig