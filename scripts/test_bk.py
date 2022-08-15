# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-04-07 17:51:29
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2022-08-15 09:57:20

import numpy as np
import matplotlib.pyplot as plt
from lab_instruments.logger import logger
from lab_instruments.visa_instrument import VisaError
from lab_instruments.bk_2555 import BKScope
from lab_instruments.si_utils import si_format


try:
    # Create oscilloscope object
    bkscope = BKScope()

    # Display settings
    # print('DISPLAY')
    # bkscope.display_menu()
    # bkscope.hide_menu()
    # bkscope.show_trace(1)
    # logger.info(f'trace on channel 1: {bkscope.is_trace(1)}')

    # Temporal and vertical scales / offsets
    print('SCALES')
    bkscope.auto_setup()
    # bkscope.set_temporal_scale(400e-6)
    logger.info(f'TDIV = {bkscope.get_temporal_scale()} S')
    bkscope.set_temporal_scale(400e-3)
    
    # bkscope.set_vertical_scale(1, 1.)
    logger.info(f'C1:VDIV = {bkscope.get_vertical_scale(1)} V')
    # # bkscope.set_vertical_offset(1, 0.8)
    logger.info(f'C1:VOFF = {bkscope.get_vertical_offset(1)} V')

    # Probes settings
    print('PROBE')
    bkscope.set_probe_attenuation(1, 1)
    logger.info(f'C1:ATTN = {bkscope.get_probe_attenuation(1)}')

    # Trigger settings
    print('TRIGGER')
    # bkscope.set_trigger_level(1, 0.05)
    logger.info(f'C1:TRLV = {bkscope.get_trigger_level(1)} V')
    # bkscope.set_trigger_delay(-5e-3)
    bkscope.check_error()
    logger.info(f'TRDL = {si_format(bkscope.get_trigger_delay())}s')
    # bkscope.set_trigger_coupling_mode(1, 'DC')
    logger.info(f'C1:TRCP = {bkscope.get_trigger_coupling_mode(1)}')
    # bkscope.set_trigger_mode('auto')
    logger.info(f'TRMD = {bkscope.get_trigger_mode()}')
    # bkscope.set_trigger_slope(1, 'POS')
    logger.info(f'C1:TRSL = {bkscope.get_trigger_slope(1)}')

    # Acquisition settings
    # print('ACQUISITION')
    # logger.info(f'sample rate = {si_format(bkscope.get_sample_rate())}Hz')
    # logger.info(f'# samples in last acquisition = {bkscope.get_nsamples(1)}')
    # bkscope.arm_acquisition()
    # logger.info(f'TRMD = {bkscope.get_trigger_mode()}')

    # Waveform parameters
    # print('WAVEFORM PARAMS')
    # logger.info(f'C1:FREQ = {si_format(bkscope.get_frequency(1))}Hz')
    # logger.info(f'C1:VPP = {bkscope.get_peak_to_peak(1)} V')
    # for k, v in bkscope.units_per_param.items():
    #     val = bkscope.get_parameter_value(1, k)
    #     print(f'{k} = {val} {v}')

    # Waveform settings
    print('WAVEFORM')
    bkscope.set_waveform_settings(npoints=10000)
    # logger.info(bkscope.waveform_settings)
    # logger.info(bkscope.comunication_format)

    # Waveform data
    t, y = bkscope.get_waveform_data(1)
    logger.info(f'waveform peak-to-peak: Vpp = {si_format(np.ptp(y), 3)}V')
    plt.figure()
    plt.xlabel('time (ms)')
    plt.ylabel(f'voltage (V)')
    plt.title(f'waveform data')
    plt.plot(t * 1e3, y, label=f'ch{1}')

    # # Screen dump
    # plt.figure()
    # plt.title('screen dump')
    # plt.imshow(bkscope.screen_dump())

    # Show graphs
    plt.show()

except VisaError as e:
    logger.error(e)
