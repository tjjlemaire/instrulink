# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Email: theo.lemaire@epfl.ch
# @Date:   2021-02-21 23:28:05
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2021-03-30 19:38:28

import logging
from functools import wraps

from keysight_33210a import *

logger.setLevel(logging.DEBUG)


def check_error(testfunc):
    @wraps(testfunc)
    def wrapper(self, *args, **kwargs):
        try:
            out = testfunc(self, *args, **kwargs)
            self.instrument.check_error()
            return out
        except FuncGenError as err:
            logger.error(f'ERROR: {err}')
    return wrapper


class Keysight332210ATest:

    # Sine wave parameters
    Fdrive = 500e3    # Hz
    Vpp = 0.06        # Vpp
    phi = 0.          # degrees
    duration = 80e-6  # s

    def __init__(self, inst):
        ''' Initialization '''
        # Create function generator object
        self.instrument = instrument

    @check_error
    def continous_wave(self):
        ''' Apply continous sine wave. '''
        choice = input('apply continous wave (y/n)?:')
        if choice == 'y':
            self.instrument.apply_continous_wave('SIN', Fdrive, Vpp)
            input('press any key to stop')
            self.instrument.disable_output()

    @check_error
    def single_pulse(self):
        ''' Set sine pulse parameters. '''
        choice = input('set sine pulse (y/n)?:')
        if choice == 'y':
            self.instrument.set_sine_pulse(Fdrive, Vpp, phi, duration)
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
    inst = Keysight332210A()
    tester = Keysight332210ATest(inst)
    # tester.all()
except FuncGenError as err:
    logger.error(f'ERROR: {err}')
