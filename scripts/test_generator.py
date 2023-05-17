# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-15 15:44:20
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-17 10:54:58

''' Initiate test sequence with Rigol waveform generator. '''

import logging
import time
import argparse

from instrulink import logger, grab_generator, VisaError

logger.setLevel(logging.INFO)

# Default waveform parameters
Fdrive = 1e3  # carrier frequency (Hz)
Vpp = 0.5  # signal amplitude (Vpp)
tstim = 0.1  # burst duration (s)
PRF = 100.  # burst internal PRF (Hz)
DC = 50.  # burst internal duty cycle (%)

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument(
    '--isignal', type=int, default=2, choices=(1, 2), help='Signal channel index')
parser.add_argument(
    '--igating', type=int, default=1, choices=(1, 2), help='Gating channel index')
parser.add_argument(
    '-T', type=float, default=-1., help='Modulation period (s, defaults to -1, i.e. continous looping)')
parser.add_argument(
    '-s', '--source', type=str, default='int', choices=('int', 'man'), help='Trigger source (only if modulation period is specified)')
args = parser.parse_args()
ich_sine = args.isignal  # signal channel
ich_mod = args.igating  # gating channel
trigger_source = args.source.upper()  # trigger source
mod_T = args.T  # modulation period (s)

try:
    # If modulation period is not specified
    if mod_T < 0:
        # Set modulation period to None
        mod_T = None
        # If manual trigger, check that signal and gating channels are different
        if trigger_source == 'MAN' and ich_sine == ich_mod:
            raise ValueError('Signal and gating channels must be different for single burst trigger')
    # Otherwise
    else:
        # Check that trigger source is internal
        if trigger_source != 'INT':
            raise ValueError('Trigger source must be internal when modulation period is specified')
        # Check that signal and gating channels are different
        if ich_sine == ich_mod:
            raise ValueError('Signal and gating channels must be different when modulation period is specified')
except ValueError as e:
    logger.error(e)
    quit()

try:
    # Grab function generator
    wg = grab_generator()

    # If modulation period is not specified
    if mod_T is None:
        # If internal trigger is used, apply continous looping
        if trigger_source == 'INT':
            wg.set_looping_sine_burst(
                ich_sine, Fdrive, Vpp=Vpp, ncycles=.01 * DC / PRF * Fdrive, BRF=PRF, 
                ich_trig=None if ich_mod == ich_sine else ich_mod)
        
        # If manual trigger is used, apply single burst
        else:
            wg.set_gated_sine_burst(
                Fdrive, Vpp, tstim, PRF, DC,
                ich_sine=ich_sine, ich_mod=ich_mod,
                trig_source=trigger_source
            )
            time.sleep(2)
            wg.trigger_channel(ich_mod)
    
    # If modulation period is specified
    else:
        # Apply signal on signal channel gated by other channel
        wg.set_gated_sine_burst(
            Fdrive, Vpp, tstim, PRF, DC,
            ich_sine=ich_sine, ich_mod=ich_mod,
            trig_source=trigger_source, T=mod_T
        )

    # Unlock front panel
    wg.unlock_front_panel()

except VisaError as e:
    logger.error(e)
    quit()