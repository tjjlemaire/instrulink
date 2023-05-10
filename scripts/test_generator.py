# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-15 15:44:20
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-10 11:07:56

''' Initiate test sequence with Rigol waveform generator. '''

import logging
import time

from lab_instruments.visa_instrument import VisaError
from lab_instruments.rigol_dg1022z import RigolDG1022Z
from lab_instruments.logger import logger


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
    instrument.set_gated_sine_burst(
        Fdrive, Vpp, tstim, PRF, DC, mod_trig_source='MAN')

    # Wait for some time
    time.sleep(3)

    # Trigger
    instrument.trigger_channel(1)
    # Options:
    # - Launch single trigger: instrument.trigger_channel(1)
    # - Start trigger loop: instrument.start_trigger_loop(1)

except VisaError as e:
    logger.error(e)
    quit()