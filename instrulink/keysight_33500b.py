# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Email: theo.lemaire@epfl.ch
# @Date:   2021-02-18 18:05:57
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-22 09:52:23

from .visa_instrument import VisaError
from .waveform_generator import *
from .logger import logger


class Keysight33500B(WaveformGenerator):
    ''' High-level interface to Keysight/Agilent 33500B function generator. '''

    USB_ID = 'MY5\d+'  # USB identifier
    NO_ERROR_CODE = '+0,"No error"'  # code returned when no error
    ANGLE_UNITS = ('DEG', 'RAD')  # angle units
    MAX_LEN_TEXT = 40  # maximum length of text strings
    WAVEFORM_TYPES = ('SIN', 'SQU', 'RAMP', 'PULS', 'NOIS', 'DC', 'USER')  # waveform types
    FMAX = 10e6  # maximum frequency (Hz)
    VMAX = 10.0  # maximum voltage (V)
    BURST_MODES = ('TRIG', 'GAT')  # burst modes
    MAX_BURST_PERIOD = 10.0  # maximum burst period (s)
    TRIGGER_SOURCES = ('IMM', 'EXT', 'BUS')  # trigger sources
    CHANNELS = (1, 2)  # channels

    SWEEP_SCALES = ('LIN', 'LOG')
    MOD_FUNCS = ('SIN', 'SQU', 'RAMP', 'NRAM', 'TRI', 'NOIS', 'USER')
    MOD_SOURCES = ('INT', 'EXT')

    def beep(self):
        ''' Issue a single beep immediately. '''
        self.write('SYST:BEEP')

    # --------------------- UNITS ---------------------
    
    def set_angle_unit(self, unit):
        self.check_angle_unit(unit)
        return self.write(f'UNIT:ANGL {unit}')

    def get_angle_unit(self):
        return self.query('UNIT:ANGL?')
    
    def set_voltage_unit(self, unit):
        self.check_voltage_unit(unit)
        self.write(f'VOLT:UNIT {unit}')

    def get_voltage_unit(self):
        return self.query('VOLT:UNIT?')

    # --------------------- OUTPUT ---------------------

    def enable_output(self):
        self.write('OUTP ON')

    def disable_output(self):
        self.write('OUTP OFF')

    def get_output_state(self):
        return self.query('OUTP?')

    # --------------------- BASIC WAVEFORM ---------------------

    def apply_waveform(self, wtype, freq, amp, offset=0.):
        ''' Apply a waveform with specific parameters.

            :param wtype: waveform function
            :param freq: frequency (Hz)
            :param amp: voltage amplitude (default: Vpp)
            :param offset: voltage offset (V)
        '''
        self.check_waveform_type(wtype)
        self.write(f'APPL:{wtype} {freq}, {amp}, {offset}')
    
    def set_waveform_type(self, wtype):
        self.check_waveform_type(wtype)
        self.write(f'FUNC {wtype}')

    def get_waveform_type(self):
        return self.query('FUNC?')

    def set_waveform_freq(self, freq):
        self.check_freq(freq)
        self.write(f'FREQ {freq}')

    def get_waveform_freq(self):
        return float(self.query('FREQ?'))

    def set_waveform_amp(self, amp):
        self.check_amp(amp)
        self.write(f'VOLT {amp}')

    def get_waveform_amp(self):
        return float(self.query(f'VOLT?'))

    def set_waveform_offset(self, offset):
        self.check_offset(offset)
        self.write(f'VOLT:OFFS {offset}')

    def get_waveform_offset(self):
        return float(self.query(f'VOLT:OFFS?'))
    
    def set_square_duty_cycle(self, DC):
        self.check_duty_cycle(DC)
        self.write(f'FUNC:SQU:DCYC {DC}')

    def get_square_duty_cycle(self):
        return float(self.query('FUNC:SQU:DCYC?'))

    # --------------------- BURST ---------------------

    def enable_burst(self):
        self.write(f'BUR:STAT ON')
    
    def disable_burst(self):
        self.write(f'BUR:STAT OFF')

    def set_burst_mode(self, mode):
        self.check_burst_mode(mode)
        self.write(f'BURS:MODE {mode}')
    
    def get_burst_mode(self):
        return self.query(f'BURS:MODE?')

    def set_burst_ncycles(self, n):
        self.write(f'BURS:NCYC {n}')

    def get_burst_ncycles(self):
        return int(self.query(f'BURS:NCYC?'))

    def set_burst_internal_period(self, T):
        self.write(f'BURS:INT:PER {T}')

    def get_burst_internal_period(self):
        return float(self.query('BURS:INT:PER?'))

    def set_burst_duration(self, t):
        T = 1 / self.get_carrier_freq()
        ncycles = self.check_burst_duration(t, T)
        self.set_burst_ncycles(ncycles)

    def set_burst_phase(self, phi):
        self.check_burst_phase(phi)
        self.write(f'BURS:PHAS {phi}')

    def get_burst_phase(self):
        return float(self.query('BURS:PHAS?'))
    
    def set_burst_gated_polarity(self, pol):
        self.check_polarity(pol)
        self.write(f'BURS:GATE:POL {pol}')

    def get_burst_gated_polarity(self):
        return self.query(f'BURS:GATE:POL?')

    # --------------------- TRIGGER ---------------------

    def set_trigger_source(self, source):
        self.check_trigger_source(source)
        self.write(f'TRIG:SOUR {source}')

    def get_trigger_source(self):
        return self.query('TRIG:SOUR?')

    def set_trigger_slope(self, slope):
        self.check_slope(slope)
        self.write(f'TRIG:SLOP {slope}')

    def get_trigger_slope(self):
        return self.query('TRIG:SLOP?')
    
    def set_external_trigger(self):
        self.set_trigger_source('EXT')
        self.set_trigger_slope('POS')

    def set_internal_trigger(self):
        self.set_trigger_source('BUS')
        self.set_trigger_slope('POS')

    def single_pulse(self):
        logger.info('sending single pulse...')
        self.set_trigger_source('BUS')
        self.enable_output()
        self.trigger()
        self.wait()
    
    def wait_for_external_trigger(self):
        logger.info('waiting for external trigger...')
        self.set_trigger_source('EXT')
        self.enable_output()
    
    def wait_for_manual_trigger(self):
        logger.info('waiting for external trigger...')
        self.set_trigger_source('MAN')
        self.enable_output()

    # --------------------- TRIGGER OUTPUT ---------------------

    def enable_trigger_output(self):
        self.write('OUTP:TRIG ON')

    def disable_trigger_output(self):
        self.write('OUTP:TRIG OFF')
    
    def set_trigger_output_slope(self, slope):
        self.check_slope(slope)
        self.write(f'OUTP:TRIG:SLOP {slope}')

    def get_trigger_output_slope(self):
        return self.query('OUTP:TRIG:SLOP?')

    # --------------------- SINE ---------------------

    def set_sine_pulse(self, freq, amp, phi, t):
        ''' Set a sinusoidal pulse with specific parameters.

            :param freq: carrier frequency (Hz)
            :param amp: pulse amplitude (Vpp)
            :param phi: sine pulse phase (degrees)
            :param t: pulse duration (s)
        '''
        self.set_mod_on('BURS')
        self.set_burst_internal_period(self.MAX_BURST_PERIOD)
        self.set_carrier_freq(freq)
        self.set_carrier_amp(amp)
        if not self.get_phase_unit() == 'DEG':
            self.set_phase_unit('DEG')
        self.set_burst_phase(phi)
        self.set_burst_duration(t)

    # --------------------- PULSE ---------------------

    def set_pulse_mode(self):
        ''' Select pulse wave mode. '''
        self.set_waveform_type('PULS')

    def set_pulse_period(self, T):
        ''' Set the pulse period (s). '''
        self.write(f'PULS:PER {T}')

    def get_pulse_period(self):
        ''' Get the pulse period (s). '''
        return float(self.query('PULS:PER?'))

    # --------------------- MODULATION ---------------------

    def set_mod_on(self, key):
        ''' Enable specific modulation mode. '''
        if self.mod_key is not None and self.mod_key != key:
            self.set_mod_off(self.mod_key)
        self.write(f'{key}:STAT ON')
        self.mod_key = key

    def set_mod_off(self, key):
        ''' Disable specific modulation mode. '''
        self.write(f'{key}:STAT OFF')
        self.mod_key = None

    def get_mod_type(self):
        ''' Check which (if any) modulation mode is enabled. '''
        assert bool(self.query(f'{self.mod_key}:STAT?')), 'modulation key mismatch'
        return self.mod_key

    def set_mod_source(self, source):
        ''' Set the source type (internal or external) of a specific modulation mode. '''
        if source not in self.MOD_SOURCES:
            raise VisaError(
                f'{source} is not a valid modulating source (options are {self.MOD_SOURCES})')
        self.write(f'{self.mod_key}:SOUR {source}')

    def get_mod_source(self):
        ''' Get the source type (internal or external) of a specific modulation mode. '''
        return self.query(f'{self.mod_key}:SOUR?')

    def set_mod_func(self, func):
        ''' Set the nature of the modulating function. '''
        if func not in self.MOD_FUNCS:
            raise VisaError(
                f'{func} is not a valid modulating function (options are {self.MOD_FUNCS})')
        self.write(f'{self.mod_key}:INT:FUNC {func}')

    def get_mod_func(self):
        ''' Get the nature of the modulating function. '''
        return self.query(f'{self.mod_key}:INT:FUNC?')

    def set_mod_freq(self, freq):
        ''' Set the modulating function frequency (in Hz). '''
        self.write(f'{self.mod_key}:INT:FREQ {freq}')

    def get_mod_freq(self):
        ''' Get the modulating function frequency (in Hz). '''
        return float(self.query(f'{self.mod_key}:INT:FREQ?'))

    # --------------------- AM ---------------------

    def set_AM_mod_depth(self, depth):
        ''' Set the signal amplitude modulation depth. '''
        self.write(f'AM:DEPT {depth}')

    def get_AM_mod_depth(self):
        ''' Get the signal amplitude modulation depth. '''
        return self.query(f'AM:DEPT?')
