# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2023-04-25 13:25:00
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-17 10:54:12

from instrulink.nidaq import *

# Parameters
interval = 1.5 #20.019  # s
npulses = 16
camdelay = 0.  # s
stimdelay = 2.8  # s

# Set up train of trigger pulses for US stimuli
stim_triggers = get_trigger_pulses('stim_triggers', stimdelay , interval, npulses, 1)
print(stim_triggers)

# Set up train of trigger pulses for camera acquisitions
cam_triggers = get_trigger_pulses('cam_triggers', camdelay, interval, npulses, 2)
print(cam_triggers)
