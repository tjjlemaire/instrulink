# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-04-07 17:51:29
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2022-09-07 19:58:08
# @Last Modified time: 2022-04-08 21:17:22

import re
import io
import struct
from PIL import Image

from .constants import *
from .si_utils import *
from .visa_instrument import *


class BKScope(VisaInstrument):

    USB_ID = '378C18113'
    NO_ERROR_CODE = 'CMR 0'
    PREFIX = ''
    UNITS = ['S', 'V', '%', 'Hz', 'Sa']
    CHANNELS = (1, 2, 3, 4)
    NAVGS = (4, 16, 32, 64, 128, 256)
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
    
    # CRST?
    # CRVA?
    # CRAU

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
    
    def get_nsweeps_per_acquisition(self):
        ''' Get the number of samples to average from for average acquisition.'''
        out = self.query('AVGA?')
        return self.process_int_mo(out, self.AVGA_REGEXP, '#sweeps/acquisition')
    
    def set_nsweeps_per_acquisition(self, value):
        ''' Set the number of samples to average from for average acquisition.'''
        if value not in self.NAVGS:
            raise VisaError(f'Not a valid number of sweeps. Candidates are {self.NAVGS}')
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

