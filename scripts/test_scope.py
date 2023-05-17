# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-04-07 17:51:29
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-17 10:55:01

import argparse
import matplotlib.pyplot as plt

from instrulink import logger, si_format, grab_oscilloscope, VisaError
from instrulink.constants import TTL_PAMP

# Default acquisition parameters
tscale = 1e-3  # temporal scale (s/div)
vscale = 0.2  # vertical scale (V/div)
voffset = 0.  # vertical offset (V)
tdelay = 5e-3 # 3e-3  # trigger delay (s)

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument(
    '--model', type=str, default=None, help='Oscilloscope model')
parser.add_argument(
    '--isignal', type=int, default=1, choices=(1, 2, 3, 4), help='Signal channel index')
parser.add_argument(
    '--itrigger', type=int, default=1, choices=(1, 2, 3, 4), help='Trigger channel index')
args = parser.parse_args()
ich_sig = args.isignal  # signal channel index
ich_trig = args.itrigger  # trigger channel index
ichs = set([ich_sig, ich_trig]) # set of channel indices

try:
    # Grab oscilloscope object
    scope = grab_oscilloscope(key=args.model)

    # Display settings
    print('DISPLAY SETTINGS')
    scope.display_menu()
    for ich in ichs:
        scope.show_trace(ich)
        logger.info(f'trace on channel {ich}: {scope.is_trace(ich)}')

    # Probes & coupling settings
    print('PROBE & COUPLING SETTINGS')
    for ich in ichs:
        scope.set_probe_attenuation(ich, 1)
        logger.info(f'channel {ich} attenuation factor = {scope.get_probe_attenuation(ich)}')
        logger.info(f'channel {ich} coupling mode: {scope.get_coupling_mode(ich)}')
    
    # Temporal and vertical scales / offsets
    print('SCALE & OFFSET SETTINGS')
    # scope.auto_setup()
    scope.set_temporal_scale(tscale)
    logger.info(f'temporal scale = {scope.get_temporal_scale()} s/div')
    for ich in ichs:
        scope.set_vertical_offset(ich, voffset)
        logger.info(f'channel {ich} vertical offset = {scope.get_vertical_offset(ich)} V')
    scope.set_vertical_scale(ich_sig, vscale)
    logger.info(f'channel {ich_sig} vertical scale = {scope.get_vertical_scale(ich_sig)} V/div')
    if ich_sig != ich_trig:
        scope.set_vertical_scale(ich_trig, TTL_PAMP / 2)
        logger.info(f'channel {ich_trig} vertical scale = {scope.get_vertical_scale(ich_trig)} V/div')

    # Trigger settings
    print('TRIGGER SETTINGS')
    scope.set_trigger_mode('norm')
    logger.info(f'trigger mode = {scope.get_trigger_mode()}')
    scope.set_trigger_coupling_mode(ich_trig, 'DC')
    logger.info(f'channel {ich_trig} trigger coupling mode = {scope.get_trigger_coupling_mode(ich_trig)}')
    logger.info(f'trigger type = {scope.get_trigger_type()}')
    scope.set_trigger_source(ich_trig)
    logger.info(f'trigger source channel = {scope.get_trigger_source()}')
    scope.set_trigger_slope(ich_trig, 'POS')
    logger.info(f'channel {ich_trig} trigger slope = {scope.get_trigger_slope(ich_trig)}')
    if ich_sig == ich_trig:
        scope.set_trigger_level(ich_trig, vscale / 2)
    else:
        scope.set_trigger_level(ich_trig, TTL_PAMP / 2)
    logger.info(f'channel {ich_trig} trigger level = {scope.get_trigger_level(ich_trig)} V')
    scope.set_trigger_delay(scope.get_temporal_range() / 3)
    logger.info(f'trigger delay = {si_format(scope.get_trigger_delay())}s')

    # Cursor settings
    print('CURSORS SETTINGS')
    if args.model == 'bk':
        for ich in ichs:
            for ctype in scope.CURSOR_TYPES:
                cpos = scope.get_cursor_position(ich, ctype)
                logger.info(f'channel {ich} {ctype} cursor position: {cpos} divs')
            for ctype in scope.CVALUES_TYPES:
                cval = scope.get_cursor_value(ich, ctype)
                logger.info(f'channel {ich} {ctype} values: {cval}')

    # Filter settings
    print('FILTER SETTINGS')
    scope.enable_bandwith_filter(ich_sig)
    scope.disable_bandwith_filter(ich_sig)
    sfilt = 'enabled' if scope.is_bandwith_filter_enabled(ich_sig) else 'disabled'
    logger.info(f'bandwidth filter for channel {ich_sig} is {sfilt}')
    fc = 10 / scope.get_temporal_scale()  # cutoff frequency (Hz)
    scope.set_filter(ich_sig, 'LP', fhigh=fc)
    scope.enable_filter(ich_sig)
    sfilt = 'enabled' if scope.is_filter_enabled(ich_sig) else 'disabled'
    logger.info(f'channel {ich_sig} filter is {sfilt}')

    # Acquisition settings
    print('ACQUISITION SETTINGS')
    logger.info(f'sample rate = {si_format(scope.get_sample_rate())}Hz')
    logger.info(f'acquisition type: {scope.get_acquisition_type()}')
    if scope.get_acquisition_type().startswith('AVER'):
        logger.info(f'# sweeps / acq: {scope.get_nsweeps_per_acquisition()}')
    scope.set_trigger_mode('norm')
    logger.info(f'trigger mode = {scope.get_trigger_mode()}')
    logger.info(f'trigger type = {scope.get_trigger_type()}')

    # Waveform settings
    print('WAVEFORM PARAMETERS')
    for k, v in scope.UNITS_PER_PARAM.items():
        try:
            val = scope.get_parameter_value(ich_sig, k)
            logger.info(f'{k} = {val} {v}')
        except VisaError as e:
            logger.error(e)
    
    # Hide menu before acquisition
    scope.hide_menu()

    # Waveform data
    print('WAVEFORM DATA')
    fig = scope.plot_waveform_data(ich_sig, n=5)

    # Screen data
    print('SCREEN CAPTURE')
    fig = scope.plot_screen_capture()

    # Show graphs
    plt.show()

except VisaError as e:
    logger.error(e)
