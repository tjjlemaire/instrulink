# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-04-07 17:51:29
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2022-11-16 11:36:55
# @Last Modified time: 2022-04-08 21:17:22

import re
import io
import struct
from PIL import Image

from .constants import *
from .si_utils import *
from .utils import is_within
from .visa_instrument import *


class BKScope(VisaInstrument):

    USB_ID = '378[A-Z]181\d+'
    NO_ERROR_CODE = 'CMR 0'
    PREFIX = ''
    UNITS = ['S', 'V', '%', 'Hz', 'Sa']
    CHANNELS = (1, 2, 3, 4)
    NHDIVS = 18  # Number of horizontal divisions
    NVDIVS = 8  # Number of vertical divisions
    NAVGS = (1, 4, 16, 32, 64, 128, 256)
    ACQ_TYPES = ('PEAK_DETECT','SAMPLING','AVERAGE')
    INTERP_TYPES = ('linear', 'sine')
    CURSOR_TYPES = ('HREF', 'HDIF', 'VREF', 'VDIF', 'TREF', 'TDIF')
    CVALUES_TYPES = ('HREL', 'VREL')
    FILTER_TYPES = ('LP', 'HP', 'BP', 'BR')
    FILTER_REL_LIMS = (2.5, 230)  # Filter cutoff limits (Hz * (s/div) = 1/div)
    units_per_param = {
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
    TRIGGER_MODES = ('AUTO', 'NORM', 'SINGLE', 'STOP')
    TRIGGER_SLOPES = ('NEG', 'POS', 'WINDOW')
    TDIV_REGEXP = f'TDIV ({SI_REGEXP})([A-z]+)'
    VDIV_REGEXP = f'C{{}}:VDIV ({SI_REGEXP})([A-z]+)'
    VOFF_REGEXP = f'C{{}}:OFST ({SI_REGEXP})([A-z]+)'
    TRLV_REGEXP = f'C{{}}:TRLV ({SI_REGEXP})([A-z]+)'
    TRSL_REGEXP = f'C{{}}:TRSL ([A-z]+)'
    ATTN_REGEXP = f'C{{}}:ATTN ({INT_REGEXP})'
    TRCP_REGEXP = 'C{}:TRCP ([A-z]+)'
    TRMD_REGEXP = 'TRMD ([A-z]+)'
    TRDL_REGEXP = f'TRDL ({FLOAT_REGEXP})([A-z]+)'
    SARA_REGEXP = f'SARA ({FLOAT_REGEXP})([A-z]+)'
    AVGA_REGEXP = f'AVGA ({INT_REGEXP})'
    SXSA_REGEXP = '(SXSA) (ON|OFF)'
    ACQW_REGEXP = '(ACQW) (AVERAGE,?\d*|SAMPLING|PEAK_DETECT)'
    SANU_REGEXP = f'SANU ({INT_REGEXP})'
    PAVA_REGEXP = f'C{{}}:PAVA {{}},({SI_REGEXP})([A-z]+)'
    SAST_REGEXP = 'SAST (.+)'
    WFSU_REGEXP = 'WFSU SP,([0-9]+),NP,([0-9]+),FP,([0-9]+),SN,([0-9]+)'
    CFMT_REGEXP = '^CFMT (DEF9|IND0|OFF),(BYTE|WORD),(BIN|HEX)$'
    TRSE_REGEXP = f'TRSE (EDGE|GLIT|INTV|TV),SR,C({INT_REGEXP}),HT,(TI|PS|PL|PE|IS|IL|IE),HV,({FLOAT_REGEXP})([A-z]+)'
    TBASES = [1, 2.5, 5]
    TWEIGHTS = np.logspace(-9, 1, 11)
    TDIVS = np.ravel((np.tile(TBASES, (TWEIGHTS.size, 1)).T * TWEIGHTS).T)
    TIMEOUT_SECONDS = 20.  # long timeout to allow slow commands (e.g. auto-setup)
    TRIG_TYPES = (  # trigger types
        'EDGE',  # edge trigger
        'GLIT',  # pulse trigger
        'INTV',  # slope trigger
        'TV'  # video trigger
    )
    HOLD_TYPES = (  # pulse types
        'TI',  # holdoff
        'PS',  # if pulse width is smaller than the set value (in GLIT mode)
        'PL',  # if pulse width is larger than the set value (in GLIT mode)
        'PE',  # if pulse width is equal with the set value (in GLIT mode)
        'IS',  # if interval is smaller than the set value (in INTV mode)
        'IL',  # if interval is larger than the set value (in INTV mode)
        'IE'   # if interval is equal with the set value (in INTV mode)
    )
    MAX_VDIV = 5.  # Max voltage per division (V)

    # --------------------- MISCELLANEOUS ---------------------

    def connect(self):
        super().connect()
        self.timeout = self.TIMEOUT_SECONDS * S_TO_MS

    def wait(self, t=None):
        s = 'WAIT'
        if t is not None:
            s = f'{s} {t}'
        self.write(s)
    
    def get_last_error(self):
        return self.query('CMR?')

    def lock_front_panel(self):
        self.write('LOCK ON')

    def unlock_front_panel(self):
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

    def si_process(self, val):
        ''' Process an input value to be set '''
        return si_format(val, space='').upper()
    
    def process_int_mo(self, out, rgxp, key):
        ''' Process an integer notation regexp match object '''
        mo = re.match(rgxp, out)
        if mo is None:
            raise VisaError(f'could not extract {key} from "{out}"')
        return int(mo[1])
    
    def process_float(self, val, suffix):
        if suffix in self.UNITS:
            exp = 0
        else:
            try:
                exp = SI_powers[suffix[0]]
            except KeyError:
                exp = SI_powers[suffix[0].swapcase()]
        factor = np.float_power(10, exp)
        return val * factor
    
    def process_float_mo(self, out, rgxp, key):
        ''' Process a float notation regexp match object '''
        mo = re.match(rgxp, out)
        if mo is None:
            raise VisaError(f'could not extract {key} from "{out}"')
        val = float(mo[1])
        suffix = mo[2]
        return self.process_float(val, suffix)
    
    # --------------------- DISPLAY ---------------------

    def display_menu(self):
        self.write('MENU ON')
    
    def hide_menu(self):
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
    
    def restrict_traces(self, ichs):
        ''' Restrict trace display to specific channels '''
        # Show traces for speficied channels
        for ich in ichs:
            self.show_trace(ich)
        # Hide traces for all other channels
        for ich in list(set(self.CHANNELS) - set(ichs)):
            if self.is_trace(ich):
                self.hide_trace(ich)

    def screen_dump(self):
        '''
        Obtain the screen information in image format
        
        :return: PIL image object representing the screenshot
        '''
        # Query image
        self.write('SCDP')
        # Extract image
        binary_img = self.read_raw()
        # Convert image to PIL readable object and return
        return Image.open(io.BytesIO(binary_img))

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
        logger.info(f'setting scope time scale to {value * S_TO_MS:.3f} ms/div')
        self.write(f'TDIV {self.si_process(value)}S')
    
    def get_temporal_scale(self):
        ''' Get the temporal scale (in s/div) '''
        out = self.query('TDIV?')
        return self.process_float_mo(out, self.TDIV_REGEXP, 'temporal scale')
    
    def set_vertical_scale(self, ich, value):
        ''' Set the vertical sensitivity of the specified channel (in V/div) '''
        self.check_channel_index(ich)
        if value > self.MAX_VDIV:
            logger.warning(
                f'target vertical scale ({value} V/div) above instrument limit ({self.MAX_VDIV} V/div) -> restricting')
            value = self.MAX_VDIV
        logger.info(f'setting oscilloscope channel {ich} vertical scale to {value:.3f} V/div')
        self.write(f'C{ich}: VDIV {self.si_process(value)}V')

    def get_vertical_scale(self, ich):
        ''' Get the vertical sensitivity of the specified channel (in V/div) '''
        self.check_channel_index(ich)
        out = self.query(f'C{ich}: VDIV?')
        return self.process_float_mo(
            out, self.VDIV_REGEXP.format(ich), f'channel {ich} vertical scale')

    def set_vertical_offset(self, ich, value):
        ''' Set the vertical offset of the specified channel (in V) '''
        self.check_channel_index(ich)
        self.write(f'C{ich}: OFST {self.si_process(value)}V')

    def get_vertical_offset(self, ich):
        ''' Get the vertical offset of the specified channel (in V) '''
        self.check_channel_index(ich)
        out = self.query(f'C{ich}: OFST?')
        return self.process_float_mo(
            out, self.VOFF_REGEXP.format(ich), f'channel {ich} vertical offset')
    
    # --------------------- FILTERS ---------------------

    def enable_bandwith_filter(self, ich):
        ''' Turn on bandwidth-limiting low-pass filter for specific channel '''
        self.check_channel_index(ich)
        self.write(f'BWL C{ich} ON')
    
    def disable_bandwith_filter(self, ich):
        ''' Turn off bandwidth-limiting low-pass filter for specific channel '''
        self.check_channel_index(ich)
        self.write(f'BWL C{ich} OFF')
    
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
        out_rgxp = f'C{ich}:FILT (ON|OFF)'
        mo = re.match(out_rgxp, out)
        return {'ON': True, 'OFF': False}[mo.group(1)]
    
    # --------------------- PROBES ---------------------

    def get_probe_attenuation(self, ich):
        ''' Get the vertical attenuation factor of a specific probe '''
        self.check_channel_index(ich)
        out = self.query(f'C{ich}:ATTN?')
        print(out)
        mo = re.match(self.ATTN_REGEXP.format(ich), out)
        return float(mo[1])
    
    def set_probe_attenuation(self, ich, value):
        ''' Set the vertical attenuation factor of a specific probe '''
        self.check_channel_index(ich)
        self.write(f'C{ich}:ATTN {value}')

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
        out_rgxp = f'C{ich}:CRST {ctype},({FLOAT_REGEXP})'
        mo = re.match(out_rgxp, out)
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

    def get_trigger_level(self, ich):
        ''' Get the trigger level of the specified trigger source (in V) '''
        self.check_channel_index(ich)
        out = self.query(f'C{ich}:TRLV?')
        return self.process_float_mo(
            out, self.TRLV_REGEXP.format(ich), f'channel {ich} trigger level')

    def set_trigger_level(self, ich, value):
        ''' Set the trigger level of the specified trigger source (in V) '''
        self.check_channel_index(ich)
        self.write(f'C{ich}:TRLV {self.si_process(value)}V')

    def set_trigger_halfamp(self):
        ''' 
        Set the trigger level of the specified trigger source to the
        centre of the signal amplitude.
        '''
        self.write('SET50')
    
    def get_trigger_delay(self):
        ''' Get the trigger delay of the specified trigger source (in s) '''
        out = self.query('TRDL?')
        return self.process_float_mo(out, self.TRDL_REGEXP, 'trigger delay')

    def set_trigger_delay(self, value):
        ''' Set the trigger delay (in s) '''
        logger.info(f'setting scope trigger time delay to {value * S_TO_MS:.3f} ms')
        self.write(f'TRDL {self.si_process(value)}S')

    def get_trigger_coupling_mode(self, ich):
        ''' Get the trigger coupling of the selected source. '''
        self.check_channel_index(ich)
        out = self.query(f'C{ich}: TRCP?')
        return re.match(self.TRCP_REGEXP.format(ich), out)[1]
    
    def set_trigger_coupling_mode(self, ich, value):
        ''' Set the trigger coupling of the selected source. '''
        self.check_channel_index(ich)
        self.write(f'C{ich}: TRCP {value}')
    
    def get_trigger_mode(self):
        ''' Get trigger mode '''
        out = self.query('TRMD?')
        return re.match(self.TRMD_REGEXP, out)[1]
     
    def set_trigger_mode(self, value):
        ''' Set trigger mode '''
        value = value.upper()
        if value not in self.TRIGGER_MODES:
            raise VisaError(
                f'{value} not a valid trigger mode (candidates are {self.TRIGGER_MODES})')
        self.write(f'TRMD {value}')

    def get_trigger_options(self):
        ''' Get trigger type and options '''
        out = self.query(f'TRIG_SELECT?')
        mo = re.match(self.TRSE_REGEXP, out)
        return {
            'type': mo[1],
            'source': int(mo[2]),
            'hold_type': mo[3],
            'hold_val': self.process_float(float(mo[4]), mo[5])
        }
    
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
        logger.info(f'setting oscilloscope trigger source to channel {ich}')
        ttype = self.get_trigger_type()
        self.write(f'TRSE {ttype},SR,C{ich}')

    def get_trigger_slope(self, ich):
        ''' Get trigger slope of a particular trigger source '''
        self.check_channel_index(ich)
        out = self.query(f'C{ich}: TRSL?')
        return re.match(self.TRSL_REGEXP.format(ich), out)[1]
    
    def set_trigger_slope(self, ich, value):
        ''' Set trigger slope of a particular trigger source '''
        self.check_channel_index(ich)
        value = value.upper()
        if value not in self.TRIGGER_SLOPES:
            raise VisaError(
                f'{value} not a valid trigger slope (candidates are {self.TRIGGER_SLOPES})')
        self.write(f'C{ich}: TRSL {value}')

    def force_trigger(self):
        ''' Force the instrument to make 1 acquisition '''
        self.write('FRTR')

    def trg(self):
        ''' Execute an ARM command '''
        self.write('*TRG')        
    
    # --------------------- ACQUISITION ---------------------
    
    def arm_acquisition(self):
        '''
        Enables the signal acquisition process by changing the acquisition state
        (trigger mode) from "stopped" to "single".
        '''
        self.write('ARM')
    
    def stop_acquisition(self):
        '''
        Immediately stops the acquisition of a signal (if the trigger mode is
        AUTO or NORM).
        '''
        self.write('STOP')

    def get_interpolation_type(self):
        ''' Get the type of waveform interpolation (linear or sine) '''
        out = self.query('SXSA?')
        mo = re.match(self.SXSA_REGEXP, out)
        _, SXSA = mo.groups()
        return {
            'ON': 'sine',
            'OFF': 'linear'
        }[SXSA]
    
    def set_interpolation_type(self, value):
        ''' Get the type of waveform interpolation (linear or sine) '''
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
        return self.process_int_mo(out, self.AVGA_REGEXP, '#sweeps/acquisition')
    
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
        mo = re.match(self.SAST_REGEXP, out)
        return mo[1]
    
    def get_sample_rate(self):
        ''' Get the acquisition sampling rate (in samples/second) '''
        out = self.query('SARA?')
        return self.process_float_mo(out, self.SARA_REGEXP, 'sample rate')
    
    def get_nsamples(self, ich):
        ''' Get the number of samples in last acquisition in a specific channel '''
        self.check_channel_index(ich)
        out = self.query(f'SANU? C{ich}')
        mo = re.match(self.SANU_REGEXP, out)
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
        mo = re.match(self.ACQW_REGEXP, out)
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
        return self.process_float_mo(
            out, self.PAVA_REGEXP.format(ich, pkey), f'channel {ich} {pkey}')
    
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
        mo = re.match(self.WFSU_REGEXP, out)
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
        mo = re.match(self.CFMT_REGEXP, out)
        bfmt = mo[1]
        dtype = mo[2]
        enc = mo[3]
        return bfmt, dtype, enc

    @property
    def comunication_format(self):
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
        :return: scaled waveform data (numpy array)
        '''
        self.check_channel_index(ich)
        # Retrieve meta data
        meta = self.query_binary_values(
            f'C{ich}:WF? DESC',
            datatype='c')
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
        # hunit = meta[244].decode('utf-8')
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
        return t, y

