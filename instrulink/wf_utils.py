# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-08-15 09:29:37
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2026-07-14 13:08:47

import numpy as np
from scipy.signal.windows import tukey

from .logger import logger
from .constants import *


def get_tukey_envelope(npulse, xramp=0, xprepad=0, xpostpad=0, rms_norm=True):
    '''
    Get a Tukey window envelope of specified size with a specific ramp-up/down fraction 
    and optional pre- and post-pulse zero padding.
    
    :param npulse: number of points in pulse window (without padding)
    :param xramp: fraction of window used for ramp-up (same for ramp-down). Defaults to zero (rectangular pulse)
    :param xprepad: relative size of pre-pulse zero padding, w.r.t pulse window. Defaults to zero.
    :param xpostpad: relative size of post-pulse zero padding, w.r.t pulse window. Defaults to zero.
    :param rms_norm: flag indicating whether to normalize the envelope to unit RMS amplitude (default = True)
    :return: Tukey window envelope vector (potentially normalized to unit RMS amplitude)
    '''
    # Check that ramp fraction is in [0, 1]
    if xramp < 0 or xramp > 1.:
        raise ValueError(f'xramp must be in [0, 1], got {xramp}')
    
    # Generate pulse envelope with Tukey window with appropriate taper
    w = tukey(npulse, alpha=xramp)

    # If specified, compensate amplitude to achieve equal RMS amplitude regardless of ramp time
    if rms_norm:
        wrms = np.sqrt(np.mean(w**2))  # RMS amplitude of the pulse envelope
        w = w / wrms  # normalize to unit RMS amplitude

    # Compute length of pre and post-padding
    npre = int(np.round(npulse * xprepad))
    npost = int(np.round(npulse * xpostpad))

    # Add pre- and post-pulse padding, if any
    if npre > 0:
        w = np.hstack([np.zeros(npre), w])
    if npost > 0:
        w = np.hstack([w, np.zeros(npost)])

    # Return
    return w


def get_pulse_envelope(n, tpulse, toff, tramp=0, **kwargs):
    '''
    Get a Tukey window pulse envelope of specified size and duration with a specific ramp-up/down time 
    and optional post-pulse zero padding.

    :param n: total number of points (including optional post-pulse padding)
    :param tpulse: pulse duration (s)
    :param toff: post-pulse off-time (s)
    :param tramp: pulse ramp-up time (s)
    :param kwargs: additional arguments for get_pulse_envelope function
    :return: time and envelope vectors
    '''
    # Compute total duration of pulse + post-padding window
    ttot = tpulse + toff

    # Compute number of points in pulse window, and check that it is at least 1
    npulse = int(np.round(n * tpulse / ttot))
    if npulse < 1:
        raise ValueError(
            f'pulse duration ({tpulse * S_TO_MS:.2f} ms) is too short for the requested total number of points ({n}) and off-time ({toff * S_TO_MS:.2f} ms)')

    # Compute relevant fractions
    xramp = 2 * tramp / tpulse  # fraction of the pulse inside tapered window
    if xramp > 1:
        raise ValueError(f'ramp time ({tramp * S_TO_MS:.2f} ms) is > 50% of pulse duration ({tpulse * S_TO_MS:.2f} ms)')
    xpostpad = toff / tpulse  # post-pulse padding fraction 

    # Construct envelope vector 
    y = get_tukey_envelope(npulse, xramp=xramp, xpostpad=xpostpad, **kwargs)

    # Check that vector is of expected size
    assert y.size == n, f'expected envelope vector of size {n}, got {y.size}'

    # Generate time vector
    t = np.linspace(0, ttot, n)  # s

    # Return time and envelope vectors
    return t, y


def get_pulse_train_envelope(dt, dur, PRF=None, DC=100., tramp=0, tprepad=None, tpostpad=None, **kwargs):
    '''
    Construct pulse train envelope from stimulation parameters

    :param dt: time step (s) for envelope resolution
    :param dur: total duration of the pulse train (s)
    :param PRF (optional): pulse repetition frequency (Hz). Must be specified if DC < 100%.
    :param DC: duty cycle (%). Defaults to 100% (continuous wave).
    :param tramp: ramp-up time (s) for each pulse envelope
    :param tprepad: pre-train zero padding (s). If None, set to 5% of pulse train duration or 20 ms, whichever is greater
    :param tpostpad: post-train zero padding (s). If None, set to 5% of pulse train duration or 20 ms, whichever is greater
    :param kwargs: additional arguments for get_pulse_envelope function
    :return: time and envelope vectors
    '''
    # Determine overall number of points
    nenv = int(np.round(dur / dt)) + 1

    # If DC = 0, construct zero envelope
    if DC == 0:
        y = np.zeros(nenv)
    
    # If DC is non-zero
    else:
        # If DC is 100% (CW mode), set nperpulse = n
        if DC == 100:
            npulses = 1
            nperpulse = nenv
            ton = dur  # nominal pulse duration (s)
        
        # If DC < 100% (PW mode), set npulse and nperpulse
        else:
            if PRF is None:
                raise ValueError('PRF must be specified for pulsed waveforms (DC < 100%)')
            PRI = 1 / PRF  # pulse repetition interval (s)
            if PRI > dur:
                raise ValueError(f'waveform duration ({dur * S_TO_MS:.2f} ms) is shorter than pulse repetition interval ({PRI * S_TO_MS:.2f} ms)')
            npulses = int(np.round(dur * PRF))  # number of pulses in the burst
            nperpulse = int(np.round(nenv / npulses * DC * 1e-2))  # number of points per pulse (with DC)
            ton = (DC * 1e-2) / PRF  # nominal pulse duration (s)

        # Compute relative ramp time and post-padding fraction
        xramp = 2 * tramp / ton  # ramp fraction
        if xramp > 1:
            raise ValueError(f'ramp time ({tramp * S_TO_MS:.2f} ms) is > 50% of pulse duration ({ton * S_TO_MS:.2f} ms)')
        xpostpad = 1 / (DC * 1e-2) - 1  # offset fraction

        # Get nominal pulse envelope
        y = get_tukey_envelope(nperpulse, xramp=xramp, xpostpad=xpostpad, **kwargs)

        # If more than one pulse, repeat nominal pulse envelope to get full train
        if npulses > 1:
            y = np.tile(y, npulses)

    # Compute effective time step post-construction, and check against requested time step
    dteff = dur / (y.size - 1)
    if not np.isclose(dteff, dt):
        logger.warning(f'effective time step ({dteff:.2e} s) does not match requested time step ({dt:.2e} s).')

    # Add pre- and post-train padding, if any
    if tprepad is None:
        tprepad = max(0.05 * dur, 0.02)  # s
    if tpostpad is None:
        tpostpad = max(0.05 * dur, 0.02)  # s
    npre = max(int(np.round(tprepad / dt)) - 1, 0)
    npost = max(int(np.round(tpostpad / dt)) - 1, 0)
    y = np.pad(y, (npre, npost), mode='constant', constant_values=0)

    # Construct time vector
    t = np.arange(y.size) * dteff  # s
    if tprepad > 0:
        t -= tprepad
    
    # Return envelope vector
    return t, y
