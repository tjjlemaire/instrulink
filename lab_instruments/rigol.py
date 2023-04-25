# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-08 08:37:26
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-04-25 13:27:41

import time

from lab_instruments.constants import MV_TO_V

from .waveform_generator import *
from .logger import logger
from .si_utils import si_format


class RigolDG1022Z(WaveformGenerator):

    USB_ID = 'DG1ZA\d+'
    NO_ERROR_CODE = '0,"No error"'
    ANGLE_UNITS = ('DEG')
    MAX_LEN_TEXT = 40
    WAVEFORM_TYPES = ('SIN', 'SQU', 'RAMP', 'PULS', 'NOIS', 'DC', 'ARB')
    FMAX = 25e6  # Hz
    VMAX = 20.0  # Vpp
    BURST_MODES = ('TRIG', 'INF', 'GAT')
    BURST_IDLE_LEVELS = ('FPT', 'TOP', 'CENTER', 'BOTTOM')
    PULSE_HOLDS = ('WIDT', 'DUTY')
    MAX_BURST_PERIOD = 500. # s
    TRIGGER_SOURCES = ('INT', 'EXT', 'MAN')
    CHANNELS = (1, 2)
    PREFIX = ':'
    
    def beep(self):
        ''' Issue a single beep immediately. '''
        self.write('SYST:BEEP:IMM')
    
    # --------------------- UNITS ---------------------
    
    def set_angle_unit(self, unit):
        self.check_angle_unit(unit)

    def get_angle_unit(self):
        return self.ANGLE_UNITS[0]
    
    def set_voltage_unit(self, ich, unit):
        self.check_channel_index(ich)
        self.check_voltage_unit(unit)
        self.write(f'SOUR{ich}:VOLT:UNIT {unit}')

    def get_voltage_unit(self, ich):
        self.check_channel_index(ich)
        return self.query(f'SOUR{ich}:VOLT:UNIT?')

    # --------------------- OUTPUT ---------------------

    def enable_output_channel(self, ich):
        ''' Turn channel output ON '''
        self.check_channel_index(ich)
        self.write(f'OUTP{ich} ON')

    def disable_output_channel(self, ich):
        ''' Turn channel output OFF '''
        self.check_channel_index(ich)
        self.write(f'OUTP{ich} OFF')   

    def enable_output(self):
        for ich in self.CHANNELS:
            self.enable_output_channel(ich)

    def disable_output(self):
        for ich in self.CHANNELS:
            self.disable_output_channel(ich)
    
    def get_output_state(self, *ich):
        ''' Get the output state for a specific channel '''
        if len(ich) == 0:
            ich = self.CHANNELS
        if len(ich) > 1:
            return [self.get_output_state(x) for x in ich]
        ich = ich[0]
        self.check_channel_index(ich)
        return self.query(f'OUTP{ich}?')

    def test_output(self):
        ''' Test output enabling/disabling sequence '''
        self.enable_output_channel(1)
        time.sleep(1)
        self.enable_output_channel(2)
        time.sleep(1)
        self.disable_output_channel(2)
        time.sleep(1)
        self.disable_output_channel(1)
        time.sleep(1)
        self.enable_output()
        time.sleep(1)
        self.disable_output()
    
    # --------------------- BASIC WAVEFORM ---------------------

    def apply_waveform(self, wtype, ich, freq, amp, offset=0, phase=0):
        ''' Apply a waveform with specific parameters.

            :param wtype: waveform function
            :param ich: channel number
            :param freq: waveform frequency (Hz)
            :param amp: waveform amplitude (default: Vpp)
            :param offset: voltage offset (V)
            :param phase: waveform phase (degrees)
        '''
        self.check_channel_index(ich)
        self.check_waveform_type(wtype)
        self.write(f'SOUR{ich}:APPL:{wtype} {freq}, {amp}, {offset}, {phase}')
    
    def apply_arbitrary(self, ich, freq):
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:APPL:ARB {freq}')

    def apply_noise(self, ich, amp, offset):
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:APPL:NOIS {amp}, {offset}')

    def set_waveform_type(self, ich, wtype):
        self.check_channel_index(ich)
        self.check_waveform_type(wtype)
        self.write(f'FUNC {wtype}')

    def get_waveform_type(self):
        return self.query('FUNC?')

    def set_waveform_freq(self, ich, freq):
        self.check_channel_index(ich)
        self.check_freq(freq)
        self.write(f'SOUR{ich}:FREQ:FIX {freq}')

    def get_waveform_freq(self, ich):
        self.check_channel_index(ich)
        return float(self.query(f'SOUR{ich}:FREQ:FIX?'))
    
    def set_waveform_amp(self, ich, amp):
        self.check_channel_index(ich)
        self.check_amp(amp)
        self.write(f'SOUR{ich}:VOLT:LEV:IMM:AMPL {amp}')

    def get_waveform_amp(self, ich):
        self.check_channel_index(ich)
        return float(self.query(f'SOUR{ich}:VOLT:LEV:IMM:AMPL?'))

    def set_waveform_offset(self, ich, offset):
        self.check_channel_index(ich)
        self.check_offset(offset)
        self.write(f'SOUR{ich}:VOLT:LEV:IMM:OFFS {offset}')

    def get_waveform_offset(self, ich):
        self.check_channel_index(ich)
        return float(self.query(f'SOUR{ich}:VOLT:LEV:IMM:OFFS?'))
    
    def set_square_duty_cycle(self, ich, DC):
        self.check_channel_index(ich)
        self.check_duty_cycle(DC)
        self.write(f'SOUR{ich}:FUNC:SQU:DCYC {DC}')

    def get_square_duty_cycle(self, ich):
        self.check_channel_index(ich)
        return float(self.query(f'SOUR{ich}:FUNC:SQU:DCYC?'))
    
    def set_pulse_hold(self, ich, phold):
        ''' 
        Set the pulse mode highlight item of the specified channel
        '''
        if phold not in self.PULSE_HOLDS:
            raise VisaError(
                f'{phold} not a valid pulse hold mode. Candidates are {self.PULSE_HOLDS}')
        self.write(f'SOUR{ich}:PULS:HOLD {phold}')
    
    def get_pulse_hold(self, ich):
        ''' 
        Get the pulse mode highlight item of the specified channel
        '''
        return self.query(f'SOUR{ich}:PULS:HOLD?')
    
    def set_pulse_duty_cycle(self, ich, DC):
        self.check_channel_index(ich)
        self.check_duty_cycle(DC)
        self.set_pulse_hold(ich, 'DUTY')
        self.write(f'SOUR{ich}:FUNC:PULS:DCYC {DC}')

    def get_pulse_duty_cycle(self, ich):
        self.check_channel_index(ich)
        return float(self.query(f'SOUR{ich}:FUNC:PULS:DCYC?'))

    def set_pulse_width(self, ich, width):
        self.check_channel_index(ich)
        self.set_pulse_hold(ich, 'WIDT')
        self.write(f'SOUR{ich}:FUNC:PULS:WIDT {width}')

    def get_pulse_width(self, ich):
        self.check_channel_index(ich)
        return float(self.query(f'SOUR{ich}:FUNC:PULS:WIDT?'))
    
    # --------------------- ARBITRARY WAVEFORM ---------------------

    def set_arbitrary_waveform(self, ich, y, precision=5):
        ''' Set an arbitrary waveform '''
        y = np.asarray(y)
        ystr = ','.join([f'{yy:.2f}' for yy in self.normalize(y)])
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:DATA VOLATILE, {ystr}')

    # --------------------- BURST ---------------------

    def enable_burst(self, ich):
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:BURS ON')
    
    def disable_burst(self, ich):
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:BURS OFF')

    def set_burst_mode(self, ich, mode):
        self.check_channel_index(ich)
        self.check_burst_mode(mode)
        self.write(f'SOUR{ich}:BURS:MODE {mode}')
    
    def get_burst_mode(self, ich):
        self.check_channel_index(ich)
        return self.query(f'SOUR{ich}:BURS:MODE?')

    def set_burst_ncycles(self, ich, n):
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:BURS:NCYC {n}')

    def get_burst_ncycles(self, ich):
        self.check_channel_index(ich)
        return int(self.query(f'SOUR{ich}:BURS:NCYC?'))

    def set_burst_internal_period(self, ich, T):
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:BURS:INT:PER {T}')

    def get_burst_internal_period(self, ich):
        self.check_channel_index(ich)
        return float(self.query('SOUR{ich}:BURS:INT:PER?'))

    def set_burst_duration(self, ich, t):
        T = 1 / self.get_waveform_freq(ich)
        ncycles = self.check_burst_duration(t, T)
        self.set_burst_ncycles(ich, ncycles)
    
    def set_burst_phase(self, ich, phi):
        self.check_channel_index(ich)
        self.check_burst_phase(phi)
        self.write(f'SOUR{ich}:BURS:PHAS {phi}')

    def get_burst_phase(self, ich):
        self.check_channel_index(ich)
        return float(self.query(f'SOUR{ich}:BURS:PHAS?'))
    
    def set_burst_gated_polarity(self, ich, pol):
        self.check_channel_index(ich)
        self.check_polarity(pol)
        self.write(f'SOUR{ich}:BURS:GATE:POL {pol}')

    def get_burst_gated_polarity(self, ich):
        self.check_channel_index(ich)
        return self.query(f'SOUR{ich}:BURS:GATE:POL?')

    def set_burst_delay(self, ich, t):
        ''' Set the burst delay of the N-cycle / infinite burst of the specified channel.'''
        self.write(f'SOUR{ich}:BURS:TDEL {t}')
    
    def get_burst_delay(self, ich):
        ''' Get the burst delay of the N-cycle / infinite burst of the specified channel.'''
        return float(self.query(f'SOUR{ich}:BURS:TDEL?'))
    
    def set_burst_idle_level(self, ich, lvl):
        ''' Set the idle level position of the burst mode for the specified channel '''
        self.check_channel_index(ich)
        if lvl not in self.BURST_IDLE_LEVELS:
            raise VisaError(
                f'{lvl} is not a valid idle level (options are {self.BURST_IDLE_LEVELS})')
        self.write(f'SOUR{ich}:BURS:IDLE {lvl}')
    
    def get_burst_idle_level(self, ich):
        self.check_channel_index(ich)
        return self.query(f'SOUR{ich}:BURS:IDLE?')

    # --------------------- TRIGGER ---------------------

    def set_trigger_source(self, ich, source):
        self.check_channel_index(ich)
        self.check_trigger_source(source)
        self.write(f'SOUR{ich}:BURS:TRIG:SOUR {source}')

    def get_trigger_source(self, ich):
        self.check_channel_index(ich)
        return self.query(f'SOUR{ich}:BURS:TRIG:SOUR?')

    def set_trigger_slope(self, ich, slope):
        self.check_channel_index(ich)
        self.check_trigger_slope(slope)
        self.write(f'SOUR{ich}:BURS:TRIG:SLOP {slope}')

    def get_trigger_slope(self, ich):
        self.check_channel_index(ich)
        return self.query(f'SOUR{ich}:BURS:TRIG:SLOP?')

    def single_pulse(self, ich):
        self.check_channel_index(ich)
        logger.info(f'sending single pulse on channel {ich}...')
        self.set_trigger_source(ich, 'MAN')
        self.enable_output_channel(ich)
        self.trigger_channel(ich)
        self.wait()
    
    def wait_for_external_trigger(self, ich):
        self.check_channel_index(ich)
        logger.info(f'waiting for external trigger on channel {ich}...')
        self.set_trigger_source('EXT')
        self.enable_output()

    # --------------------- TRIGGER OUTPUT ---------------------
    
    def enable_trigger_output(self, ich):
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:BURS:TRIG:TRIGO POS')

    def disable_trigger_output(self, ich):
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:BURS:TRIG:TRIGO OFF')
     
    def set_trigger_output_slope(self, ich, slope):
        self.check_channel_index(ich)
        self.check_slope(slope)
        self.write(f'SOUR{ich}:BURS:TRIG:TRIGO {slope}')

    def get_trigger_output_slope(self, ich):
        self.check_channel_index(ich)
        return self.query(f'SOUR{ich}:BURS:TRIGO:SLOP?')

    def trigger_channel(self, ich):
        ''' Trigger specific channel '''
        self.check_channel_index(ich)
        source = self.get_trigger_source(ich)
        self.set_trigger_source(ich, 'MAN')
        self.write(f'SOUR{ich}:BURS:TRIG:IMM')
        self.display_for(f'triggered channel {ich} instrument triggered', duration=0.5) 
        if source != 'MAN':
            self.set_trigger_source(1, source)

    def start_trigger_loop(self, ich):
        ''' Start a trigger loop with a specific channel '''
        self.set_trigger_source(ich, 'INT')
    
    def set_gating_pulse_train(self, ich, PRF, Vpp, T, tburst, trig_source='EXT'):
        '''
        Set a gating pulse train on a specific channel
        
        :param ich: channel index
        :param PRF: pulse repetition frequency (Hz)
        :param Vpp: pulse amplitude (V)
        :param T: burst repetition period (s)
        :param tburst: burst duration (s)
        :param trig_source: trigger source (default: external)
        '''
        # Apply pulse with specific frequency, amplitude and offset
        self.apply_pulse(ich, PRF, Vpp, offset=Vpp / 2.)
        # Set nominal pulse width
        self.set_pulse_width(ich, self.TTL_PWIDTH)
        # Set pulse idle level to "bottom"
        self.set_burst_idle_level(ich, 'BOTTOM')
        # Set channel trigger source to external (to avoid erroneous outputs upon setting)
        self.set_trigger_source(ich, 'EXT')
        # Set burst repetition period
        self.set_burst_internal_period(ich, T)  # s
        # Set burst duration
        self.set_burst_duration(ich, tburst)  # s
        # Enable burst mode on channel
        self.enable_burst(ich)
        # Set channel trigger source
        self.set_trigger_source(ich, trig_source)

    def set_gated_sine_burst(self, Fdrive, Vpp, tstim, PRF, DC, mod_Vpp=None, mod_T=2.,
                             ich_mod=1, ich_sine=2, mod_trig_source='EXT'):
        '''
        Set sine burst on channel 2 gated by channel 1 (used for pulsed US stimulus)
        
        :param Fdrive: driving frequency (Hz)
        :param Vpp: waveform amplitude (Vpp)
        :param tstim: total stimulus duration (s)
        :param PRF: pulse repetition frequency (Hz)
        :param DC: duty cycle (%)
        :param mod_Vpp: amplitude of the modulating square pulse (default = 5 Vpp)
        :param mod_T: repetition period of the modulating square pulse (default = 2s)
        :param ich_mod: index of the modulating signal channel
        :param ich_sine: index of the carrier signal channel
        :param mod_trig_source: trigger source of the modulating channel (default: external)
        '''
        if mod_Vpp is None:
            mod_Vpp = self.TTL_PAMP / MV_TO_V
        if ich_mod == ich_sine:
            raise VisaError('gating and signal channels cannot be identical')
        # Disable all outputs
        self.disable_output()
        # Set gating channel parameters
        self.set_gating_pulse_train(
            ich_mod, PRF, mod_Vpp, mod_T, tstim, trig_source=mod_trig_source)

        # Set sinewave channel parameters
        self.apply_sine(ich_sine, Fdrive, Vpp)
        self.set_trigger_source(ich_sine, 'EXT')
        self.set_burst_duration(ich_sine, DC / (100 * PRF))  # s
        self.enable_burst(ich_sine)
        self.set_trigger_source(ich_sine, 'EXT')

        # Enable all outputs (only if amplitude is > 0)
        if Vpp > 0.:
            self.enable_output()
    
    def set_looping_sine_burst(self, ich, Fdrive, Vpp=.1, ncycles=200, BRF=100., ich_trig=None):
        '''
        Set an internally looping sine burst on a specific channel
        
        :param ich: channel index (1 or 2)
        :param Fdrive: driving frequency (Hz)
        :param Vpp: waveform amplitude (Vpp)
        :param ncycles: number of cycles per burst
        :param BRF: Burst repetition frequency (Hz)
        :param ich_trig (optional): triggering channel index
        '''
        # Log process
        params_str = ', '.join([
            f'{si_format(Fdrive, 3)}Hz',
            f'{si_format(Vpp, 3)}Vpp', 
            f'{ncycles} cycles'
        ])
        s = f'setting ({params_str}) sine wave looping at {BRF:.1f} Hz on channel {ich}'
        if ich_trig is not None:
            s = f'{s}, triggered by channel {ich_trig}'
        logger.info(s)
        if ich_trig is not None:
            tburst = ncycles / Fdrive  # nominal burst duration (s)
            self.set_gated_sine_burst(
                Fdrive, Vpp, tburst, 1. / tburst, BRF, mod_T=1. / BRF,
                ich_mod=ich_trig, ich_sine=ich)
            self.start_trigger_loop(ich_trig)
            self.enable_output()
        else:
            # Disable all outputs
            self.disable_output()
            # Set sine wave channel parameters
            self.apply_sine(ich, Fdrive, Vpp)
            self.set_burst_internal_period(ich, 1 / BRF)  # s
            self.set_burst_ncycles(ich, ncycles)
            self.enable_burst(ich)
            self.start_trigger_loop(ich)
            self.enable_output_channel(ich)
