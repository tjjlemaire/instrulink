# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-15 15:44:20
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-08-04 11:38:21

''' Initiate test sequence with Rigol waveform generator. '''

import numpy as np
import logging
import time
import argparse

from instrulink.rigol_dg1022z import RigolDG1022Z
from instrulink import logger, grab_generator, VisaError
from instrulink.wf_utils import *
import matplotlib.pyplot as plt

logger.setLevel(logging.INFO)

# Default waveform parameters
Fdrive = 1e4  # carrier frequency (Hz)
Vpp = 2  # signal amplitude (Vpp)
tstim = 50e-3  # burst duration (s)
PRF = 100.  # burst internal PRF (Hz)
DC = 50.  # burst internal duty cycle (%)
tramp = 1.5e-3  # ramp up time for smoothed waveforms (s)

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

    npts = RigolDG1022Z.ARB_WF_MAXNPTS_PER_PACKET
    for tramp in [1e-4, 4.5e-3]:
        get_DC_smoothed_pulse_envelope(
            npts, PRF, DC, tramp=tramp, plot='all', nreps=5, Fdrive=Fdrive)

    # # Grab function generator
    # wg = grab_generator()

    # wg.set_modulated_sine_burst(
    #     Fdrive, Vpp, tstim, PRF, DC, tramp=tramp, ich_mod=ich_mod, ich_sine=ich_sine, 
    #     T=mod_T, trig_source=trigger_source)

    # # Unlock front panel
    # wg.unlock_front_panel()

    # Show figures
    plt.show()


except (VisaError, ValueError) as e:
    logger.error(e)
    quit()