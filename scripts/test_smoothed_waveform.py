# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-15 15:44:20
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-08-04 16:08:56

''' Initiate test sequence with Rigol waveform generator. '''

import logging
import matplotlib.pyplot as plt

from instrulink.rigol_dg1022z import RigolDG1022Z
from instrulink import logger
from instrulink.wf_utils import get_DC_smoothed_pulse_envelope

# Set logger level
logger.setLevel(logging.INFO)

# Waveform parameters
Fdrive = 1e4  # carrier frequency (Hz)
Vpp = 2  # signal amplitude (Vpp)
tstim = 50e-3  # burst duration (s)
PRF = 100.  # burst internal PRF (Hz)
DC = 50.  # burst internal duty cycle (%)
npts = RigolDG1022Z.ARB_WF_MAXNPTS_PER_PACKET
tramps = [1e-4, 4.5e-3]  # ramp up times for smoothed waveforms (s)

for tramp in tramps:
    get_DC_smoothed_pulse_envelope(
        npts, PRF, DC, tramp=tramp, plot='all', nreps=5, Fdrive=Fdrive)

# Show figures
plt.show()
