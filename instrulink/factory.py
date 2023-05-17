# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2023-05-10 23:09:28
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-17 15:13:14

from .rigol_dg1022z import RigolDG1022Z
from .rigol_ds1054z import RigolDS1054Z
from .bk_2555 import BK2555
from .sutter_mp285a import SutterMP285A, SutterError
from .visa_instrument import VisaError
from .logger import logger

''' High-level interface functions to access lab instruments. '''

# Dictionary of available waveform generator classes
generator_classes = {
    'rigol': RigolDG1022Z
}

# Dictionary of available oscilloscope classes
oscilloscope_classes = {
    'bk': BK2555,
    'rigol': RigolDS1054Z
}

# Dictionary of available micro-manipulator classes
manipulator_classes = {
    'sutter': SutterMP285A
}


def grab_instrument(type, instdict, key=None):
    ''' 
    Generic function to grab instrument object.
    
    :param type: intrument type (e.g. generator, oscilloscope, etc.)
    :param instdict: dictionary of instrument classes for that specific type
    :param key: instrument key (optional, if None, the first available instrument is returned)
    :return: instrument object
    '''
    if key is not None:
        if key not in instdict.keys():
            raise ValueError(f'Invalid {type} key: "{key}". Candidates are: {instdict.keys()}')
        return instdict[key]()
    else:
        for key in instdict.keys():
            try:
                logger.info(f'Attempting to grab "{key}" {type} ...')
                return instdict[key]()
            except (VisaError, SutterError):
                logger.info(f'Failed to grab "{key}" {type}')
        raise ValueError(f'No {type} found')


def grab_generator(**kwargs):
    ''' Grab waveform generator '''
    return grab_instrument('waveform generator', generator_classes, **kwargs)


def grab_oscilloscope(**kwargs):
    ''' Grab oscilloscope '''
    return grab_instrument('oscilloscope', oscilloscope_classes, **kwargs)
    

def grab_manipulator(**kwargs):
    ''' Grab micro-manipulator '''
    return grab_instrument('micro-manipulator', manipulator_classes, **kwargs)
