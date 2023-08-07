# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-15 09:26:06
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-08-07 16:14:09

import abc
import numpy as np

from .visa_instrument import *


class WaveformGenerator(VisaInstrument):
    ''' Generic interface to a waveform generator instrument using the SCPI command interface '''

    PREFIX = ''
    SLOPES = ('POS', 'NEG')
    POLARITIES = ('NORM', 'INV') 
    VOLTAGE_UNITS = ('VPP', 'VRMS', 'DBM')
    
    # --------------------- MISCELLANEOUS ---------------------
    
    def connect(self):
        super().connect()
        self.disable_output()
        self.beep()
        # self.display_for('instrument connected', duration=1.0)

    def get_version(self):
        ''' Get system SCPI version. '''
        return float(self.query('SYST:VERS?'))

    def get_nchannels(self):
        ''' Get the number of channels available in the instrument '''
        return float(self.query(f'SYST:CHAN:NUM?'))
    
    @abc.abstractmethod
    def beep(self):
        ''' Issue a single beep immediately. '''
        raise NotImplementedError
    
    def check_slope(self, slope):
        if slope not in self.SLOPES:
            raise VisaError(
                f'{slope} is not a valid slope (options are {self.SLOPES})')
    
    def check_polarity(self, pol):
        if pol not in self.POLARITIES:
            raise VisaError(
                f'{[pol]} is not a valid polarity (options are {self.POLARITIES})')
    
    def wait(self):
        self.write('*WAI')
        
    # --------------------- FRONT PANEL & DISPLAY ---------------------

    def lock_front_panel(self):
        self.write('SYST:KLOC:STAT ON')

    def unlock_front_panel(self):
        self.write('SYST:KLOC:STAT OFF')

    @property
    @abc.abstractmethod
    def MAX_LEN_TEXT(self):
        ''' Maximum text length on instrument display '''
        raise NotImplementedError
    
    def display_text(self, text):
        ''' Display text on the instrument screen. '''
        if len(text) > self.MAX_LEN_TEXT:
            raise VisaError(f'Maximum text length ({self.MAX_LEN_TEXT} chars) exceeded.')
        self.write(f'DISP:TEXT "{text}"')

    def erase_text(self):
        ''' Erase text from the instrument screen. '''
        self.write('DISP:TEXT:CLEAR')
    
    def display_for(self, text, duration=1.):
        ''' Display text on the instrument screen for a given duration (in s). '''
        self.chain(lambda: self.display_text(text), self.erase_text, interval=duration)

    # --------------------- ERRORS ---------------------

    def get_last_error(self):
        ''' Get last entry in error queue. '''
        return self.query('SYST:ERR?')
    
    def enable_beep_on_error(self):
        ''' Enable instrument beeping upon error. '''
        self.write('SYST:BEEP:STAT ON')

    def disable_beep_on_error(self):
        ''' Disable instrument beeping upon error. '''
        self.write('SYST:BEEP:STAT OFF')

    def beeps_on_error(self):
        ''' Get whether instrument beeps upon error. '''
        return bool(self.query('SYST:BEEP:STAT?'))

    # --------------------- UNITS ---------------------

    @property
    @abc.abstractmethod
    def ANGLE_UNITS(self):
        raise NotImplementedError

    def check_angle_unit(self, unit):
        if unit not in self.ANGLE_UNITS:
            raise VisaError(
                f'{unit} is not a valid angle unit (options are {self.ANGLE_UNITS})')
    
    @abc.abstractmethod
    def set_angle_unit(self, *args, **kwargs):
        ''' Set the unit used for angles. '''
        raise NotImplementedError

    @abc.abstractmethod        
    def get_angle_unit(self, *args, **kwargs):
        ''' Get the unit used for angles. '''
        raise NotImplementedError
    
    def check_voltage_unit(self, unit):
        if unit not in self.VOLTAGE_UNITS:
            raise VisaError(
                f'{unit} is not a valid voltage unit (options are {self.VOLTAGE_UNITS})')
    
    @abc.abstractmethod
    def set_voltage_unit(self, *args, **kwargs):
        ''' Set the unit used for voltages. '''
        raise NotImplementedError

    @abc.abstractmethod        
    def get_voltage_unit(self, *args, **kwargs):
        ''' Get the unit used for voltages. '''
        raise NotImplementedError

    # --------------------- OUTPUT ---------------------

    @abc.abstractmethod
    def enable_output(self):
        ''' Turn all outputs ON '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def disable_output(self):
        ''' Turn all outputs OFF '''
        raise NotImplementedError

    @abc.abstractmethod    
    def get_output_state(self, *args, **kwargs):
        ''' Get output state '''
        raise NotImplementedError

    # --------------------- BASIC WAVEFORM ---------------------

    @property
    @abc.abstractmethod
    def WAVEFORM_TYPES(self):
        return NotImplementedError

    def check_waveform_type(self, wtype):
        ''' Check that waveform type is available on the instrument '''
        if wtype not in self.WAVEFORM_TYPES:
            raise VisaError(
                f'{wtype} is not a valid waveform (options are {self.WAVEFORM_TYPES})')
    
    @abc.abstractmethod
    def apply_waveform(*args, **kwargs):
        raise NotImplementedError

    def apply_pulse(self, *args, **kwargs):
        self.apply_waveform('PULS', *args, **kwargs)

    def apply_ramp(self, *args, **kwargs):
        self.apply_waveform('RAMP', *args, **kwargs)

    def apply_sine(self, *args, **kwargs):
        self.apply_waveform('SIN', *args, **kwargs)

    def apply_square(self, *args, **kwargs):
        self.apply_waveform('SQU', *args, **kwargs)

    def apply_triangle(self, *args, **kwargs):
        self.apply_waveform('TRI', *args, **kwargs)
    
    def apply_DC(self, *args, **kwargs):
        self.apply_waveform('DC', *args, freq=1, amp=1, **kwargs)

    @abc.abstractmethod
    def set_waveform_type(self, *args, **kwargs):
        ''' Set the nature of the carrier waveform. '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def get_waveform_type(self, *args, **kwargs):
        ''' Get the nature of the carrier waveform. '''
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def FMAX(self):
        raise NotImplementedError

    def check_freq(self, freq):
        if freq > self.FMAX:
            raise VisaError(f'Frequency must be lower than {self.FMAX}')

    @abc.abstractmethod
    def set_waveform_freq(self, *args, **kwargs):
        ''' Set the carrier frequency (Hz). '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def get_waveform_freq(self, *args, **kwargs):
        ''' get the carrier frequency (Hz). '''
        raise NotImplementedError
    
    @property
    @abc.abstractmethod
    def VMAX(self):
        raise NotImplementedError

    def check_amp(self, amp):
        if amp / 2 > self.VMAX:
            raise VisaError(f'VPP exceeds {self.VMAX} V')
    
    @abc.abstractmethod
    def set_waveform_amp(self, *args, **kwargs):
        ''' set the carrier signal amplitude '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_waveform_amp(self, *args, **kwargs):
        ''' Get the carrier signal amplitude '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def check_offset(self, offset, *args, **kwargs):
        ''' Check the waveform voltage offset '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def set_waveform_offset(self, *args, **kwargs):
        ''' Set the waveform voltage offset (V). '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_waveform_offset(self, *args, **kwargs):
        ''' Get the waveform voltage offset (V). '''
        raise NotImplementedError
    
    def check_phase(self, phi):
        ''' Check the waveform phase '''
        if phi < 0. or phi > 360:
            raise VisaError(f'phase out of range : {phi} (must be within [0, 360]deg)')

    @abc.abstractmethod
    def set_waveform_phase(self, *args, **kwargs):
        ''' Set the waveform phase of the specified channel (in degrees) '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def get_waveform_phase(self, *args, **kwargs):
        ''' Get the waveform phase of the specified channel (in degrees) '''
        raise NotImplementedError
    
    def check_duty_cycle(self, DC):
        ''' Check duty cycle '''
        if DC <= 0. or DC >= 100.:
            raise VisaError('Duty cycle out of range (must be within [0-100]%)')
    
    @abc.abstractmethod
    def set_square_duty_cycle(self, *args, **kwargs):
        ''' Set the square wave duty cycle (in %). '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_square_duty_cycle(self, *args, **kwargs):
        ''' Get the square wave duty cycle (in %). '''
        raise NotImplementedError

    # --------------------- ARBITRARY WAVEFORMS ---------------------

    def normalize(self, y, lb=-1, ub=1):
        ''' Normalize AF signal to [-1, 1] interval by linear transformation.

            :param y: AF signal
            :param lb: lower bound
            :param ub: upper bound
        '''
        return (y - y.min()) / np.ptp(y) * (ub - lb) + lb

    # --------------------- BURST ---------------------

    @abc.abstractmethod
    def enable_burst(self, *args, **kwargs):
        ''' Turn burst ON '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def disable_burst(self, *args, **kwargs):
        ''' Turn burst OFF '''
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def BURST_MODES(self):
        raise NotImplementedError
    
    def check_burst_mode(self, mode):
        ''' Check that burst mode is available on the instrument '''
        if mode not in self.BURST_MODES:
            raise VisaError(
                f'{mode} is not a valid burst mode (options are {self.BURST_MODES})')

    @abc.abstractmethod
    def set_burst_mode(self, *args, **kwargs):
        ''' Set burst mode '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def get_burst_mode(self, *args, **kwargs):
        ''' Get burst mode '''
        raise NotImplementedError

    @abc.abstractmethod
    def set_burst_ncycles(self, *args, **kwargs):
        ''' Set number of cycles in burst '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_burst_ncycles(self, *args, **kwargs):
        ''' Get the number of cycles in the burst '''
        raise NotImplementedError

    @abc.abstractmethod
    def set_burst_internal_period(self, T):
        ''' Set burst repetition period (in s). '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_burst_internal_period(self):
        ''' Get burst repetition period (in s). '''
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def MAX_BURST_PERIOD(self):
        raise NotImplementedError

    def check_burst_duration(self, t, T):
        ''' Check the burst duration and return corresponding number of cycles '''
        if t < T:
            if not np.isclose(T - t, 0):
                raise VisaError(
                    f'burst duration ({si_format(t, 2)}s) shorter than stimulus periodicity ({si_format(T, 2)}s)')
        if t > self.MAX_BURST_PERIOD:
            raise VisaError(
                f'burst duration ({t:.2e} s) above max value ({self.MAX_BURST_PERIOD:.2e} s)')
        return int(np.round(t / T))

    @abc.abstractmethod
    def set_burst_duration(self, *args, **kwargs):
        ''' Set burst duration (in s). '''
        raise NotImplementedError

    def get_burst_duration(self, *args, **kwargs):
        ''' Get burst duration (in s). '''
        return self.get_burst_ncycles(*args, **kwargs) / self.get_carrier_freq(*args, **kwargs)

    @abc.abstractmethod
    def get_burst_phase(self, *args, **kwargs):
        ''' Get the burst phase. '''
        raise NotImplementedError

    def check_burst_phase(self, phi):
        unit = self.get_phase_unit()
        half_cycle = 180. if unit == 'DEG' else np.pi
        if phi not in (0., half_cycle):
            raise VisaError(f'burst phase ({phi} {unit}) is not a multiple of the half-cycle')

    @abc.abstractmethod
    def set_burst_phase(self, *args, **kwargs):
        ''' Set the burst phase. '''
        raise NotImplementedError

    @abc.abstractmethod
    def set_burst_gated_polarity(self, *args, **kwargs):
        ''' Set the gate polarity of the gated burst of the specified channel '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_burst_gated_polarity(self, *args, **kwargs):
        ''' Get the gate polarity of the gated burst of the specified channel '''
        raise NotImplementedError
    

    # --------------------- MODULATION ---------------------

    def check_modulation_mode(self, mode):
        ''' Check that modulation mode is available on the instrument '''
        if mode not in self.MOD_MODES:
            raise VisaError(
                f'{mode} is not a valid modulation mode (options are {self.MOD_MODES})')
    
    def check_modulation_source(self, source):
        ''' Check that modulation source is available on the instrument '''
        if source not in self.MOD_SOURCES:
            raise VisaError(
                f'{source} is not a valid modulation source (options are {self.MOD_SOURCES})')
    
    # --------------------- TRIGGER ---------------------

    @property
    @abc.abstractmethod
    def TRIGGER_SOURCES(self):
        raise NotImplementedError

    def check_trigger_source(self, source):
        ''' Check the trigger source '''
        if source not in self.TRIGGER_SOURCES:
            raise VisaError(
                f'{source} is not a valid trigger source (options are {self.TRIGGER_SOURCES})')

    @abc.abstractmethod
    def set_trigger_source(self, *args, **kwargs):
        ''' Select the trigger source. '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_trigger_source(self, *args, **kwargs):
        ''' Read the trigger source. '''
        raise NotImplementedError

    def trigger(self, verbose=True):
        super().trigger()
        if verbose:
            self.display_for('instrument triggered', duration=0.5)

    @abc.abstractmethod
    def wait_for_external_trigger(self, *args, **kwargs):
        ''' Wait for an external trigger '''
        raise NotImplementedError

    @abc.abstractmethod
    def wait_for_manual_trigger(self, *args, **kwargs):
        ''' Wait for a manual/programmatic trigger '''
        raise NotImplementedError

    # --------------------- TRIGGER OUTPUT ---------------------
    
    @abc.abstractmethod
    def enable_trigger_output(self):
        ''' Enable trigger output '''
        raise NotImplementedError

    @abc.abstractmethod
    def disable_trigger_output(self):
        ''' Disable trigger output '''
        raise NotImplementedError

    @abc.abstractmethod
    def set_trigger_output_slope(self, slope):
        ''' Set the trigger output slope type '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_trigger_output_slope(self):
        ''' Read the trigger output slope type. '''
        raise NotImplementedError

    def disconnect(self):
        self.unlock_front_panel()
        super().disconnect()