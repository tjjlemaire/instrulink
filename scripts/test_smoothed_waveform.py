# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-15 15:44:20
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-08-07 14:54:46

''' Initiate test sequence with Rigol waveform generator. '''

import logging
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm

from instrulink.rigol_dg1022z import RigolDG1022Z
from instrulink import logger
from instrulink.wf_utils import *

# Set logger level
logger.setLevel(logging.INFO)

# Waveform parameters
Fdrive = 2.1e6  # carrier frequency (Hz)
Vpp = 2  # signal amplitude (Vpp)
tstim = 50e-3  # burst duration (s)
PRF = 100.  # burst internal PRF (Hz)
DC = 50.  # burst internal duty cycle (%)
npts = RigolDG1022Z.ARB_WF_MAXNPTS_PER_PACKET  # nominal waveform envelope vector size
tramp_bounds = (0, 5e-3)  # ramp up time range for smoothed waveforms (s)
tramps = np.linspace(*tramp_bounds, 20)  # ramp up times (s)

# Determine which ramps to actually plot
nplt = 3
if nplt < tramps.size:
    iplt = np.linspace(0, tramps.size - 1, nplt).astype(int)
else:
    iplt = np.arange(tramps.size)

# Determine color map
cmap = sns.color_palette('crest', as_cmap=True)

# Initialize vector to store log-frequency spectrum value (in dB) at PRF 
# for each ramp time
PRFdb = np.zeros(tramps.size)

# Create figure for spectrum plot
fig, axes = plt.subplots(1, 2, figsize=(8, 4))

# Loop over ramp up times
logger.info('looping through ramp up times and generating waveforms')
for i, tramp in tqdm(enumerate(tramps)):
    # Generate label
    label = f'tramp = {tramp * 1e3:.2f} ms'

    # Generate waveform
    t, y = get_DC_smoothed_pulse_envelope(npts, PRF, DC, tramp=tramp)

    # # Plot waveform
    # plot_smoothed_waveform(
    #     t, y, Fdrive, ax=axes[0], nreps=5, label=label, mark_regs=False, 
    #     title='waveforms comparison')
    
    # Plot spectrum
    _, PRFdb[i] = plot_waveform_spectrum(
        t, y, Fdrive, ax=axes[0], nreps=20, 
        plot=i in iplt, label=label, 
        mark_freqs=i == len(tramps) - 1, title='spectra comparison',
        get_PRF_val=True, color=cmap(i / (len(tramps) - 1)))

# Plot log-spectrum value at PRF as a function of ramp up time
ax = axes[1]
sns.despine(ax=ax)
ax.set_title(f'spectrum attenuation at PRF = {PRF:.2f} Hz')
ax.plot(tramps * 1e3, PRFdb, c='k', marker='o')
ax.set_xlabel('ramp up time (ms)')
ax.set_ylabel('log-spectrum value at PRF (dB)')

# Adjust figure layout and render
fig.tight_layout()
plt.show()
