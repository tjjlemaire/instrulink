# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-15 15:44:20
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-08-08 11:51:23

''' Initiate test sequence with Rigol waveform generator. '''

import logging
import time
import argparse

from instrulink import logger, grab_generator, VisaError

logger.setLevel(logging.INFO)

# Default waveform parameters
Fdrive = 1e4  # carrier frequency (Hz)
Vpp = 0.5  # signal amplitude (Vpp)
tstim = 200e-3  # burst duration (s)
PRF = 100.  # burst internal PRF (Hz)
DC = 50.  # burst internal duty cycle (%)
tramp = 0.  # nominal pulse ramp up time (s)

# Parse command line arguments
parser = argparse.ArgumentParser()
parser.add_argument(
    '--icarrier', type=int, default=2, choices=(1, 2), help='Carrier channel index')
parser.add_argument(
    '--igating', type=int, default=1, choices=(1, 2), help='Gating channel index')
parser.add_argument(
    '--gtype', default='trig', choices=('mod', 'trig'), 
    help='Gating type, i.e. "mod" for modulation or "trig" for trigger (only if modulation period is specified)')
parser.add_argument(
    '-s', '--source', type=str, default='int', choices=('int', 'man'), help='Trigger source (only if modulation period is specified)')
parser.add_argument(
    '-f', '--frequency', type=float, default=Fdrive, help='Carrier frequency (Hz)')
parser.add_argument(
    '--vpp', type=float, default=Vpp, help='Signal amplitude (Vpp)')
parser.add_argument(
    '--tstim', type=float, default=tstim, help='Burst duration (s)')
parser.add_argument(
    '--PRF', type=float, default=PRF, help='Burst internal PRF (Hz)')
parser.add_argument(
    '--DC', type=float, default=DC, help='Burst internal duty cycle (%)')
parser.add_argument(
    '--tramp', type=float, default=tramp, help='Nominal pulse ramp up time (ms)')
parser.add_argument(
    '-T', type=float, default=-1., help='Modulation period (s, defaults to -1, i.e. continous looping)')
args = parser.parse_args()
ich_carrier = args.icarrier  # carrier channel
ich_gate = args.igating  # gating channel
gtype = args.gtype  # gating type
trigger_source = args.source.upper()  # trigger source
Fdrive = args.frequency  # carrier frequency (Hz)
Vpp = args.vpp  # signal amplitude (Vpp)
tstim = args.tstim  # burst duration (s)
PRF = args.PRF  # burst internal PRF (Hz)
DC = args.DC  # burst internal duty cycle (%)
tramp = args.tramp * 1e-3  # nominal pulse ramp up time (s)
mod_T = args.T  # modulation period (s)

try:
    # If modulation period is not specified
    if mod_T < 0:
        # Set modulation period to None
        mod_T = None
        # If manual trigger, check that signal and gating channels are different
        if trigger_source == 'MAN' and ich_carrier == ich_gate:
            raise ValueError('Signal and gating channels must be different for single burst trigger')
    # Otherwise
    else:
        # Check that signal and gating channels are different
        if ich_carrier == ich_gate:
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
            tburst = .01 * DC / PRF   # burst duration = pulse duration (s)
            wg.set_looping_sine_burst(
                ich_carrier, Fdrive, Vpp=Vpp, ncycles=tburst * Fdrive, 
                PRF=PRF, tramp=tramp, 
                ich_trig=None if ich_gate == ich_carrier else ich_gate,
                gate_type=gtype,
            )
        
        # If manual trigger is used, apply single burst
        else:
            wg.set_gated_sine_burst(
                Fdrive, Vpp, tstim, PRF, DC,
                ich_carrier=ich_carrier, ich_gate=ich_gate,
                trig_source=trigger_source,
                tramp=tramp,
                gate_type=gtype,
            )
            time.sleep(2)
            wg.trigger_channel(ich_gate)
    
    # If modulation period is specified
    else:
        # Apply signal on signal channel triggered/modulated by other channel
        wg.set_gated_sine_burst(
            Fdrive, Vpp, tstim, PRF, DC,
            tramp=tramp,
            ich_carrier=ich_carrier, ich_gate=ich_gate,
            trig_source=trigger_source, T=mod_T,
            gate_type=gtype
        )
        
        # Manual trigger: set up infinite trigger loop at specified periodicity
        if trigger_source == 'MAN':
            while True:
                wg.trigger_channel(ich_gate)
                time.sleep(mod_T)

    # Unlock front panel
    wg.unlock_front_panel()

    # Close connection
    wg.disconnect()

except VisaError as e:
    logger.error(e)
    quit()