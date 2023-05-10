# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-04-27 18:30:00
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-10 11:21:29

from lab_instruments.sutter_mp285a import SutterMP285A, SutterError
from lab_instruments.logger import logger

try:
    # Grab micro-manipulator
    mp = SutterMP285A()

    # Display position, velocity and resolution
    mp.get_position(verbose=True)
    mp.get_velocity(verbose=True)
    mp.get_resolution(verbose=True)

    # Change velocity
    mp.set_velocity(1000)
    mp.get_velocity(verbose=True)

    # Change motion mode
    mp.set_resolution(0)
    mp.get_resolution(verbose=True)
    
    # Move up 1 mm
    mp.translate([0, 0, -1000])
    mp.get_position(verbose=True)

except SutterError as e:
    logger.error(e)
    quit()