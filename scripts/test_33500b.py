# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Email: theo.lemaire@epfl.ch
# @Date:   2021-02-21 23:28:05
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-22 09:52:47

import logging
from functools import wraps

from instrulink import logger, VisaError
from instrulink.keysight_33500b import Keysight33500B

logger.setLevel(logging.DEBUG)


def check_error(testfunc):
    @wraps(testfunc)
    def wrapper(self, *args, **kwargs):
        try:
            out = testfunc(self, *args, **kwargs)
            self.instrument.check_error()
            return out
        except VisaError as err:
            logger.error(f'ERROR: {err}')
    return wrapper


class Keysight33500BTest:

    # Sine wave parameters
    Fdrive = 500e3    # Hz
    Vpp = 0.06        # Vpp
    phi = 0.          # degrees
    duration = 80e-6  # s

    def __init__(self, inst):
        ''' Initialization '''
        # Create function generator object
        self.instrument = inst

    @check_error
    def continous_wave(self):
        ''' Apply continous sine wave. '''
        choice = input('apply continous wave (y/n)?:')
        if choice == 'y':
            self.instrument.apply_continous_wave('SIN', self.Fdrive, self.Vpp)
            input('press any key to stop')
            self.instrument.disable_output()

    @check_error
    def single_pulse(self):
        ''' Set sine pulse parameters. '''
        choice = input('set sine pulse (y/n)?:')
        if choice == 'y':
            self.instrument.set_sine_pulse(self.Fdrive, self.Vpp, self.phi, self.duration)
            stop = False
            while not stop:
                choice = input('press SPACE send pulse or "s" to stop:')
                if choice == ' ':
                    self.instrument.send_pulse()
                elif choice == 's':
                    stop = True

    def all(self):
        self.continous_wave()
        self.single_pulse()


try:
    inst = Keysight33500B()
    tester = Keysight33500BTest(inst)
    # tester.all()
except VisaError as err:
    logger.error(f'ERROR: {err}')
