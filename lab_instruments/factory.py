# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2023-05-10 23:09:28
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-11 09:02:43

from .rigol_dg1022z import RigolDG1022Z
from .rigol_ds1054z import RigolDS1054Z
from .bk_2555 import BK2555
from .sutter_mp285a import SutterMP285A
from .camera import grab_flir_camera


''' High-level interface functions to access lab instruments. '''


def grab_generator(type='rigol'):
    ''' Grab waveform generator of specific type. '''
    if type == 'rigol':
        return RigolDG1022Z()
    else:
        raise ValueError(f'Invalid oscilloscope type: {type}')


def grab_oscilloscope(type='bk'):
    ''' Grab oscilloscope of specific type. '''
    if type == 'bk':
        return BK2555()
    elif type == 'rigol':
        return RigolDS1054Z()
    else:
        raise ValueError(f'Invalid generator type: {type}')
    

def grab_manipulator(type='sutter'):
    ''' Grab micro-manipulator of specific type. '''
    if type == 'sutter':
        return SutterMP285A()
    else:
        raise ValueError(f'Invalid micro-manipulator type: {type}')


def grab_camera(type='flir'):
    ''' Grab camera of specific type. '''
    if type == 'flir':
        return grab_flir_camera()
    else:
        raise ValueError(f'Invalid camera type: {type}')