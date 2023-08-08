# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-08 08:37:26
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-08-08 15:17:25

import time
import re
from tqdm import tqdm
import numpy as np

from .waveform_generator import *
from .logger import logger
from .si_utils import si_format
from .constants import TTL_PWIDTH, TTL_PAMP, MV_TO_V
from .utils import is_within
from instrulink.wf_utils import *


class RigolDG1022Z(WaveformGenerator):

    # Miscellaneous
    USB_ID = 'DG1ZA\d+'  # USB identifier
    NO_ERROR_CODE = '0,"No error"'  # error code returned when no error
    ANGLE_UNITS = ('DEG')
    MAX_LEN_TEXT = 40
    WAVEFORM_TYPES = ('SIN', 'SQU', 'RAMP', 'PULS', 'NOIS', 'DC', 'USER')
    FMAX = 25e6  # max frequency (Hz)
    VMAX = 20.0  # max voltage (Vpp)
    ANTIPHASE = 180  # degrees
    CHANNELS = (1, 2)
    PREFIX = ':'
    # TIMEOUT_SECONDS = 20.  # long timeout to allow slow commands (e.g. waveform loading)

    # Coupling
    CPL_PATTERN = '^FREQ:(ON|OFF),PHASE:(ON|OFF),AMPL:(ON|OFF)$'
    CPL_MODES = ('OFFS', 'RAT')  # coupling modes
    CPL_AMP_RATIO_BOUNDS = (1e-3, 1e3)  # bounds for amplitude coupling ratio
    CPL_AMP_DEV_BOUNDS = (-19.998, 19.998)  # bounds for amplitude coupling deviation
    CPL_FREQ_RATIO_BOUNDS = (1e-6, 1e6)  # bounds for frequency coupling ratio
    CPL_FREQ_DEV_BOUNDS = (-0.99 * FMAX, 0.99 * FMAX)  # bounds for frequency coupling deviation
    CPL_PHASE_RATIO_BOUNDS = (1e-2, 1e2)  # bounds for phase coupling ratio
    CPL_PHASE_DEV_BOUNDS = (-360, 360)  # bounds for phase coupling deviation

    # Bursting
    BURST_MODES = ('TRIG', 'INF', 'GAT')
    BURST_IDLE_LEVELS = ('FPT', 'TOP', 'CENTER', 'BOTTOM')
    PULSE_HOLDS = ('WIDT', 'DUTY')
    MAX_BURST_PERIOD = 500. # s

    # Modulation
    MOD_MODES = ('AM', 'FM', 'PM', 'ASK', 'FSK', 'PSK', 'PWM')
    MOD_VOLT_RANGE = (-5, 5)  # voltage range regulating modulation (V)
    MOD_VOLT_MARGIN = 0.05  # margin on each side to ensure full range amplitude modulation (V)
    AM_DEPTH_RANGE = (0, 120)  # AM depth range (%)
    AM_FREQ_RANGE = (2e-3, 1e6)  # AM frequency range (Hz)
    MOD_SOURCES = ('INT', 'EXT')  # modulation sources

    # Trigger
    TRIGGER_SOURCES = ('INT', 'EXT', 'MAN')

    # Arbitrary waveform
    ARB_OUTPUT_MODES = ('FREQ', 'SRATE')
    ARB_SRATE_BOUNDS = (1e-6, 60e6)  # bounds for arbitrary waveform sample rate (Hz)
    ARB_WF_NPTS_BOUNDS = (8, 16384)  # bounds for arbitrary waveform number of points
    ARB_WF_MAXNPTS_PER_PACKET = 8192  # max number of points per packet for arbitrary waveform upload
    ARB_WF_DAC_RANGE = (0, 16383)  # integer range for arbitrary waveform DAC values
    ARB_WF_FLOAT_RANGE = (-1, 1)  # floating point range for arbitrary waveform values
    WAF_PATTERN = '^(ARB)(10?|[2-9])$'

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
    
    # --------------------- SYNC ---------------------
    
    def enable_output_sync(self, ich):
        ''' Enable sync signal of specific channel on rear panel connector '''
        self.check_channel_index(ich)
        self.write(f'OUTP{ich}:SYNC ON')
    
    def disable_output_sync(self, ich):
        ''' Disable sync signal of specific channel on rear panel connector '''
        self.check_channel_index(ich)
        self.write(f'OUTP{ich}:SYNC OFF')
    
    def is_output_sync_on(self, ich):
        ''' Query whether sync signal is enabled for a specific channel '''
        self.check_channel_index(ich)
        out = self.query(f'OUTP{ich}:SYNC?')
        return out == 'ON'

    def set_output_sync_delay(self, ich, delay):
        ''' 
        Set sync signal delay for a specific channel 

        :param ich: channel index
        :param delay: delay (s)
        '''
        self.check_channel_index(ich)
        T = 1 / self.get_waveform_freq(ich)
        if not is_within(delay, (0, T)):
            raise VisaError(f'invalid delay: {delay} (must be within [0, 1/f = {si_format(T, 2)}s])')
        self.write(f'OUTP{ich}:SYNC:DEL {delay}')
    
    def get_output_sync_delay(self, ich):
        ''' 
        Get sync signal delay for a specific channel 

        :param ich: channel index
        :return: delay (s)
        '''
        self.check_channel_index(ich)
        return float(self.query(f'OUTP{ich}:SYNC:DEL?'))
    
    def set_output_sync_polarity(self, ich, pol):
        ''' 
        Set sync signal polarity for a specific channel 

        :param ich: channel index
        :param pol: polarity ("POS" or "NEG")
        '''
        self.check_channel_index(ich)
        if pol not in self.SLOPES:
            raise VisaError(f'invalid polarity: "{pol}" (must be in {self.SLOPES})')
        self.write(f'OUTP{ich}:SYNC:POL {pol}')

    def get_output_sync_polarity(self, ich):
        ''' 
        Get sync signal polarity for a specific channel 

        :param ich: channel index
        :return: polarity ("POS" or "NEG")
        '''
        self.check_channel_index(ich)
        return self.query(f'OUTP{ich}:SYNC:POL?')

    # --------------------- COUPLING ---------------------

    def enable_all_coupling(self):
        ''' 
        Enable frequency, phase and amplitude coupling across channels.
        '''
        self.write('COUP ON')
    
    def disable_all_coupling(self):
        ''' 
        Disable frequency, phase and amplitude coupling across channels.
        '''
        self.write('COUP OFF')
    
    def is_coupling_on(self):
        ''' 
        Query whether frequency, phase and amplitude coupling across channels are enabled.

        :return: dictionary of coupling states
        '''
        out = self.query('COUP?')
        mo = re.match(self.CPL_PATTERN, out)
        if mo is None:
            raise VisaError(f'invalid coupling query response: "{out}"')
        cplstates = dict(zip(('FREQ', 'PHASE', 'AMPL'), mo.groups()))
        return {k: v == 'ON' for k, v in cplstates.items()}

    # --------------------- AMPLITUDE COUPLING ---------------------

    def enable_amplitude_coupling(self):
        ''' 
        Enable amplitude coupling across channels.
        '''
        self.write('COUP:AMPL ON')
    
    def disable_amplitude_coupling(self):
        ''' 
        Disable amplitude coupling across channels.
        '''
        self.write('COUP:AMPL OFF')
    
    def is_amplitude_coupling_on(self):
        ''' 
        Query whether amplitude coupling across channels is enabled.

        :return: boolean
        '''
        return self.query('COUP:AMPL?') == 'ON'

    def set_amplitude_coupling_mode(self, mode):
        ''' 
        Set amplitude coupling mode across channels.

        :param mode: amplitude coupling ("OFFS" for deviation or "RAT" for ratio)
        '''
        if mode not in self.CPL_MODES:
            raise VisaError(f'invalid amplitude coupling mode: "{mode}" (must be one of {self.CPL_MODES})')
        self.write(f'COUP:AMPL:MODE {mode}')
    
    def get_amplitude_coupling_mode(self):
        ''' 
        Get amplitude coupling mode across channels.

        :return: amplitude coupling mode
        '''
        return self.query('COUP:AMPL:MODE?')

    def set_amplitude_coupling_ratio(self, ratio):
        ''' 
        Set amplitude coupling ratio across channels.

        :param ratio: amplitude coupling ratio
        '''
        if not is_within(ratio, self.CPL_AMP_RATIO_BOUNDS):
            raise VisaError(f'invalid amplitude coupling ratio: "{ratio}" (must be within {self.CPL_AMP_RATIO_BOUNDS})')
        self.write(f'COUP:AMPL:RAT {ratio}')
    
    def get_amplitude_coupling_ratio(self):
        ''' 
        Get amplitude coupling ratio across channels.

        :return: amplitude coupling ratio
        '''
        return float(self.query('COUP:AMPL:RAT?'))

    def set_amplitude_coupling_deviation(self, deviation):
        ''' 
        Set amplitude coupling deviation across channels.

        :param deviation: amplitude coupling deviation
        '''
        if not is_within(deviation, self.CPL_AMP_DEV_BOUNDS):
            raise VisaError(f'invalid amplitude coupling deviation: "{deviation}" (must be within {self.CPL_AMP_DEV_BOUNDS})')
        self.write(f'COUP:AMPL:DEV {deviation}')
    
    def get_amplitude_coupling_deviation(self):
        ''' 
        Get amplitude coupling deviation across channels.

        :return: amplitude coupling deviation
        '''
        return float(self.query('COUP:AMPL:DEV?'))
    
    # --------------------- FREQUENCY COUPLING ---------------------

    def enable_frequency_coupling(self):
        ''' 
        Enable frequency coupling across channels.
        '''
        self.write('COUP:FREQ ON')

    def disable_frequency_coupling(self):
        ''' 
        Disable frequency coupling across channels.
        '''
        self.write('COUP:FREQ OFF')

    def is_frequency_coupling_on(self):
        '''
        Query whether frequency coupling across channels is enabled.
        '''
        return self.query('COUP:FREQ?') == 'ON'

    def set_frequency_coupling_mode(self, mode):
        ''' 
        Set frequency coupling mode across channels.

        :param mode: frequency coupling ("OFFS" for deviation or "RAT" for ratio)
        '''
        if mode not in self.CPL_MODES:
            raise VisaError(f'invalid frequency coupling mode: "{mode}" (must be one of {self.CPL_MODES})')
        self.write(f'COUP:FREQ:MODE {mode}')
    
    def get_frequency_coupling_mode(self):
        ''' 
        Get frequency coupling mode across channels.

        :return: frequency coupling mode
        '''
        return self.query('COUP:FREQ:MODE?')

    def set_frequency_coupling_ratio(self, ratio):
        ''' 
        Set frequency coupling ratio across channels.

        :param ratio: frequency coupling ratio
        '''
        if not is_within(ratio, self.CPL_FREQ_RATIO_BOUNDS):
            raise VisaError(f'invalid frequency coupling ratio: "{ratio}" (must be within {self.CPL_FREQ_RATIO_BOUNDS})')
        self.write(f'COUP:FREQ:RAT {ratio}')
    
    def get_frequency_coupling_ratio(self):
        ''' 
        Get frequency coupling ratio across channels.

        :return: frequency coupling ratio
        '''
        return float(self.query('COUP:FREQ:RAT?'))

    def set_frequency_coupling_deviation(self, deviation):
        ''' 
        Set frequency coupling deviation across channels.

        :param deviation: frequency coupling deviation
        '''
        if not is_within(deviation, self.CPL_FREQ_DEV_BOUNDS):
            raise VisaError(f'invalid frequency coupling deviation: "{deviation}" (must be within {self.CPL_FREQ_DEV_BOUNDS})')
        self.write(f'COUP:FREQ:DEV {deviation}')

    def get_frequency_coupling_deviation(self):
        ''' 
        Get frequency coupling deviation across channels.

        :return: frequency coupling deviation
        '''
        return float(self.query('COUP:FREQ:DEV?'))

    # --------------------- PHASE COUPLING ---------------------

    def enable_phase_coupling(self):
        ''' 
        Enable phase coupling across channels.
        '''
        self.write('COUP:PHAS ON')
    
    def disable_phase_coupling(self):
        ''' 
        Disable phase coupling across channels.
        '''
        self.write('COUP:PHAS OFF')
    
    def is_phase_coupling_on(self):
        '''
        Query whether phase coupling across channels is enabled.
        '''
        return self.query('COUP:PHAS?') == 'ON'

    def set_phase_coupling_mode(self, mode):
        ''' 
        Set phase coupling mode across channels.

        :param mode: phase coupling ("OFFS" for deviation or "RAT" for ratio)
        '''
        if mode not in self.CPL_MODES:
            raise VisaError(f'invalid phase coupling mode: "{mode}" (must be one of {self.CPL_MODES})')
        self.write(f'COUP:PHAS:MODE {mode}')
    
    def get_phase_coupling_mode(self):
        ''' 
        Get phase coupling mode across channels.

        :return: phase coupling mode
        '''
        return self.query('COUP:PHAS:MODE?')
    
    def set_phase_coupling_ratio(self, ratio):
        ''' 
        Set phase coupling ratio across channels.

        :param ratio: phase coupling ratio
        '''
        if not is_within(ratio, self.CPL_PHASE_RATIO_BOUNDS):
            raise VisaError(f'invalid phase coupling ratio: "{ratio}" (must be within {self.CPL_PHASE_RATIO_BOUNDS})')
        self.write(f'COUP:PHAS:RAT {ratio}')
    
    def get_phase_coupling_ratio(self):
        ''' 
        Get phase coupling ratio across channels.

        :return: phase coupling ratio
        '''
        return float(self.query('COUP:PHAS:RAT?'))
    
    def set_phase_coupling_deviation(self, deviation):
        ''' 
        Set phase coupling deviation across channels.

        :param deviation: phase coupling deviation
        '''
        if not is_within(deviation, self.CPL_PHASE_DEV_BOUNDS):
            raise VisaError(f'invalid phase coupling deviation: "{deviation}" (must be within {self.CPL_PHASE_DEV_BOUNDS})')
        self.write(f'COUP:PHAS:DEV {deviation}')
    
    def get_phase_coupling_deviation(self):
        ''' 
        Get phase coupling deviation across channels.

        :return: phase coupling deviation
        '''
        return float(self.query('COUP:PHAS:DEV?'))

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
    
    def apply_arbitrary(self, ich, sr):
        ''' 
        Apply an arbitrary waveform with specific sample rate. This function automatically
        sets the waveform type to "USER" and the output mode to "SRATE".

        :param ich: channel number
        :param sr: sample rate (samples/s)
        '''
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:APPL:ARB {sr}')

    def apply_noise(self, ich, amp, offset):
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:APPL:NOIS {amp}, {offset}')

    def set_waveform_type(self, ich, wtype):
        self.check_channel_index(ich)
        self.check_waveform_type(wtype)
        self.write(f'SOUR{ich}:FUNC {wtype}')

    def get_waveform_type(self, ich):
        self.check_channel_index(ich)
        return self.query(f'SOUR{ich}:FUNC?')

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
    
    def check_offset(self, offset, ich):
        if np.absolute(offset) > self.VMAX - self.get_waveform_amp(ich) / 2:
            raise VisaError(f'|VPP/2| + |Voffset| exceeds {self.VMAX} V')

    def set_waveform_offset(self, ich, offset):
        self.check_channel_index(ich)
        self.check_offset(offset, ich)
        self.write(f'SOUR{ich}:VOLT:LEV:IMM:OFFS {offset}')

    def get_waveform_offset(self, ich):
        self.check_channel_index(ich)
        return float(self.query(f'SOUR{ich}:VOLT:LEV:IMM:OFFS?'))
    
    def set_waveform_phase(self, ich, phase):
        self.check_channel_index(ich)
        self.check_phase(phase)
        self.write(f'SOUR{ich}:PHAS {phase}')
    
    def get_waveform_phase(self, ich):
        self.check_channel_index(ich)
        return float(self.query(f'SOUR{ich}:PHAS?'))  # degrees

    def invert_waveform_phase(self, ich):
        ''' Invert the phase of the waveform of the specified channel. '''
        self.set_waveform_phase(ich, self.ANTIPHASE)
    
    def is_waveform_phase_inverted(self, ich):
        ''' Query whether the phase of the waveform of the specified channel is inverted. '''
        return self.get_waveform_phase(ich) == self.ANTIPHASE
    
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

    def get_arbitrary_output_mode(self, ich):
        '''
        Get the output mode of the arbitrary waveform of the specified channel.

        :param ich: channel index
        :return: output mode (frequency or sample rate)
        '''
        # Check channel index
        self.check_channel_index(ich)
        # Query and return output mode
        return self.query(f'SOUR{ich}:FUNC:ARB:MODE?')
    
    def set_arbitrary_output_mode(self, ich, mode):
        '''
        Set the output mode of the arbitrary waveform of the specified channel.

        :param ich: channel index
        :param mode: output mode ("FREQ" for frequency or "SRATE" for sample rate)
        '''
        # Check channel index
        self.check_channel_index(ich)
        # Check that mode is valid
        if mode not in self.ARB_OUTPUT_MODES:
            raise VisaError(f'invalid output mode: {mode} (must be one of {self.ARB_OUTPUT_MODES})')
        # Set output mode on specified channel
        return self.write(f'SOUR{ich}:FUNC:ARB:MODE {mode}')
    
    def get_arbitrary_sample_rate(self, ich):
        '''
        Get the sample rate of the arbitrary waveform of the specified channel.

        :param ich: channel index
        :return: sample rate (Hz, or samples/s)
        '''
        # Check channel index
        self.check_channel_index(ich)
        # Query sample rate
        out = self.query(f'SOUR{ich}:FUNC:ARB:SRAT?')
        # Return as float
        return float(out)
    
    def set_arbitrary_sample_rate(self, ich, sr):
        '''
        Set the sample rate of the arbitrary waveform of the specified channel.

        :param ich: channel index
        :param sr: sample rate (Hz, or samples/s)
        '''
        # Check channel index
        self.check_channel_index(ich)
        # Check that sample rate is valid
        if not is_within(sr, self.ARB_SRATE_BOUNDS):
            raise VisaError(f'invalid sample rate: {sr} (must be within {self.ARB_SRATE_BOUNDS}')
        # Set sample rate on specified channel
        return self.write(f'SOUR{ich}:FUNC:ARB:SRAT {sr}')

    def get_waveform_catalog(self, ich=None):
        '''
        Query the arbitrary waveform data files currently stored in non-volatile memory.
        
        :param ich: channel index (optional)
        :return: list of stored waveform files
        '''
        # Get list of available waveforms as string
        query_str = 'DATA:CAT?'
        if ich is not None:
            self.check_channel_index(ich)
            query_str = f'SOUR{ich}:{query_str}'
        wfs = self.query(query_str)
        # Remove quotes and split string into list
        wfs = wfs.replace('"', '').split(',')
        # Remove empty strings
        wfs = [x for x in wfs if x != '']
        # Return list of waveforms
        return wfs

    def get_waveform_npoints(self, ich):
        '''
        Query the number of initial points of the waveform editing in
        volatile memory of specific channel.

        :param ich: channel index
        :return: number of initial points of the waveform editing
        '''
        # Check channel index
        self.check_channel_index(ich)
        # Query number of points
        n = self.query(f'SOUR{ich}:DATA:POIN? VOLATILE')
        # Return as integer
        return int(n)
    
    def set_waveform_npoints(self, ich, n):
        '''
        Set the number of initial points of the waveform editing in
        volatile memory of specific channel.

        :param ich: channel index
        :return: number of initial points of the waveform editing
        '''
        # Check channel index
        self.check_channel_index(ich)
        # Check that number of points is valid
        if not is_within(n, self.ARB_WF_NPTS_BOUNDS):
            raise VisaError(f'invalid number of points: {n} (must be within {self.ARB_WF_NPTS_BOUNDS})')
        # Set number of points for waveform editing
        self.write(f'SOUR{ich}:DATA:POIN VOLATILE,{n}')
        # Check that number of points was set correctly
        if self.get_waveform_npoints(ich) != n:
            raise VisaError(f'failed to set number of points to {n}')
    
    def write_binary_values(self, cmd, values, **kwargs):
        ''' Write binary values to instrument. '''
        logger.debug(f'{cmd} {values.size}')
        self.instrument_handle.write_binary_values(
            f'{self.PREFIX}{cmd}', values, **kwargs)

    def upload_arbitrary_waveform(self, ich, y, dtype='dac16', precision=2,
                                  adapt_npoints=True, activate=False):
        ''' 
        Upload an arbitrary waveform into volatile memory of a specific channel
        
        :param ich: channel index
        :param y: waveform vector
        :param dtype: data type used to upload waveform vector (default: "dac16")
            - "float": floating point values between -1 and 1
            - "dac": decimal DAC values between 0 and 16383
            - "dac16": 16-bits binary DAC values between 0 and 16383
        :param precision: number of decimal digits to use for each sample (default: 2, only used with "float" data type)
        :param adapt_npoints: whether to adapt the waveform vector to match the reference number of points of instrument waveforms
        :param activate: whether to set waveform type to arbitrary after upload (default: False)
        '''
        # Check channel index
        self.check_channel_index(ich)

        # Cast waveform vector to numpy array, and check waveform size
        y = np.asarray(y)
        
        # If specified, interpolate waveform vector to match the reference number
        # of points of instrument waveforms
        if adapt_npoints and y.size != self.ARB_WF_MAXNPTS_PER_PACKET:
            tref = np.arange(y.size)
            ttarget = np.linspace(tref[0], tref[-1], self.ARB_WF_MAXNPTS_PER_PACKET)
            y = np.interp(ttarget, tref, y)
        
        if not is_within(y.size, self.ARB_WF_NPTS_BOUNDS):
            raise VisaError(f'invalid waveform size: {y.size} (must be within {self.ARB_WF_NPTS_BOUNDS})')
        
        # Log
        logger.info(f'uploading {y.size}-points arbitrary waveform into volatile memory')

        # Normalize vector to appropriate range
        if dtype in ('dac', 'dac16'):
            lb, ub = self.ARB_WF_DAC_RANGE
            precision = 0  # no decimals specified for integer values
        elif dtype == 'float':
            lb, ub = self.ARB_WF_FLOAT_RANGE
        y = self.normalize(y, lb=lb, ub=ub)

        # Convert to integer if necessary
        if dtype in ('dac', 'dac16'):
            y = y.astype(int)

        # If binary upload
        if dtype == 'dac16':
            # Upload waveform to volatile memory, by successive packets
            nperpacket = self.ARB_WF_MAXNPTS_PER_PACKET
            yremain = y.copy()
            while yremain.size > 0:
                ypacket, yremain = yremain[:nperpacket], yremain[nperpacket:]
                suffix = 'CON' if yremain.size > 0 else 'END'
                self.write_binary_values(
                    f'SOUR{ich}:TRAC:DATA:DAC16 VOLATILE,{suffix},',
                    ypacket, datatype='H', is_big_endian=False)
        
        # If string upload
        else:
            # Transform waveform vector to string
            ystr = ','.join([f'{yy:.{precision}f}' for yy in y])

            # Upload waveform to volatile memory
            cmdprefix = f'SOUR{ich}:DATA'
            if dtype == 'dac':
                cmdprefix = f'{cmdprefix}:DAC'
            self.write(f'{cmdprefix} VOLATILE,{ystr}')

        # Check that waveform was uploaded correctly
        self.check_error()

        # If needed, set number of waveform points to uploaded waveform size
        # to avoid unwanted padding
        if y.size < self.ARB_WF_MAXNPTS_PER_PACKET:
            self.set_waveform_npoints(ich, y.size)

        # Set output mode to frequency to enable use as amplitude modulator
        self.set_arbitrary_output_mode(ich, 'FREQ')

        # If specified, set waveform type to arbitrary
        if activate:
            self.set_waveform_type(ich, 'USER')

    @property
    def ARB_WF_DAC_MAX(self):
        ''' Maximum integer value for arbitrary waveform DAC. '''
        return self.ARB_WF_DAC_RANGE[1]
    
    def get_waveform_value(self, ich, idx):
        '''
        Get value of arbitrary waveform loaded in volatile memory of specific channel at specific index.

        :param ich: channel index
        :param idx: waveform index (0-based, converted to 1-based for query)
        :return: waveform value at index, normalized to [0 - 1] range
        '''
        # Check channel index
        self.check_channel_index(ich)
        # Check that index is valid
        imax = self.get_waveform_npoints(ich) - 1
        if idx < 0 or idx >= imax:
            raise VisaError(f'invalid index: {idx} (must be between 0 and {imax})')
        # Query waveform value at specific index
        n = int(self.query(f'SOUR{ich}:DATA:VAL? VOLATILE,{idx + 1}'))
        # Return as float within [0 - 1] interval
        return float(n / self.ARB_WF_DAC_MAX)
    
    def set_waveform_value(self, ich, idx, val):
        '''
        Set value of arbitrary waveform loaded in volatile memory of specific channel at specific index.

        :param ich: channel index
        :param idx: waveform index (0-based, converted to 1-based for set command)
        :param val: waveform value at index, normalized to [0 - 1] range
        '''
        # Check channel index
        self.check_channel_index(ich)
        # Check that index is valid
        imax = self.get_waveform_npoints(ich) - 1
        if idx < 0 or idx >= imax:
            raise VisaError(f'invalid index: {idx} (must be between 0 and {imax})')
        # Check that value is valid
        if val < 0 or val > 1:
            raise VisaError(f'invalid value: {val} (must be between 0 and 1)')
        # Scale value to DAC integer range
        val = int(val * self.ARB_WF_DAC_MAX)
        # Set waveform value at specific index
        self.write(f'SOUR{ich}:DATA:VAL VOLATILE,{idx + 1},{val}')
        self.check_error()
    
    def download_arbitrary_waveform(self, ich):
        '''
        Get waveform vector loaded in volatile memory of specific channel.

        :param ich: channel index
        :return: waveform data as numpy array
        '''
        raise NotImplementedError('download_arbitrary_waveform() not implemented yet')
        # Check channel index
        self.check_channel_index(ich)

        # # Variant 1: binary transfer by packet (currently not working)
        # logger.info(f'querying waveform vector from channel {ich} volatile memory')
        # npackages = int(self.query(f'SOUR{ich}:DATA:LOAD? VOLATILE'))
        # data = []
        # for i in range(npackages):
        #     query = f'SOUR{ich}:DATA:LOAD? {i + 1}'
        #     chunk = self.instrument_handle.query_binary_values(
        #         f'{self.PREFIX}{query}', datatype='H', is_big_endian=False)
        #     data += chunk
        # data = np.asarray(data)

        # # Variant 2: query waveform data, point by point (currently not working)
        # npts = self.get_waveform_npoints(ich)
        # data = np.zeros(npts, dtype=int)
        # logger.info(f'querying {npts}-points waveform vector from channel {ich} volatile memory')
        # for idx in tqdm(range(npts)):
        #     val = self.query(f'SOUR{ich}:DATA:VAL? VOLATILE,{idx + 1}')
        #     self.check_error()
        #     data[idx] = int(val)
        
        # Return as vector normalized to [0 - 1] interval
        return data / self.ARB_WF_DAC_MAX
    
    def load_waveform_from_file(self, ich, name):
        '''
        Load an arbitrary waveform from file into volatile memory of a specific channel.

        :param ich: channel index
        :param name: waveform file name
        '''
        # Check channel index
        self.check_channel_index(ich)
        # Check that waveform file name is valid
        if name not in self.get_waveform_catalog(ich=ich):
            raise VisaError(f'"{name}" file not found in channel {ich} catalog')
        # Load waveform from file
        self.write(f'SOUR{ich}:DATA:COPY {name},VOLATILE')
        self.check_error()
    
    def check_waveform_file_name(self, name):
        ''' Check that a waveform file name is valid. '''
        mo = re.match(self.WAF_PATTERN, name)
        if mo is None:
            raise VisaError(f'invalid waveform file name: "{name}" (must match {self.WAF_PATTERN})')
    
    def save_waveform_to_memory(self, name):
        '''
        Store the current arbitrary waveform data (ARB) in the specified storage
        location in the internal non-volatile memory with the default name.

        :param name: waveform file name
        '''
        self.check_waveform_file_name(name)
        self.write(f'*SAV {name}')
    
    def get_waveform_from_memory(self, name):
        '''
        Recall the arbitrary waveform file (ARB) stored in the specified location
        in the internal non-volatile memory.

        :param name: waveform file name
        '''
        self.check_waveform_file_name(name)
        self.write(f'*RCL {name}')

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
    
    # --------------------- MODULATION ---------------------

    def enable_modulation(self, ich):
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:MOD ON')
    
    def disable_modulation(self, ich):
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:MOD OFF')

    def is_modulation_enabled(self, ich):
        self.check_channel_index(ich)
        return self.query(f'SOUR{ich}:MOD?') == 'ON'

    def set_modulation_mode(self, ich, mode):
        self.check_channel_index(ich)
        self.check_modulation_mode(mode)
        self.write(f'SOUR{ich}:MOD:TYP {mode}')
    
    def get_modulation_mode(self, ich):
        self.check_channel_index(ich)
        return self.query(f'SOUR{ich}:MOD:TYP?')

    @property
    def MOD_VOLT_AMP(self):
        return self.MOD_VOLT_RANGE[1] - self.MOD_VOLT_RANGE[0]
    
    # --------------------- AM ---------------------

    def get_am_depth(self, ich):
        ''' 
        Get amplitude modulation depth for the specified channel (in %)

        :param ich: channel index
        :return: modulation depth (in %)
        '''
        self.check_channel_index(ich)
        return float(self.query(f'SOUR{ich}:AM:DEPT?'))

    def set_am_depth(self, ich, depth):
        ''' 
        Set amplitude modulation depth for the specified channel (in %)

        :param ich: channel index
        :param depth: modulation depth (in %)
        '''
        self.check_channel_index(ich)
        if not is_within(depth, self.AM_DEPTH_RANGE):
            raise VisaError(f'invalid AM depth: {depth} (must be within {self.AM_DEPTH_RANGE})')
        self.write(f'SOUR{ich}:AM:DEPT {depth}')

    def enable_am_dssc(self, ich):
        ''' 
        Enable AM Distortion Suppression Signal Control (DSSC) for the specified channel. 

        :param ich: channel index
        '''
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:AM:DSSC ON')
    
    def disable_am_dssc(self, ich):
        '''
        Disable AM Distortion Suppression Signal Control (DSSC) for the specified channel. 

        :param ich: channel index
        '''
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:AM:DSSC OFF')
    
    def is_am_dssc_enabled(self, ich):
        ''' 
        Check whether AM Distortion Suppression Signal Control (DSSC) is enabled for the specified channel.

        :param ich: channel index
        '''
        self.check_channel_index(ich)
        return self.query(f'SOUR{ich}:AM:DSSC?') == 'ON'
    
    def set_am_freq(self, ich, freq):
        ''' 
        Set amplitude modulation frequency for the specified channel.

        :param ich: channel index
        :param freq: modulation frequency (Hz)
        '''
        self.check_channel_index(ich)
        if not is_within(freq, self.AM_FREQ_RANGE):
            raise VisaError(f'invalid AM frequency: {freq} (must be within {self.AM_FREQ_RANGE})')
        self.write(f'SOUR{ich}:AM:INT:FREQ {freq}')
    
    def get_am_freq(self, ich):
        ''' 
        Get amplitude modulation frequency for the specified channel.

        :param ich: channel index
        :return: modulation frequency (Hz)
        '''
        self.check_channel_index(ich)
        return float(self.query(f'SOUR{ich}:AM:INT:FREQ?'))
    
    def set_am_waveform(self, ich, wtype):
        ''' 
        Set amplitude modulation waveform for the specified channel.

        :param ich: channel index
        :param wtype: modulation waveform
        '''
        self.check_channel_index(ich)
        self.check_waveform_type(wtype)
        self.write(f'SOUR{ich}:AM:INT:FUNC {wtype}')
    
    def get_am_waveform(self, ich):
        ''' 
        Get amplitude modulation waveform for the specified channel.

        :param ich: channel index
        :return: modulation waveform
        '''
        self.check_channel_index(ich)
        return self.query(f'SOUR{ich}:AM:INT:FUNC?')
    
    def set_am_source(self, ich, source):
        ''' 
        Set amplitude modulation source for the specified channel.

        :param ich: channel index
        :param source: modulation source
        '''
        self.check_channel_index(ich)
        self.check_modulation_source(source)
        self.write(f'SOUR{ich}:AM:SOUR {source}')
    
    def get_am_source(self, ich):
        ''' 
        Get amplitude modulation source for the specified channel.

        :param ich: channel index
        :return: modulation source
        '''
        self.check_channel_index(ich)
        return self.query(f'SOUR{ich}:AM:SOUR?')
    
    def enable_am(self, ich):
        ''' 
        Enable amplitude modulation for the specified channel.

        :param ich: channel index
        '''
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:AM:STAT ON')

    def disable_am(self, ich):
        ''' 
        Disable amplitude modulation for the specified channel.

        :param ich: channel index
        '''
        self.check_channel_index(ich)
        self.write(f'SOUR{ich}:AM:STAT OFF')
    
    def is_am_enabled(self, ich):
        ''' 
        Check whether amplitude modulation is enabled for the specified channel.

        :param ich: channel index
        '''
        self.check_channel_index(ich)
        return self.query(f'SOUR{ich}:AM:STAT?') == 'ON'

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
        self.write(f'SOUR{ich}:BURS:TRIG:SLOP {slope}')

    def get_trigger_slope(self, ich):
        self.check_channel_index(ich)
        return self.query(f'SOUR{ich}:BURS:TRIG:SLOP?')
    
    def wait_for_external_trigger(self, ich):
        ''' Set up channel to wait for external trigger. '''
        self.check_channel_index(ich)
        logger.info(f'waiting for external trigger on channel {ich}...')
        self.set_trigger_source(ich, 'EXT')
        self.enable_output_channel(ich)
    
    def wait_for_manual_trigger(self, ich):
        ''' Set up channel to wait for manual trigger. '''
        self.check_channel_index(ich)
        logger.info(f'waiting for manual/programmatic trigger on channel {ich}...')
        self.set_trigger_source(ich, 'MAN')
        self.enable_output_channel(ich)

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
        ''' Trigger specific channel programmatically. '''
        self.check_channel_index(ich)
        logger.info(f'triggering channel {ich} programmatically')
        self.write(f'SOUR{ich}:BURS:TRIG:IMM')
        self.wait()

    def start_trigger_loop(self, ich, T=None):
        '''
        Start a trigger loop with a specific channel
        
        :param ich: channel index
        :param T: trigger loop period (s)
        '''
        if T is not None:
            self.set_burst_internal_period(ich, T)
        self.set_trigger_source(ich, 'INT')
    
    # --------------------- MULTI-LAYER PULSING ---------------------
    
    def set_trigger_pulse_train(self, ich, PRF, tburst, Vpp=None, T=None, trig_source='EXT'):
        '''
        Set a train of TTL-type trigger pulses on a specific channel
        
        :param ich: channel index
        :param PRF: pulse repetition frequency (Hz)
        :param tburst: burst duration (s)
        :param Vpp: pulse amplitude in V, defaults to TTL pulse amplitude (5V)
        :param T: burst repetition period in s, only for internal trigger source (defaults to 2)
        :param trig_source: trigger source (default: external)
        '''
        # Define default log message
        s = f'setting channel {ich} to trigger {si_format(tburst, 2)}s long TTL pulse train with {si_format(PRF, 2)}Hz internal PRF'

        # Set default pulse amplitude if not specified
        if Vpp is None:
            Vpp = TTL_PAMP / MV_TO_V
        else:
            s = f'{s}, {si_format(Vpp, 2)}Vpp'

        # Complete log message based on trigger source
        if trig_source == 'INT':
            if T is None:
                T = 2.  # s
            s = f'{s}, repeated every {si_format(T, 2)}s'
        elif trig_source == 'EXT':
            s = f'{s}, triggered externally'
        elif trig_source == 'MAN':
            s = f'{s}, triggered manually/programmatically'
        else:
            raise ValueError(f'invalid trigger source: {trig_source}')
        
        # Log process
        logger.info(s)
        
        # Apply pulse with specific frequency, amplitude and offset
        self.apply_pulse(ich, PRF, Vpp, offset=Vpp / 2.)
        # Set nominal pulse width
        self.set_pulse_width(ich, TTL_PWIDTH)
        # Set pulse idle level to "bottom"
        self.set_burst_idle_level(ich, 'BOTTOM')
        # Set channel trigger source to external (to avoid erroneous outputs upon setting)
        self.set_trigger_source(ich, 'EXT')
        # Set burst repetition period, if any
        if T is not None:
            self.set_burst_internal_period(ich, T)  # s
        # Set burst duration
        self.set_burst_duration(ich, tburst)  # s
        # Enable burst mode on channel
        self.enable_burst(ich)
        # Enable channel sync signal on rear panel connector
        self.enable_output_sync(ich)
        # Set channel trigger source
        self.set_trigger_source(ich, trig_source)
    
    def set_AM_pulse_train(self, ich, PRF, DC, tburst, tramp=0, T=None, trig_source='EXT'):
        '''
        Set an amplitude modulating pulse train on a specific channel
        
        :param ich: channel index
        :param PRF: pulse repetition frequency (Hz)
        :param DC: duty cycle (%)
        :param tburst: burst duration (s)
        :param tramp: nominal pulse ramping duration (s), defaults to 0
        :param T: burst repetition period in s, only for internal trigger source (defaults to 2)
        :param trig_source: trigger source (default: external)
        '''
        # Define default log message
        s = f'setting channel {ich} to trigger {si_format(tburst, 2)}s long amplitude-modulating pulse train with {si_format(PRF, 2)}Hz internal PRF'

        # Add ramping time to log message if specified
        if tramp > 0:
            s = f'{s} and {si_format(tramp, 2)}s ramping time'

        # Complete log message based on trigger source
        if trig_source == 'INT':
            if T is None:
                T = 2.  # s
            s = f'{s}, repeated every {si_format(T, 2)}s'
        elif trig_source == 'EXT':
            s = f'{s}, triggered externally'
        elif trig_source == 'MAN':
            s = f'{s}, triggered manually/programmatically'
        else:
            raise ValueError(f'invalid trigger source: {trig_source}')
        
        # Log process
        logger.info(s)

        # If ramping time is specified
        if tramp > 0:
            # Design smoothed waveform with appropriate number of points
            npts = self.ARB_WF_MAXNPTS_PER_PACKET
            _, y = get_DC_smoothed_pulse_envelope(npts, PRF, DC, tramp=tramp, plot='all')
            # Upload it to volatile memory of specified channel, 
            # and set waveform type to "user"
            self.upload_arbitrary_waveform(ich, y, activate=True)
        # Otherwise
        else:
            # Use standard rectangular pulse with specific duty cycle
            self.set_waveform_type(ich, 'SQU')
            self.set_square_duty_cycle(ich, DC)  # %
            self.invert_waveform_phase(ich)  # invert phase to avoid DC offset

        # Set waveform amplitude to full AM range (with extra margin) and ensure zero offset
        self.set_waveform_amp(ich, (1 + 2 * self.MOD_VOLT_MARGIN) * self.MOD_VOLT_AMP)
        self.set_waveform_offset(ich, 0)
        # Apply waveform as burst with specific repetition frequency
        self.set_waveform_freq(ich, PRF)
        # Set channel trigger source to external (to avoid erroneous outputs upon setting)
        self.set_trigger_source(ich, 'EXT')
        # Set burst repetition period, if any
        if T is not None:
            self.set_burst_internal_period(ich, T)  # s
        # Set burst duration
        self.set_burst_duration(ich, tburst)  # s
        # Enable burst mode on channel
        self.enable_burst(ich)
        # Enable channel sync signal on rear panel connector
        self.enable_output_sync(ich)
        # If waveform is phase-inverted, set sync polarity to negative
        if self.is_waveform_phase_inverted(ich):
            self.set_output_sync_polarity(ich, 'NEG')
        # Set channel trigger source
        self.set_trigger_source(ich, trig_source)

    def set_triggered_sine_burst_train(self, Fdrive, Vpp, tstim, PRF, DC, ich_trig=1, ich_carrier=2, **kwargs):
        '''
        Set a train of sine bursts on a specific channel, triggered by another channel. 
        Used for pulsed sinusoidal waveform generation.
        
        :param Fdrive: driving frequency (Hz)
        :param Vpp: waveform amplitude (Vpp)
        :param tstim: total stimulus duration (s)
        :param PRF: pulse repetition frequency (Hz)
        :param DC: duty cycle (%)
        :param ich_gate: index of the gating channel
        :param ich_carrier: index of the carrier channel
        '''
        # Check that channels indexes are different
        if ich_trig == ich_carrier:
            raise VisaError('trigger and carrier channels cannot be identical')
        
        # Disable all outputs (carrier channel first to avoid erroneous outputs)
        self.disable_output_channel(ich_carrier)
        self.disable_output_channel(ich_trig)
        
        # Set trigger channel parameters
        self.set_trigger_pulse_train(ich_trig, PRF, tstim, **kwargs)

        # Set carrier channel parameters
        tburst = DC / (100 * PRF)  # s
        logger.info(f'setting channel {ich_carrier} to output {si_format(tburst, 2)}s long, ({si_format(Fdrive, 2)}Hz, {si_format(Vpp, 3)}Vpp) sine wave triggered externally by channel {ich_trig}')
        self.apply_sine(ich_carrier, Fdrive, Vpp)
        self.set_burst_duration(ich_carrier, tburst)  # s
        self.enable_burst(ich_carrier)
        self.set_trigger_source(ich_carrier, 'EXT')

        # If carrier amplitude is > 0, enable all outputs 
        # (carrier channel last to avoid erroneous outputs)
        if Vpp > 0.:
            self.enable_output_channel(ich_trig)
            self.enable_output_channel(ich_carrier)
    
    def set_AM_sine_burst_train(self, Fdrive, Vpp, tstim, PRF, DC, tramp=0, ich_mod=1, ich_carrier=2, **kwargs):
        '''
        Set a train of sine bursts on a specific channel, amplitude-modulated by another channel.
        Used for pulsed sinusoidal waveform generation, with optional envelope smoothing.
        
        :param Fdrive: driving frequency (Hz)
        :param Vpp: waveform amplitude (Vpp)
        :param tstim: total stimulus duration (s)
        :param PRF: pulse repetition frequency (Hz)
        :param DC: duty cycle (%)
        :param tramp: nominal pulse ramping duration (s), defaults to 0
        :param ich_mod: index of the modulating channel
        :param ich_carrier: index of the carrier channel
        '''
        # Check that channels indexes are different
        if ich_mod == ich_carrier:
            raise VisaError('gating and carrier channels cannot be identical')
        
        # Disable all outputs (carrier channel first to avoid erroneous outputs)
        self.disable_output_channel(ich_carrier)
        self.disable_output_channel(ich_mod)
        
        # Set envelope modulating channel parameters
        self.set_AM_pulse_train(ich_mod, PRF, DC, tstim, tramp=tramp, **kwargs)

        # Set sinewave channel parameters
        logger.info(f'setting channel {ich_carrier} to output ({si_format(Fdrive, 2)}Hz, {si_format(Vpp, 3)}Vpp) sine wave amplitude-modulated externally by channel {ich_mod}')
        self.apply_sine(ich_carrier, Fdrive, Vpp, 0)
        self.enable_am(ich_carrier)
        self.set_am_source(ich_carrier, 'EXT')

        # If carrier amplitude is > 0, enable all outputs 
        # (carrier channel last to avoid erroneous outputs)
        if Vpp > 0.:
            self.enable_output_channel(ich_mod)
            self.enable_output_channel(ich_carrier)
    
    def set_gated_sine_burst(self, *args, tramp=0, ich_gate=1, ich_carrier=2, gate_type='trig', **kwargs):
        '''
        Wrapper method to set up a train of sine bursts on a carrier channel, gated by
        another channel with a specific gating method. Two gating methods are supported:
        - "trigger" gating -> calls `set_triggered_sine_burst` method
        - "mod" gating -> calls `set_AM_sine_burst` method
        The "trigger" gating method is the default, but does not support envelope smoothing.
        
        :param tramp: nominal pulse ramping duration (s), defaults to 0
        :param ich_gate: index of the gating channel
        :param ich_carrier: index of the carrier channel
        :param gate_type: gating type (default: "trigger")
        '''
        # Trigger gating
        if gate_type == 'trig':
            # Check that ramp time is 0
            if tramp > 0:
                raise VisaError('ramping time not supported for trigger gating')
            # Call `set_triggered_sine_burst` method
            self.set_triggered_sine_burst_train(
                *args, ich_trig=ich_gate, ich_carrier=ich_carrier, **kwargs)
        
        # Modulation gating
        elif gate_type == 'mod':
            # Call `set_AM_sine_burst` method
            self.set_AM_sine_burst_train(
                *args, tramp=tramp, ich_mod=ich_gate, ich_carrier=ich_carrier, **kwargs)
        
        # Invalid gating type
        else:
            raise VisaError(f'invalid gating type: {gate_type}')
    
    def set_looping_sine_burst(self, ich, Fdrive, Vpp=.1, ncycles=200, PRF=100., tramp=0, 
                               ich_trig=None, gate_type='trig'):
        '''
        Set an internally looping sine burst on a specific channel
        
        :param ich: channel index (1 or 2)
        :param Fdrive: driving frequency (Hz)
        :param Vpp: waveform amplitude (Vpp)
        :param ncycles: number of cycles per burst
        :param PRF: pulse repetition frequency (Hz)
        :param tramp: nominal pulse ramping duration (s), defaults to 0
        :param ich_trig (optional): triggering channel index
        '''
        # Cast number of cycles to integer
        ncycles = int(np.round(ncycles))
        if ncycles < 1:
            raise VisaError(f'invalid number of cycles: {ncycles} (must be >= 1)')

        # If trigger channel is different than signal channel
        if ich_trig is not None:
            # Compute nominal burst duration and duty cycle
            tburst = ncycles / Fdrive  # s

            # Compute modulation periodicity
            mod_T = 1 / PRF  # s

            # Determine gating type
            if gate_type not in ('trig', 'mod'):
                raise ValueError(f'invalid gating type: {gate_type}')
            if tramp > 0 and gate_type == 'trig':
                logger.warning('ramping time not supported for trigger gating, switching to modulation gating')
                gate_type = 'mod'

            # Determine gate-type-dependent parameters
            if gate_type == 'trig':
                DC = 100  # %
                tstim = tburst  # s
                internal_PRF = 1 / tburst
            else:
                DC = PRF * tburst * 100  # %
                if DC > 100:
                    raise ValueError(f'{si_format(tburst, 2)}s burst cannot be pulsed at {PRF:.2f} Hz')
                tstim = 2 / PRF  # s
                internal_PRF = PRF

            # Set up gated pulse train
            self.set_gated_sine_burst(
                Fdrive, Vpp, tstim, internal_PRF, DC, T=mod_T, 
                tramp=tramp if gate_type == 'mod' else 0, 
                ich_gate=ich_trig, ich_carrier=ich, gate_type=gate_type
            )
            
            # Trigger mode: start trigger loop on trigger channel
            if gate_type == 'trig':
                self.start_trigger_loop(ich_trig, T=1. / PRF)
            
            # Modulation mode: disable burst mode on modulation channel to start
            # infinite modulation loop
            else:
                self.disable_burst(ich_trig)
        
        # Otherwise, set up loop directly on signal channel
        else:
            # Check that ramping time is 0
            if tramp > 0:
                raise VisaError('ramping time not supported for looping sine burst without trigger channel')
            
            # Log process
            params_str = ', '.join([
                f'{si_format(Fdrive, 3)}Hz',
                f'{si_format(Vpp, 3)}Vpp', 
                f'{ncycles} cycles'
            ])
            logger.info(f'setting ({params_str}) sine wave looping at {PRF:.1f} Hz on channel {ich}')
            
            # Disable all outputs
            self.disable_output_channel(ich)
            
            # Set sine wave channel parameters
            self.apply_sine(ich, Fdrive, Vpp)
            self.set_burst_internal_period(ich, 1 / PRF)  # s
            self.set_burst_ncycles(ich, ncycles)
            self.enable_burst(ich)

            # Start trigger loop and enable output
            self.start_trigger_loop(ich)
            self.enable_output_channel(ich)
