# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-08-08 10:11:50
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-17 10:54:49

from instrulink.camera import grab_camera, TriggerSource

# Grab camera
cam = grab_camera()

# Define acquisition settings
duration = 10.  # s
nacqs = 10
output_fname = 'D:/Theo/testacq/test_video.mp4'

# Acquire videos
try:
    cam.acquire(
        output_fname, duration, nacqs=nacqs, 
        trigger_source=TriggerSource.EXTERNAL)
except KeyboardInterrupt as err:
    cam.stopCapture()

# Disconnect camera
cam.disconnect()
