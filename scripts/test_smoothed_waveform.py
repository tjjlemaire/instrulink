# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-15 15:44:20
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2026-07-14 13:08:00

''' Initiate test sequence with Rigol waveform generator. '''

import logging
import matplotlib.pyplot as plt
import seaborn as sns

from instrulink.rigol_dg1022z import RigolDG1022Z
from instrulink import logger
from instrulink.wf_utils import *

# Set logger level
logger.setLevel(logging.INFO)

# Waveform parameters
Fdrive = 50e3# 2.1e6  # carrier frequency (Hz)
Vpp = 2  # signal amplitude (Vpp)
tstim = 50e-3  # burst duration (s)
PRF = 100.  # burst internal PRF (Hz)
DC = 50.  # burst internal duty cycle (%)
npts = RigolDG1022Z.ARB_WF_MAXNPTS_PER_PACKET  # nominal waveform envelope vector size

# Derived parameters
tpulse = (DC / 100.) / PRF  # pulse duration (s)
toff = 1 / PRF - tpulse  # off-time (s)

# Ramp time vector
tramps = np.linspace(0, tpulse / 2, 3)  # ramp up times (s)

# Determine color map
colors = plt.get_cmap('tab10').colors

# Create figure
fig, axes = plt.subplots(1, 2, figsize=(10, 4))
axes[0].set_title('single pulse envelope')
axes[1].set_title('pulse train envelope')

# Loop over ramp up times
logger.info('looping through ramp up times and generating waveforms')
for tramp, color in zip(tramps, colors):
    label = f'tramp = {tramp * 1e3:.2f} ms'

    # Generate and plot single pulse envelope
    t, y = get_pulse_envelope(npts, tpulse, toff, tramp=tramp)
    axes[0].plot(t, y, label=label, color=color)

    # Generate and plot pulse train envelope
    t, y = get_pulse_train_envelope(1 / Fdrive, PRF=PRF, DC=DC, tramp=tramp, dur=200e-3)
    axes[1].plot(t, y, label=label, color=color)

# Post-process figure
for ax in axes:
    ax.set_xlabel('time (s)')
    ax.set_ylabel('relative amplitude')
    sns.despine(ax=ax)
    ax.legend()
fig.tight_layout()

# Render
plt.show()
