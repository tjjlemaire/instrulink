# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-04-27 18:30:00
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-17 10:54:43

from instrulink import grab_manipulator, SutterError, logger

try:
    # Grab micro-manipulator
    mp = grab_manipulator()

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

    mp.disconnect()

except SutterError as e:
    logger.error(e)
    quit()