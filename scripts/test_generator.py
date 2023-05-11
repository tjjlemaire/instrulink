# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-15 15:44:20
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-11 07:54:10

''' Initiate test sequence with Rigol waveform generator. '''

import logging
import time

from lab_instruments import logger, grab_generator, VisaError

logger.setLevel(logging.DEBUG)

try:
    # Grab function generator
    wg = grab_generator()

    # # Run test output sequence
    # instrument.test_output()

    # Set stimulus parameters
    Fdrive = 2.1e6  # Hz
    Vpp = 0.5  # Vpp
    PRF= 100. # Hz
    DC = 50.  # %
    tstim = 0.2  # s
    wg.set_gated_sine_burst(
        Fdrive, Vpp, tstim, PRF, DC, mod_trig_source='MAN')

    # Wait for some time
    time.sleep(3)

    # Trigger
    wg.trigger_channel(1)
    # Options:
    # - Launch single trigger: wg.trigger_channel(1)
    # - Start trigger loop: wg.start_trigger_loop(1)

except VisaError as e:
    logger.error(e)
    quit()