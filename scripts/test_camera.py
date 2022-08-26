# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-08-08 10:11:50
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2022-08-15 09:57:29

from lab_instruments.camera import *

# Grab camera
cam = grab_camera()

# Acquire videos
duration = 10.  # s
nacqs = 10
output_fname = 'D:/Theo/testacq/video_avi3.mp4'
try:
    cam.acquire(
        output_fname, duration, nacqs=nacqs, 
        trigger_source=TriggerSource.EXTERNAL)
except KeyboardInterrupt as err:
    cam.stopCapture()

# Disconnect camera
cam.disconnect()
