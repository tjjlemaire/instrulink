# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-04-07 17:51:29
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-11 17:26:57
# @Last Modified time: 2022-04-08 21:17:22

import re
import struct

from .constants import *
from .si_utils import *
from .utils import is_within
from .oscilloscope import Oscilloscope
from .visa_instrument import VisaError
from .logger import logger

class BK2555(Oscilloscope):

    # General parameters
    USB_ID = '378[A-Z]181\d+'  # USB identifier
    PREFIX = ''  # prefix to be added to each command
    TIMEOUT_SECONDS = 20.  # long timeout to allow slow commands (e.g. auto-setup)
    CHANNELS = (1, 2, 3, 4)  # available channels
    NHDIVS = 18  # Number of horizontal divisions
    NVDIVS = 8  # Number of vertical divisions
    NO_ERROR_CODE = 'CMR 0'  # error code returned when no error
    MAX_VDIV = 5.  # Max voltage per division (V)
    TBASES = [1, 2.5, 5]  # timebase relative values
    TFACTORS = np.logspace(-9, 1, 11)  # timebase multiplying factors
    TDIVS = np.ravel((np.tile(TBASES, (TFACTORS.size, 1)).T * TFACTORS).T)  # timebase values

    # Acquisition parameters
    COUPLING_MODES = (  # coupling modes
        'A1M',  # alternating current, 1 MOhm input impedance
        'A50',  # alternating current, 50 Ohm input impedance
        'D1M',  # direct current, 1 MOhm input impedance
        'D50',  # direct current, 50 Ohm input impedance
        'GND'   # ground
    )
    ACQ_TYPES = ('PEAK_DETECT','SAMPLING','AVERAGE')  # acquisition types
    NAVGS = (1, 4, 16, 32, 64, 128, 256)  # number of samples to average for average acquisition
    INTERP_TYPES = ('linear', 'sine')  # interpolation types

    # Trigger parameters
    TRIGGER_MODES = ('AUTO', 'NORM', 'SINGLE', 'STOP')  # trigger modes
    TRIGGER_COUPLING_MODES = ('AC', 'DC', 'HFREJ', 'LFREJ')  # trigger coupling modes
    TRIG_TYPES = (  # trigger types
        'EDGE',  # edge trigger
        'GLIT',  # pulse trigger
        'INTV',  # slope trigger
        'TV'  # video trigger
    )
    TRIGGER_SLOPES = ('NEG', 'POS', 'WINDOW')  # trigger slopes
    HOLD_TYPES = (  # pulse types
        'TI',  # holdoff
        'PS',  # if pulse width is smaller than the set value (in GLIT mode)
        'PL',  # if pulse width is larger than the set value (in GLIT mode)
        'PE',  # if pulse width is equal with the set value (in GLIT mode)
        'IS',  # if interval is smaller than the set value (in INTV mode)
        'IL',  # if interval is larger than the set value (in INTV mode)
        'IE'   # if interval is equal with the set value (in INTV mode)
    )

    # Cursor parameters
    CURSOR_TYPES = ('HREF', 'HDIF', 'VREF', 'VDIF', 'TREF', 'TDIF')  # cursor types
    CVALUES_TYPES = ('HREL', 'VREL')  # cursor value types

    # Filter parameters
    FILTER_TYPES = ('LP', 'HP', 'BP', 'BR')  # filter types
    FILTER_REL_LIMS = (2.5, 230)  # Filter cutoff limits (Hz * (s/div) = 1/div)

    # Unit parameters
    UNITS = ['S', 'V', '%', 'Hz', 'Sa']  # valid units for I/O communication
    UNITS_PER_PARAM = {
        'PKPK': 'V',  # peak-to-peak
        'MAX': 'V',  # maximum
        'MIN': 'V',  # minimum
        'AMPL': 'V',  # amplitude
        'TOP': 'V',  # top
        'BASE': 'V',  # base
        'CMEAN': 'V', # mean for cyclic waveform
        'MEAN': 'V',  # mean
        'RMS': 'V',  # root mean square
        'CRMS': 'V',  # RMS for cyclic waveform
        'OVSN': '%',  # negative overshoot 
        'OVSP': '%',  # positive overshoot 
        'FPRE': '%',  # (Vmin-Vbase)/ Vamp before the waveform falling transition
        'RPRE': '%',  # (Vmin-Vbase)/ Vamp before the waveform rising transition
        'PER': 'S',  # period
        'FREQ': 'Hz',  # frequency
        'PWID': 'S',  # positive width
        'NWID': 'S',  # negative width
        'RISE': 'S',  # rise time
        'FALL': 'S',  # fall time
        'WID': 'S',  # width
        'DUTY': '%',  # duty cycle
        'NDUTY': '%'  # negative duty cycle
    }

    # --------------------- MISCELLANEOUS ---------------------

    def wait(self, t=None):
        ''' Wait for previous command to finish. '''
        s = 'WAIT'
        if t is not None:
            s = f'{s} {t}'
        self.write(s)
    
    def get_last_error(self):
        ''' Query instrument for last error code. '''
        return self.query('CMR?')
    
    def get_status_byte_register(self):
        ''' Get the status byte register. '''
        # Query status byte register
        out = self.query('*STB?')
        # Extrat status byte register value (integer from 0 to 255)
        stb_int = self.process_int_mo(out, f'\*STB ({INT_REGEXP})', 'status byte')
        # Convert to binary string and extract status byte codes
        stb_seq = bin(stb_int)[2:].zfill(8)
        # Assemble outputs as dictionary
        stb_codes = ['INB', 'DIO1', 'VAB', 'DIO3', 'MAV', 'ESB', 'MSS/RQS', 'DIO7']
        stb_dict = {k: bool(int(s)) for k, s in zip(stb_codes, stb_seq)}
        # Remove unecessary codes
        stb_dict = {k: v for k, v in stb_dict.items() if not k.startswith('DIO')}
        # Return dictionary
        return stb_dict
    
    def lock_front_panel(self):
        ''' Lock front panel '''
        self.write('LOCK ON')

    def unlock_front_panel(self):
        ''' Unlock front panel '''
        self.write('LOCK OFF')

    def calibrate(self):
        ''' Calibrate oscilloscope '''
        self.query('*CAL?')

    def enable_automatic_calibration(self):
        ''' Enable automatic calibration. '''
        self.write('ACAL ON')

    def disable_automatic_calibration(self):
        ''' Disable automatic calibration. '''
        self.write('ACAL OFF')
    
    # --------------------- DISPLAY ---------------------

    def display_menu(self):
        ''' Display menu '''
        self.write('MENU ON')
    
    def hide_menu(self):
        ''' Hide menu '''
        self.write('MENU OFF')
    
    def show_trace(self, ich):
        ''' Enable trace display on specific channel '''
        self.check_channel_index(ich)
        self.write(f'C{ich}: TRA ON')
    
    def hide_trace(self, ich):
        ''' Disable trace display on specific channel '''
        self.check_channel_index(ich)
        self.write(f'C{ich}: TRA OFF')
    
    def is_trace(self, ich):
        ''' Query trace display on specific channel '''
        self.check_channel_index(ich)
        out = self.query(f'C{ich}: TRA?')
        return out.endswith('ON')
    
    def get_screen_binary_img(self):
        '''
        Extract screen capture image in binary format
        
        :return: binary image
        '''
        # Query image
        self.write('SCDP')
        # Extract image and return
        return self.read_raw()

    # --------------------- SCALES / OFFSETS ---------------------

    def auto_setup(self):
        ''' Perform auto-setup. '''
        logger.info('running oscilloscope auto-setup...')
        self.write('ASET')

    def set_temporal_scale(self, value):
        ''' Set the temporal scale (in s/div) '''
        # If not in set, replace with closest valid number (in log-distance)
        if value not in self.TDIVS:
            value = self.TDIVS[np.abs(np.log(self.TDIVS) - np.log(value)).argmin()]
        logger.info(f'setting time scale to {si_format(value, 2)}s/div')
        self.write(f'TDIV {self.si_process(value)}S')
    
    def get_temporal_scale(self):
        ''' Get the temporal scale (in s/div) '''
        out = self.query('TDIV?')
        return self.process_float_mo(out, f'TDIV ({SI_REGEXP})([A-z]+)', 'temporal scale')
    
    def set_vertical_scale(self, ich, value):
        ''' Set the vertical sensitivity of the specified channel (in V/div) '''
        self.check_channel_index(ich)
        if value > self.MAX_VDIV:
            logger.warning(
                f'target vertical scale ({value} V/div) above instrument limit ({self.MAX_VDIV} V/div) -> restricting')
            value = self.MAX_VDIV
        logger.info(f'setting channel {ich} vertical scale to {si_format(value, 2)}V/div')
        self.write(f'C{ich}: VDIV {self.si_process(value)}V')

    def get_vertical_scale(self, ich):
        ''' Get the vertical sensitivity of the specified channel (in V/div) '''
        self.check_channel_index(ich)
        out = self.query(f'C{ich}: VDIV?')
        return self.process_float_mo(
            out, f'C{ich}:VDIV ({SI_REGEXP})([A-z]+)', f'channel {ich} vertical scale')

    def set_vertical_offset(self, ich, value):
        ''' Set the vertical offset of the specified channel (in V) '''
        self.check_channel_index(ich)
        logger.info(f'setting channel {ich} vertical offset to {si_format(value, 2)}V/div')
        self.write(f'C{ich}: OFST {self.si_process(value)}V')

    def get_vertical_offset(self, ich):
        ''' Get the vertical offset of the specified channel (in V) '''
        self.check_channel_index(ich)
        out = self.query(f'C{ich}: OFST?')
        return self.process_float_mo(
            out, f'C{ich}:OFST ({SI_REGEXP})([A-z]+)', f'channel {ich} vertical offset')
    
    # --------------------- FILTERS ---------------------

    def enable_bandwith_filter(self, ich):
        ''' Turn on bandwidth-limiting low-pass filter for specific channel '''
        self.check_channel_index(ich)
        self.write(f'BWL C{ich}, ON')
    
    def disable_bandwith_filter(self, ich):
        ''' Turn off bandwidth-limiting low-pass filter for specific channel '''
        self.check_channel_index(ich)
        self.write(f'BWL C{ich}, OFF')
    
    def is_bandwith_filter_enabled(self, ich):
        ''' Query bandwidth-limiting low-pass filter for specific channel '''
        self.check_channel_index(ich)
        out = self.query('BWL?')
        bwl_rgxp = 'BWL ' + ','.join([f'C{c},(ON|OFF)' for c in self.CHANNELS])
        mo = re.match(bwl_rgxp, out)
        return mo.group(ich) == 'ON'
    
    def set_filter(self, ich, ftype, flow=None, fhigh=None):
        '''
        Set specific filter on specific channel
        
        :param ich: channel index
        :param ftype: filter type
        :param flow: filter lower limit frequency (Hz)
        :param flow: filter upper limit frequency (Hz)
        '''
        self.check_channel_index(ich)
        # Check filter type
        if ftype not in self.FILTER_TYPES:
            raise VisaError(
                f'invalid filter type: {ftype} (candidates are {self.FILTER_TYPES})')
        # Check frequency limits
        if ftype == 'LP':
            if flow is not None:
                raise VisaError('cannot specify frequency lower limit for LP filter')
            if fhigh is None:
                raise VisaError('frequency higher limit is required for LP filter')
        elif ftype == 'HP':
            if fhigh is not None:
                raise VisaError('cannot specify frequency higher limit for HP filter')
            if flow is None:
                raise VisaError('frequency lower limit is required for HP filter')
        else:
            if flow is None or fhigh is None:
                raise VisaError(
                    f'frequency lower and higher limits are required for {ftype} filter')
            if flow is not None and fhigh is not None:
                if flow >= fhigh:
                    raise VisaError(
                        f'frequency lower limit ({flow} Hz) must be smaller than higher limit ({fhigh} Hz)')
        tdiv = self.get_temporal_scale()  # s/div
        flims = np.asarray(self.FILTER_REL_LIMS) / tdiv  # Hz
        flims_str = ' - '.join([f'{si_format(f, 1)}Hz' for f in flims])
        for k, f in {'flow': flow, 'fhigh': fhigh}.items():
            if f is not None:
                if not is_within (f, flims):
                    raise VisaError(
                        f'{k} value ({si_format(f, 1)}Hz) outside of frequency limits ({flims_str}) with current temporal scale ({si_format(tdiv, 1)}s/div)')
        fdict = {'flow': flow, 'fhigh': fhigh}
        fdict = {k: v for k, v in fdict.items() if v is not None}
        fstr = ', '.join([f'{k} = {si_format(f, 1)}Hz' for k, f in fdict.items()])
        logger.info(f'setting {ftype} filter on channel {ich} with {fstr}')
        # Generate instruction code
        s = f'C{ich}:FILTS TYPE,{ftype}'
        if flow is not None:
            sf = si_format(flow, 1, space='').upper()
            s = f'{s},LOWLIMIT,{sf}Hz'
        if fhigh is not None:
            sf = si_format(fhigh, 1, space='').upper()
            s = f'{s},UPPLIMIT,{sf}Hz'
        self.write(s)
    
    def enable_filter(self, ich):
        ''' Turn on filter on spefific channel trace '''
        self.check_channel_index(ich)
        self.write(f'C{ich}: FILT ON')
    
    def disable_filter(self, ich):
        ''' Turn off filter on spefific channel trace '''
        self.check_channel_index(ich)
        self.write(f'C{ich}: FILT OFF')
    
    def is_filter_enabled(self, ich):
        ''' Check whether filter is enabled on spefific channel trace '''
        self.check_channel_index(ich)
        out = self.query(f'C{ich}: FILT?')
        mo = re.match(f'C{ich}:FILT (ON|OFF)', out)
        return {'ON': True, 'OFF': False}[mo.group(1)]
    
    # --------------------- PROBES & COUPLING ---------------------

    def get_probe_attenuation(self, ich):
        ''' Get the vertical attenuation factor of a specific channel '''
        self.check_channel_index(ich)
        out = self.query(f'C{ich}:ATTN?')
        mo = re.match(f'C{ich}:ATTN ({INT_REGEXP})', out)
        return float(mo[1])
    
    def set_probe_attenuation(self, ich, value):
        ''' Set the vertical attenuation factor of a specific channel '''
        self.check_channel_index(ich)
        logger.info(f'setting channel {ich} probe attenuation factor to {value}')
        self.write(f'C{ich}:ATTN {value}')

    def get_coupling_mode(self, ich):
        ''' Get the coupling mode of a specific channel '''
        out = self.query(f'C{ich}: CPL?')
        mo = re.match(f'C{ich}:CPL ([A-z0-9]+)', out)
        return mo[1]

    def set_coupling_mode(self, ich, value):
        ''' Set the coupling mode of a specific channel '''
        self.check_channel_index(ich)
        if value not in self.COUPLING_MODES:
            raise VisaError(
                f'invalid coupling mode: {value} (candidates are {self.COUPLING_MODES})')
        logger.info(f'setting channel {ich} coupling mode to {value}')
        self.write(f'C{ich}: CPL {value}')

    # --------------------- CURSORS ---------------------

    def set_cursor_position(self, ich, ctype, cpos):
        ''' 
        Set cursor position at a given screen location
        
        :param ich: cursor reference channel
        :param ctype: cursor type
        :param cpos: cursor position (in number of divisions)
        '''
        # Check cursor type
        if ctype not in self.CURSOR_TYPES:
            raise VisaError(
                f'invalid cursor type: {ctype} (candidates are {self.CURSOR_TYPES}')
        # Check cursor position
        if ctype in ('HREF', 'HDIF'):
            divbounds = (0.1, self.NHDIVS - 0.1)
        elif ctype in ('TREF', 'TDIF'):
            divbounds = (-self.NVDIVS / 2, self.NVDIVS / 2)
        elif ctype in ('VREF', 'VDIF'):
            divbounds = (-self.NHDIVS / 2, self.NHDIVS / 2)
        if not is_within(cpos, divbounds):
            raise VisaError(
                f'invalid {ctype} cursor position: {cpos} (bounds are {divbounds})')
        
        self.write(f'C{ich}: CRST {ctype}, {cpos}DIV')
    
    def get_cursor_position(self, ich, ctype):
        ''' 
        Get cursor position at a given screen location
        
        :param ich: cursor reference channel
        :param ctype: cursor type
        :return: cursor position (in number of divisions)
        '''
        # Check cursor type
        if ctype not in self.CURSOR_TYPES:
            raise VisaError(
                f'invalid cursor type: {ctype} (candidates are {self.CURSOR_TYPES}')
        out = self.query(f'C{ich}: CRST? {ctype}')
        mo = re.match(f'C{ich}:CRST {ctype},({FLOAT_REGEXP})', out)
        return float(mo.group(1))

    def get_cursor_value(self, ich, ctype):
        ''' 
        Get cursor value
        
        :param ich: cursor reference channel
        :param ctype: cursor type
        :return: cursor value(s)
        '''
        # Check cursor type
        if ctype not in self.CVALUES_TYPES:
            raise VisaError(
                f'invalid cursor type for value extraction: {ctype} (candidates are {self.CVALUES_TYPES}')
        out = self.query(f'C{ich}: CRVA? {ctype}')
        # Parser output depending on cursor type
        out_rgxp = f'C{ich}:CRVA {ctype}'
        if ctype == 'HREL':
            out_rgxp = f'{out_rgxp},({SI_REGEXP}),({SI_REGEXP}),({SI_REGEXP}),({FLOAT_REGEXP})'
        else:
            out_rgxp = f'{out_rgxp},({SI_REGEXP})'
        mo = re.match(out_rgxp, out)
        # Return cursor value(s)
        outs = [float(x) for x in mo.groups()]
        return outs

    def set_auto_cursor(self):
        ''' Set cursor mode to auto '''
        self.write('CRAU')

    # --------------------- TRIGGER ---------------------

    def get_trigger_mode(self):
        ''' Get trigger mode '''
        out = self.query('TRMD?')
        return re.match('TRMD ([A-z]+)', out)[1]
     
    def set_trigger_mode(self, value):
        ''' Set trigger mode '''
        value = value.upper()
        if value not in self.TRIGGER_MODES:
            raise VisaError(
                f'{value} not a valid trigger mode (candidates are {self.TRIGGER_MODES})')
        self.write(f'TRMD {value}')
    
    def get_trigger_coupling_mode(self, ich):
        ''' Get the trigger coupling of the selected source. '''
        self.check_channel_index(ich)
        out = self.query(f'C{ich}: TRCP?')
        return re.match(f'C{ich}:TRCP ([A-z]+)', out)[1]
    
    def set_trigger_coupling_mode(self, ich, value):
        ''' Set the trigger coupling of the selected source. '''
        self.check_channel_index(ich)
        if value not in self.TRIGGER_COUPLING_MODES:
            raise VisaError(
                f'{value} not a valid trigger coupling mode (candidates are {self.TRIGGER_COUPLING_MODES})')
        self.write(f'C{ich}: TRCP {value}')

    def get_trigger_type(self):
        ''' Get trigger type '''
        return self.get_trigger_options()['type']
    
    def set_trigger_type(self, val):
        ''' Set trigger type '''
        if val not in self.TRIG_TYPES:
            raise VisaError(
                f'{val} not a valid trigger types. Candidates are {self.TRIG_TYPES}')
        self.write(f'TRSE {val}')
    
    def get_trigger_source(self):
        ''' Get trigger source channel index '''
        return self.get_trigger_options()['source']
    
    def set_trigger_source(self, ich):
        ''' Set trigger source channel index '''
        self.check_channel_index(ich)
        logger.info(f'setting trigger source to channel {ich}')
        ttype = self.get_trigger_type()
        self.write(f'TRSE {ttype},SR,C{ich}')
    
    def get_trigger_slope(self, ich):
        ''' Get trigger slope of a particular trigger source '''
        self.check_channel_index(ich)
        out = self.query(f'C{ich}: TRSL?')
        return re.match(f'C{ich}:TRSL ([A-z]+)', out)[1]
    
    def set_trigger_slope(self, ich, value):
        ''' Set trigger slope of a particular trigger source '''
        self.check_channel_index(ich)
        value = value.upper()
        if value not in self.TRIGGER_SLOPES:
            raise VisaError(
                f'{value} not a valid trigger slope (candidates are {self.TRIGGER_SLOPES})')
        logger.info(f'setting channel {ich} trigger slope to {value}')
        self.write(f'C{ich}: TRSL {value}')

    def get_trigger_level(self, ich):
        ''' Get the trigger level of the specified trigger source (in V) '''
        self.check_channel_index(ich)
        out = self.query(f'C{ich}:TRLV?')
        return self.process_float_mo(
            out, f'C{ich}:TRLV ({SI_REGEXP})([A-z]+)', f'channel {ich} trigger level')

    def set_trigger_level(self, ich, value):
        ''' Set the trigger level of the specified trigger source (in V) '''
        self.check_channel_index(ich)
        logger.info(f'setting channel {ich} trigger level to {si_format(value, 2)}V')
        self.write(f'C{ich}:TRLV {self.si_process(value)}V')

    def set_trigger_halfamp(self):
        ''' 
        Set the trigger level of the specified trigger source to the
        centre of the signal amplitude.
        '''
        self.write('SET50')
    
    def get_trigger_delay(self):
        ''' Get trigger delay (in s) '''
        out = self.query('TRDL?')
        return self.process_float_mo(out, f'TRDL ({FLOAT_REGEXP})([A-z]+)', 'trigger delay')

    def set_trigger_delay(self, value):
        ''' Set trigger delay (in s) '''
        value = self.check_trigger_delay(value)
        logger.info(f'setting trigger time delay to {si_format(value, 2)}s')
        self.write(f'TRDL {self.si_process(value)}S')

    def get_trigger_options(self):
        ''' Get trigger type and options '''
        out = self.query(f'TRIG_SELECT?')
        tt_opts = '|'.join(self.TRIG_TYPES)
        ht_opts = '|'.join(self.HOLD_TYPES)
        mo = re.match(
            f'TRSE ({tt_opts}),SR,C({INT_REGEXP}),HT,({ht_opts}),HV,({FLOAT_REGEXP})([A-z]+)', out)
        return {
            'type': mo[1],
            'source': int(mo[2]),
            'hold_type': mo[3],
            'hold_val': self.process_float(float(mo[4]), mo[5])
        }

    def force_trigger(self):
        ''' Force the instrument to make 1 acquisition '''
        self.write('FRTR')
    
    # --------------------- ACQUISITION ---------------------
    
    def arm_acquisition(self):
        '''
        Enables the signal acquisition process by changing the acquisition state
        (trigger mode) from "stopped" to "single".
        '''
        self.write('ARM')

    def get_interpolation_type(self):
        ''' Get the type of waveform interpolation (linear or sine) '''
        out = self.query('SXSA?')
        mo = re.match('(SXSA) (ON|OFF)', out)
        _, SXSA = mo.groups()
        return {
            'ON': 'sine',
            'OFF': 'linear'
        }[SXSA]
    
    def set_interpolation_type(self, value):
        ''' Set the type of waveform interpolation (linear or sine) '''
        if value not in self.INTERP_TYPES:
            raise ValueError(
                f'invalid interpolation type: {value} (candidates are {self.INTERP_TYPES})')
        SXSA = {
            'sine': 'ON',
            'linear': 'OFF'
        }[value]
        self.write(f'SXSA {SXSA}')
    
    def get_nsweeps_per_acquisition(self):
        ''' Get the number of samples to average from for average acquisition.'''
        out = self.query('AVGA?')
        return self.process_int_mo(out, f'AVGA ({INT_REGEXP})', '#sweeps/acquisition')
    
    def set_nsweeps_per_acquisition(self, value):
        ''' Set the number of samples to average from for average acquisition.'''
        if value not in self.NAVGS:
            raise VisaError(f'Not a valid number of sweeps. Candidates are {self.NAVGS}')
        if value == 1:
            self.set_acquisition_type('SAMPLING')
        else:
            self.set_acquisition_type('AVERAGE')
            self.write(f'AVGA {value}')
    
    def get_acquisition_status(self):
        ''' Get the acquisition status of the oscilloscope '''
        out = self.query('SAST?')
        mo = re.match('SAST (.+)', out)
        return mo[1]
    
    def get_sample_rate(self):
        ''' Get the acquisition sampling rate (in samples/second) '''
        out = self.query('SARA?')
        return self.process_float_mo(out, f'SARA ({FLOAT_REGEXP})([A-z]+)', 'sample rate')
    
    def get_nsamples(self, ich):
        ''' Get the number of samples in last acquisition in a specific channel '''
        self.check_channel_index(ich)
        out = self.query(f'SANU? C{ich}')
        mo = re.match(f'SANU ({INT_REGEXP})', out)
        return int(mo[1])

    def enable_peak_detector(self):
        ''' Turn on peak detector '''
        self.write('PDET ON')

    def disable_peak_detector(self):
        ''' Turn off peak detector '''
        self.write('PDET OFF')

    def get_acquisition_type(self):
        ''' Get oscilloscope acquisition type '''
        out = self.query('ACQW?')
        mo = re.match('(ACQW) (AVERAGE,?\d*|SAMPLING|PEAK_DETECT)', out)
        _, acqtype = mo.groups()
        return acqtype
    
    def set_acquisition_type(self, value):
        ''' Set oscilloscope acquisition type '''
        value = value.upper()
        if value not in self.ACQ_TYPES:
            raise ValueError(
                f'invalid acquisition type: {value} (candidates are {self.ACQ_TYPES})')
        if value == 'AVERAGE':
            nsweeps = self.get_nsweeps_per_acquisition()
            value = f'{value},{nsweeps}'
        self.write(f'ACQW {value}')
    
    # --------------------- PARAMETERS ---------------------

    def get_parameter_value(self, ich, pkey):
        ''' Query the value of a parameter on a particular channel '''
        self.check_channel_index(ich)
        out = self.query(f'C{ich}: PAVA? {pkey}')
        if '****' in out:
            raise VisaError(f'could not extract {pkey} from channel {ich}')
        if out.endswith('%'):
            return self.process_float_mo(
                out, f'C{ich}:PAVA {pkey},({FLOAT_REGEXP})(%)', f'channel {ich} {pkey}')
        else:
            return self.process_float_mo(
                out, f'C{ich}:PAVA {pkey},({SI_REGEXP})([A-z]+)', f'channel {ich} {pkey}')
    
    def get_frequency(self, ich):
        ''' Get the waveform frequency on a particular channel '''
        self.check_channel_index(ich)
        return self.get_parameter_value(ich, 'FREQ')
    
    def get_ampl(self, ich):
        ''' Get the waveform amplitude on a particular channel '''
        self.check_channel_index(ich)
        return self.get_parameter_value(ich, 'AMPL')

    def get_min(self, ich):
        ''' Get the waveform min voltage on a particular channel '''
        self.check_channel_index(ich)
        return self.get_parameter_value(ich, 'MIN')
    
    def get_max(self, ich):
        ''' Get the waveform max voltage on a particular channel '''
        self.check_channel_index(ich)
        return self.get_parameter_value(ich, 'MAX')        

    def get_peak_to_peak(self, ich):
        ''' Get the waveform peak-to-peak voltage on a particular channel '''
        self.check_channel_index(ich)
        return self.get_parameter_value(ich, 'PKPK')
    
    # --------------------- WAVEFORMS ---------------------

    def get_waveform_settings(self):
        '''
        Get waveform settings
        
        :return: 3-tuple with (sparsing, number of points, and position of the 1st point)
        '''
        out = self.query('WAVEFORM_SETUP?')
        mo = re.match('WFSU SP,([0-9]+),NP,([0-9]+),FP,([0-9]+),SN,([0-9]+)', out)
        sp, npoints, fp, si = [int(x) for x in mo.groups()]
        return sp, npoints, fp, si
    
    @property
    def waveform_settings(self):
        sp, npoints, fp, si = self.get_waveform_settings()
        pdict = {'sparsing': sp, '# points': npoints, '1st point': fp, 'segment index': si}
        l = ['waveform settings:'] + [f' - {k} = {v}' for k, v in pdict.items()]
        return '\n'.join(l)
    
    def set_waveform_settings(self, sp=1, npoints=100, fp=0):
        '''
        Set waveform settings
        
        :param sp: sparsing,
        :param npoints: number of points
        :param fp: position of the 1st point)
        '''
        self.write(f'WFSU SP,{sp}, NP,{npoints}, FP,{fp}')
    
    def get_waveform_template(self):
        ''' Get a template description of the various logical entities making up a complete waveform.'''
        out = self.query('TMPL?')
        return out[8:-5]
    
    def get_comunication_format(self):
        '''
        Get the format features the oscilloscope uses to send waveform data
        
        :return: 3-tuple with (block_format, data_type, encoding)
        '''
        out = self.query('COMM_FORMAT?')
        mo = re.match('^CFMT (DEF9|IND0|OFF),(BYTE|WORD),(BIN|HEX)$', out)
        bfmt = mo[1]
        dtype = mo[2]
        enc = mo[3]
        return bfmt, dtype, enc

    @property
    def comunication_format(self):
        ''' Get a single string summarizing the format features the oscilloscope uses to send waveform data '''
        bfmt, dtype, enc = self.get_comunication_format()
        pdict = {'block format': bfmt, 'data type': dtype, 'encoding': enc}
        l = ['communication format:'] + [f' - {k} = {v}' for k, v in pdict.items()]
        return '\n'.join(l)

    @staticmethod
    def extract_from_bytes(bytes, istart, dtype='f'):
        '''
        Extract a field from the binary waveform header
        
        :param bytes: list of bytes representing the waveform header
        :param istart: start position of the field of interest
        :param dtype: data type of the field of interest
        :return: value of the field of interest
        '''
        # Deduce field size (in bytes) from data type
        s = {'f': 4, 'd': 8, 'l': 4}[dtype]
        
        # Extract binary segment
        fbin = b''.join(bytes[istart:istart + s])
        
        # Convert and return
        return struct.unpack(dtype, fbin)[0]

    def get_waveform_data(self, ich):
        '''
        Get waveform data from a specific channel
        
        :param ich: channel index
        :return: 2-tuple of numpy arrays with:
            - t: time signal (s)
            - y: waveform signal (V)
        '''
        # Check channel index
        self.check_channel_index(ich)
        
        # Retrieve meta data
        meta = self.query_binary_values(f'C{ich}:WF? DESC', datatype='c')
        
        # Extract number of sweeps per acquisition
        nsweeps_per_acq = self.extract_from_bytes(meta, istart=148, dtype='l')
        logger.debug(f'# sweeps/acq: {nsweeps_per_acq}')
        
        # Extract amplitude scale factor and amplitude offset
        vgain = self.extract_from_bytes(meta, istart=156)
        logger.debug(f'vertical gain: {vgain:.5e}')
        voff = self.extract_from_bytes(meta, istart=160)
        logger.debug(f'vertical offset: {voff:.5f} V')
        
        # Get sampling interval and horizontal offset
        dt = self.extract_from_bytes(meta, istart=176)
        logger.debug(f'sampling interval: {si_format(dt, 3)}s')
        hoff = self.extract_from_bytes(meta, istart=180, dtype='d')
        logger.debug(f'horizontal offset: {hoff} s')
        
        # Extract waveform data
        y = self.query_binary_values(
            f'C{ich}:WF? DAT2',
            container=np.ndarray,
            datatype='b')
        
        # Compare data length to expected number of points
        expected_npoints = self.get_waveform_settings()[1]
        if y.size != expected_npoints:
            raise VisaError(
                f'waveform parsing error: waveform size ({y.size}) does not correspond to expected number of points ({expected_npoints})')
        
        # Rescale waveform
        y = y * vgain - voff  # V
        
        # Get time vector
        t = np.arange(y.size) * dt + hoff  # s
        
        # Return
        return t, y
