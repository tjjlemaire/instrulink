# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-04-07 17:51:29
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-10 23:18:34

import argparse
import matplotlib.pyplot as plt

from lab_instruments import logger, si_format, grab_oscilloscope, VisaError

# Parse oscilloscope class from command line
parser = argparse.ArgumentParser()
parser.add_argument(
    '-t', '--type', type=str, default='bk', choices=('bk', 'rigol'), help='Oscilloscope type')
args = parser.parse_args()

try:
    # Grab oscilloscope object
    scope = grab_oscilloscope(type=args.type)

    # Display settings
    print('DISPLAY SETTINGS')
    if args.type == 'bk':
        scope.display_menu()
        scope.hide_menu()
    scope.show_trace(1)
    logger.info(f'trace on channel 1: {scope.is_trace(1)}')

    # Probes & coupling settings
    print('PROBE & COUPLING SETTINGS')
    scope.set_probe_attenuation(1, 1)
    logger.info(f'channel 1 attenuation factor = {scope.get_probe_attenuation(1)}')
    logger.info(f'channel 1 coupling mode: {scope.get_coupling_mode(1)}')
    
    # Temporal and vertical scales / offsets
    print('SCALE & OFFSET SETTINGS')
    # scope.auto_setup()
    scope.set_temporal_scale(1e-3)
    logger.info(f'temporal scale = {scope.get_temporal_scale()} s/div')
    scope.set_vertical_scale(1, 2)
    logger.info(f'channel 1vertical scale = {scope.get_vertical_scale(1)} V/div')
    scope.set_vertical_offset(1, .0)
    logger.info(f'channel 1 vertical offset = {scope.get_vertical_offset(1)} V')

    # Trigger settings
    print('TRIGGER SETTINGS')
    scope.set_trigger_mode('norm')
    logger.info(f'trigger mode = {scope.get_trigger_mode()}')
    if args.type == 'bk':
        scope.set_trigger_coupling_mode(1, 'DC')
        logger.info(f'channel 1 trigger coupling mode = {scope.get_trigger_coupling_mode(1)}')
    else:
        scope.set_trigger_coupling_mode('DC')
        logger.info(f'trigger coupling mode = {scope.get_trigger_coupling_mode()}')
    logger.info(f'trigger type = {scope.get_trigger_type()}')
    scope.set_trigger_source(1)
    logger.info(f'trigger source channel = {scope.get_trigger_source()}')
    if args.type == 'bk':
        scope.set_trigger_slope(1, 'POS')
        logger.info(f'channel 1 trigger slope = {scope.get_trigger_slope(1)}')
    else:
        scope.set_trigger_slope('POS')
        logger.info(f'trigger slope = {scope.get_trigger_slope()}')
    if args.type == 'bk':
        scope.set_trigger_level(1, 0.4)
        logger.info(f'channel 1 trigger level = {scope.get_trigger_level(1)} V')
    else:
        scope.set_trigger_level(0.4)
        logger.info(f'trigger level = {scope.get_trigger_level()} V')
    scope.set_trigger_delay(-5e-3)
    logger.info(f'trigger delay = {si_format(scope.get_trigger_delay())}s')

    # Cursor settings
    print('CURSORS SETTINGS')
    ich = 1
    if args.type == 'bk':
        for ctype in scope.CURSOR_TYPES:
            cpos = scope.get_cursor_position(ich, ctype)
            logger.info(f'channel {ich} {ctype} cursor position: {cpos} divs')
        for ctype in scope.CVALUES_TYPES:
            cval = scope.get_cursor_value(ich, ctype)
            logger.info(f'channel {ich} {ctype} values: {cval}')

    # Filter settings
    print('FILTER SETTINGS')
    ich = 1
    scope.enable_bandwith_filter(ich)
    scope.disable_bandwith_filter(ich)
    sfilt = 'enabled' if scope.is_bandwith_filter_enabled(ich) else 'disabled'
    logger.info(f'bandwidth filter for channel {ich} is {sfilt}')
    if args.type == 'bk':
        fc = 10 / scope.get_temporal_scale()  # cutoff frequency (Hz)
        scope.set_filter(ich, 'LP', fhigh=fc)
        scope.enable_filter(ich)
        sfilt = 'enabled' if scope.is_filter_enabled(ich) else 'disabled'
        logger.info(f'channel {ich} filter is {sfilt}')

    # Acquisition settings
    print('ACQUISITION SETTINGS')
    if args.type == 'bk':
        logger.info(f'acquisition status: {scope.get_acquisition_status()}')
        logger.info(f'# samples in last acquisition = {scope.get_nsamples(1)}')
        logger.info(f'interpolation type = {scope.get_interpolation_type()}')
    else:
        logger.info(f'# samples in internal memory = {scope.get_nsamples()}')
    logger.info(f'sample rate = {si_format(scope.get_sample_rate())}Hz')
    logger.info(f'acquisition type: {scope.get_acquisition_type()}')
    if scope.get_acquisition_type().startswith('AVER'):
        logger.info(f'# sweeps / acq: {scope.get_nsweeps_per_acquisition()}')
    scope.set_trigger_mode('norm')
    logger.info(f'trigger mode = {scope.get_trigger_mode()}')
    logger.info(f'trigger type = {scope.get_trigger_type()}')

    # Waveform settings
    print('WAVEFORM SETTINGS')
    if args.type == 'bk':
        for k, v in scope.units_per_param.items():
            try:
                val = scope.get_parameter_value(1, k)
                logger.info(f'{k} = {val} {v}')
            except VisaError as e:
                logger.error(e)
        scope.set_waveform_settings(npoints=10000)
        logger.info(scope.waveform_settings)
        logger.info(scope.comunication_format)

    # Waveform data
    print('WAVEFORM DATA')
    fig = scope.plot_waveform_data(1)

    # Screen data
    print('SCREEN CAPTURE')
    fig = scope.plot_screen_capture()

    # Show graphs
    plt.show()

except VisaError as e:
    logger.error(e)
