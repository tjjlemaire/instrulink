# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-15 15:44:20
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-08 17:43:22

''' Initiate test sequence with Rigol waveform generator. '''

import logging
import time

from lab_instruments.visa_instrument import VisaError
from lab_instruments.rigol import RigolDG1022Z
from lab_instruments.logger import logger
from lab_instruments.wf_utils import get_smoothed_waveform


logger.setLevel(logging.DEBUG)

try:
    # Grab function generator
    instrument = RigolDG1022Z()

    # # Run test output sequence
    # instrument.test_output()

    # Set stimulus parameters
    Fdrive = 2.1e6  # Hz
    Vpp = 0.5  # Vpp
    PRF= 100. # Hz
    DC = 50.  # %
    tstim = 0.2  # s
    instrument.set_gated_sine_burst(Fdrive, Vpp, tstim, PRF, DC, mod_trig_source='MAN')

    time.sleep(3)
    instrument.trigger_channel(1)

    # # Test smoothed waveform
    # f = 10e3  # carrier frequency (Hz)
    # tpulse = 20e-3  # pulse duration (s)
    # tsmooth = 1e-3  # smoothing period for ramp-up and ramp-down phases (s)
    # npc = 25  # number of points per cycle
    # _, y = get_smoothed_waveform(f, tpulse, tsmooth, npercycle=npc)
    # ich = 1
    # sr = y.size / tpulse  # Hz
    # instrument.apply_arbitrary(ich, 1000)
    # instrument.set_arbitrary_waveform(ich, y)
    # instrument.set_burst_internal_period(ich, 0.1)  # s
    # instrument.set_burst_ncycles(ich, 1)  # s
    # instrument.enable_burst(ich)    
    # instrument.enable_output_channel(ich)

    # Options:
    # - Launch single trigger: instrument.trigger_channel(1)
    # - Start trigger loop: instrument.start_trigger_loop(1)

except VisaError as e:
    logger.error(e)
    quit()