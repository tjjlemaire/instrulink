# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-04-27 18:30:00
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2022-08-15 09:57:38

import numpy as np
np.set_printoptions(precision=2, formatter={'float': lambda x: f'{x:.2f}'})

from lab_instruments.sutter_mp285a import SutterMP285A, SutterError
from lab_instruments.logger import logger

try:
    # Grab micro-manipulator
    mp = SutterMP285A()

    # Display position, velocity and resolution
    x = mp.get_position()
    logger.info(f'position = {x} um')
    v = mp.get_velocity()
    logger.info(f'velocity = {v} um/s')
    res = mp.get_resolution()
    logger.info(f'motion mode: {mp.res_str(res)}')

    # Change velocity
    mp.set_velocity(1000)
    v = mp.get_velocity()
    logger.info(f'velocity = {v} um/s')

    # Change motion mode
    mp.set_resolution(0)
    res = mp.get_resolution()
    logger.info(f'motion mode: {mp.res_str(res)}')
    
    # # Move up 1 mm
    x[2] -= 1000
    mp.set_position(x)
    x = mp.get_position()
    logger.info(f'position = {x} um')

except SutterError as e:
    logger.error(e)
    quit()