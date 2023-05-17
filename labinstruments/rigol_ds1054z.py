# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-04-07 17:51:29
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-11 17:31:16
# @Last Modified time: 2022-04-08 21:17:22

import struct
import numpy as np

from .constants import *
from .si_utils import *
from .visa_instrument import VisaError
from .oscilloscope import Oscilloscope
from .logger import logger


class RigolDS1054Z(Oscilloscope):

    # General parameters
    USB_ID = 'DS1ZA\d+' # USB identifier
    PREFIX = ':'  # prefix to be added to each command
    TIMEOUT_SECONDS = 20.  # long timeout to allow slow commands (e.g. auto-setup)
    CHANNELS = (1, 2, 3, 4)  # available channels
    NHDIVS = 12  # Number of horizontal divisions
    NVDIVS = 8  # Number of vertical divisions
    NO_ERROR_CODE = '0,"No error"'  # error code returned when no error
    MAX_VDIV = 10.  # Max voltage per division (V)
    VUNITS = ('VOLT', 'WATT', 'AMP', 'UNKN') # vertical units
    TBASES = [1, 2, 5]  # timebase relative values
    TFACTORS = np.logspace(-9, 1, 11)  # timebase multiplying factors
    TDIVS = np.ravel((np.tile(TBASES, (TFACTORS.size, 1)).T * TFACTORS).T)[2:]  # timebase values

    # Acquisition parameters
    COUPLING_MODES = (  # coupling modes
        'AC',  # alternating current
        'DC',  # direct current
        'GND'   # ground
    )
    ACQ_TYPES = ('NORM', 'AVER', 'PEAK', 'HRES')  # acquisition types
    NAVGS = np.power(2, np.arange(0, 11))  # number of sweeps to average from
    INTERP_TYPES = ('LIN', 'OFF')  # interpolation types

    # Trigger parameters
    TRIGGER_MODES = ('AUTO', 'NORM', 'SING')  # trigger modes
    TRIGGER_COUPLING_MODES = ('AC', 'DC', 'LFR', 'HFR')  # trigger coupling modes
    TRIG_TYPES = (  # trigger types
        'EDGE', 'PULS', 'RUNT', 'WIND', 'NEDG', 'SLOP', 'VID',
        'PATT', 'DEL', 'TIM', 'DUR', 'SHOL', 'RS232', 'IIC', 'SPI'
    )
    TRIGGER_SLOPES = ('POS', 'NEG', 'RFAL')  # trigger slopes

    # Waveform parameters
    SAMPLES_ON_DISPLAY = 1200  # number of samples available on display
    WAVEFORM_READING_MODES = ('NORM', 'MAX', 'RAW')   # waveform reading modes
    WAVEFORM_FORMATS = ('WORD', 'BYTE', 'ASC')  # waveform reading formats
    MAX_BYTE_LEN = 250000  # max number of bytes to read from internal memory at once

    # Units parameters
    UNITS_PER_PARAM = {}

    # --------------------- MISCELLANEOUS ---------------------

    def wait(self, t=None):
        ''' Wait for previous command to finish. '''
        self.write('*WAI')
    
    def get_last_error(self):
        ''' Get last error message. '''
        return self.query('SYST:ERR?')

    def lock_front_panel(self):
        ''' Lock front panel '''
        self.write('SYST:LOCK ON')

    def unlock_front_panel(self):
        ''' Unlock front panel '''
        self.write('SYST:LOCK OFF')

    def calibrate(self):
        ''' Calibrate oscilloscope '''
        self.query('CAL:STAR')

    def stop_calibrate(self):
        ''' Stop calibration '''
        self.query('CAL:QUIT')
    
    @staticmethod
    def decode_ieee_block(ieee_bytes):
        '''
        Strips headers (and trailing bytes) from a IEEE binary data block off.

        This is the block format commands like `WAV:DATA?`, `DISP:DATA?`,
        `SYST:SET?`, and `ETAB<n>:DATA?` return their data in.

        :param ieee_bytes: binary data block
        :return: stripped binary data block
        '''
        n_header_bytes = int(chr(ieee_bytes[1])) + 2
        n_data_bytes = int(ieee_bytes[2:n_header_bytes].decode('ascii'))
        return ieee_bytes[n_header_bytes:n_header_bytes + n_data_bytes]
    
    # --------------------- DISPLAY ---------------------

    def display_menu(self):
        pass

    def hide_menu(self):
        pass
    
    def show_trace(self, ich):
        ''' Enable trace display on specific channel '''
        self.check_channel_index(ich)
        self.write(f'CHAN{ich}:DISP ON')
    
    def hide_trace(self, ich):
        ''' Disable trace display on specific channel '''
        self.check_channel_index(ich)
        self.write(f'CHAN{ich}:DISP OFF')
    
    def is_trace(self, ich):
        ''' Query trace display on specific channel '''
        self.check_channel_index(ich)
        out = self.query(f'CHAN{ich}:DISP?')
        return bool(int(out))
    
    def get_screen_binary_img(self):
        '''
        Extract screen capture image in binary format
        
        :return: binary image
        '''
        # Query image
        self.write('DISP:DATA? ON,OFF,PNG')
        # Extract image buffer
        logger.info('Receiving screen capture...')
        buff = self.read_raw() #self.DISPLAY_DATA_BYTES)
        logger.info(f'read {len(buff)} bytes in .display_data')
        return self.decode_ieee_block(buff)

    # --------------------- SCALES / OFFSETS ---------------------

    def auto_setup(self):
        ''' Perform auto-setup. '''
        logger.info('running scope auto-setup...')
        self.write('AUT')

    def set_temporal_scale(self, value):
        ''' Set the temporal scale (in s/div) '''
        # If not in set, replace with closest valid number (in log-distance)
        if value not in self.TDIVS:
            value = self.TDIVS[np.abs(np.log(self.TDIVS) - np.log(value)).argmin()]
        logger.info(f'setting time scale to {si_format(value, 2)}s/div')
        self.write(f'TIM:MAIN:SCAL {value}')
    
    def get_temporal_scale(self):
        ''' Get the temporal scale (in s/div) '''
        out = self.query('TIM:MAIN:SCAL?')
        return float(out)
    
    def set_vertical_scale(self, ich, value):
        ''' Set the vertical sensitivity of the specified channel (in V/div) '''
        self.check_channel_index(ich)
        if value > self.MAX_VDIV:
            logger.warning(
                f'target vertical scale ({value} V/div) above instrument limit ({self.MAX_VDIV} V/div) -> restricting')
            value = self.MAX_VDIV
        logger.info(f'setting channel {ich} vertical scale to {si_format(value, 2)}V/div')
        self.write(f'CHAN{ich}:SCAL {value}')

    def get_vertical_scale(self, ich):
        ''' Get the vertical sensitivity of the specified channel (in V/div) '''
        self.check_channel_index(ich)
        out = self.query(f'CHAN{ich}:SCAL?')
        return float(out)

    def set_vertical_offset(self, ich, value):
        ''' Set the vertical offset of the specified channel (in V) '''
        self.check_channel_index(ich)
        self.write(f'CHAN{ich}:OFFS {value}')

    def get_vertical_offset(self, ich):
        ''' Get the vertical offset of the specified channel (in V) '''
        self.check_channel_index(ich)
        out = self.query(f'CHAN{ich}:OFFS?')
        return float(out)
    
    def get_vertical_unit(self, ich):
        ''' Get the vertical axis unit of a specific channel '''
        self.check_channel_index(ich)
        out = self.query(f'CHAN{ich}:UNIT?')
        return out

    def set_vertical_unit(self, ich, value):
        ''' Set the vertical axis unit of a specific channel '''
        self.check_channel_index(ich)
        if value not in self.VUNITS:
            raise VisaError(
                f'{value} not a valid vertical unit (candidates are {self.VUNITS})')
        self.write(f'CHAN{ich} {value}')
    
    def enable_vertical_scale_fine_adjustment(self, ich):
        ''' Enable fine adjustment of the vertical scale of the specific channel '''
        self.check_channel_index(ich)
        self.write(f'CHAN{ich}:VERN ON')
    
    def disable_vertical_scale_fine_adjustment(self, ich):
        ''' Disable fine adjustment of the vertical scale of the specific channel '''
        self.check_channel_index(ich)
        self.write(f'CHAN{ich}:VERN OFF')
    
    def is_vertical_scale_fine_adjustment_enabled(self, ich):
        ''' Query fine adjustment of the vertical scale of the specific channel '''
        self.check_channel_index(ich)
        out = self.query(f'CHAN{ich}:VERN?')
        return bool(int(out))
    
    def invert_vertical_scale(self, ich):
        ''' Invert the vertical scale of the specific channel '''
        self.check_channel_index(ich)
        self.write(f'CHAN{ich}:INV ON')
    
    def uninvert_vertical_scale(self, ich):
        ''' Uninvert the vertical scale of the specific channel '''
        self.check_channel_index(ich)
        self.write(f'CHAN{ich}:INV OFF')
    
    def is_vertical_scale_inverted(self, ich):
        ''' Query vertical scale inversion of the specific channel '''
        self.check_channel_index(ich)
        out = self.query(f'CHAN{ich}:INV?')
        return bool(int(out))
    
    def get_vertical_range(self, ich):
        ''' Get the vertical range of the specific channel '''
        self.check_channel_index(ich)
        out = self.query(f'CHAN{ich}:RANG?')
        return float(out)
    
    def set_vertical_range(self, ich, value):
        ''' Set the vertical range of the specific channel '''
        self.check_channel_index(ich)
        self.write(f'CHAN{ich}:RANG {value}')
    
    # --------------------- FILTERS ---------------------

    def enable_bandwith_filter(self, ich):
        ''' Turn on bandwidth-limiting low-pass filter for specific channel '''
        self.check_channel_index(ich)
        self.write(f'CHAN{ich}:BWL 20M')
    
    def disable_bandwith_filter(self, ich):
        ''' Turn off bandwidth-limiting low-pass filter for specific channel '''
        self.check_channel_index(ich)
        self.write(f'CHAN{ich}:BWL OFF')
    
    def is_bandwith_filter_enabled(self, ich):
        ''' Query bandwidth-limiting low-pass filter for specific channel '''
        self.check_channel_index(ich)
        out = self.query(f'CHAN{ich}:BWL?')
        return out == 'ON'
    
    # --------------------- PROBES & COUPLING ---------------------

    def get_probe_attenuation(self, ich):
        ''' Get the vertical attenuation factor of a specific channel '''
        self.check_channel_index(ich)
        out = self.query(f'CHAN{ich}:PROB?')
        return float(out)
    
    def set_probe_attenuation(self, ich, value):
        ''' Set the vertical attenuation factor of a specific channel '''
        self.check_channel_index(ich)
        self.write(f'CHAN{ich}:PROB {value}')

    def get_coupling_mode(self, ich):
        ''' Get the coupling mode of a specific channel '''
        return self.query(f'CHAN{ich}:COUP?')

    def set_coupling_mode(self, ich, value):
        ''' Set the coupling mode of a specific channel '''
        self.check_channel_index(ich)
        if value not in self.COUPLING_MODES:
            raise VisaError(
                f'invalid coupling mode: {value} (candidates are {self.COUPLING_MODES})')
        logger.info(f'setting channel {ich} coupling mode to {value}')
        self.write(f'CHAN{ich}:COUP {value}')

    # --------------------- TRIGGER ---------------------

    def get_trigger_mode(self):
        ''' Get trigger mode '''
        return self.query('TRIG:SWE?')
     
    def set_trigger_mode(self, value):
        ''' Set trigger mode '''
        value = value.upper()
        if value not in self.TRIGGER_MODES:
            raise VisaError(
                f'{value} not a valid trigger mode (candidates are {self.TRIGGER_MODES})')
        self.write(f'TRIG:SWE {value}')
    
    def get_trigger_coupling_mode(self, ich):
        ''' Get the trigger coupling mode. '''
        if self.get_trigger_source() != ich:
            self.set_trigger_source(ich)
        return self.query('TRIG:COUP?')
    
    def set_trigger_coupling_mode(self, ich, value):
        ''' Set the trigger coupling mode. '''
        if self.get_trigger_source() != ich:
            self.set_trigger_source(ich)
        if value not in self.TRIGGER_COUPLING_MODES:
            raise VisaError(
                f'{value} not a valid trigger coupling mode (candidates are {self.TRIGGER_COUPLING_MODES})')
        self.write(f'TRIG:COUP {value}')
    
    def get_trigger_type(self):
        ''' Get trigger type '''
        return self.query('TRIG:MODE?')
    
    def set_trigger_type(self, val):
        ''' Set trigger type '''
        if val not in self.TRIG_TYPES:
            raise VisaError(
                f'{val} not a valid trigger types. Candidates are {self.TRIG_TYPES}')
        self.write(f'TRIG:MODE {val}')
    
    def get_trigger_status(self):
        ''' Get trigger status '''
        return self.query('TRIG:STAT?')

    def set_trigger_holdoff(self, value):
        ''' Set trigger holdoff '''
        self.write(f'TRIG:HOLD {value}')
    
    def get_trigger_holdoff(self):
        ''' Get trigger holdoff '''
        return self.query('TRIG:HOLD?')
    
    def enable_trigger_noise_rejection(self):
        ''' Enable trigger noise rejection '''
        self.write('TRIG:NREJ ON')

    def disable_trigger_noise_rejection(self):
        ''' Disable trigger noise rejection '''
        self.write('TRIG:NREJ OFF')
    
    def is_trigger_noise_rejected(self):
        ''' Query trigger noise rejection status '''
        return bool(int(self.query('TRIG:NREJ?')))
    
    def get_trigger_position(self):
        ''' Get position in internal memory that corresponds to the waveform trigger position. '''
        out = int(self.query('TRIG:POS?'))
        if out == -2:
            raise VisaError('instrument not triggered')
        elif out == -1:
            raise VisaError('instrument triggered outside internal memory')
        return out

    def get_trigger_source(self):
        ''' Get trigger source channel index '''
        ttype = self.get_trigger_type()
        out = self.query(f'TRIG:{ttype}:SOUR?')
        return int(out[-1])
    
    def set_trigger_source(self, ich):
        ''' Set trigger source channel index '''
        self.check_channel_index(ich)
        logger.info(f'setting trigger source to channel {ich}')
        ttype = self.get_trigger_type()
        self.write(f'TRIG:{ttype}:SOUR CHAN{ich}')
    
    def get_trigger_slope(self, ich):
        ''' Get trigger slope for current trigger type '''
        if self.get_trigger_source() != ich:
            self.set_trigger_source(ich)
        ttype = self.get_trigger_type()
        return self.query(f'TRIG:{ttype}:SLOP?')
    
    def set_trigger_slope(self, ich, value):
        ''' Set trigger slope for current trigger type '''
        if self.get_trigger_source() != ich:
            self.set_trigger_source(ich)
        value = value.upper()
        if value not in self.TRIGGER_SLOPES:
            raise VisaError(
                f'{value} not a valid trigger slope (candidates are {self.TRIGGER_SLOPES})')
        ttype = self.get_trigger_type()
        logger.info(f'setting {ttype} trigger slope to {value}')
        self.write(f'TRIG:{ttype}:SLOP {value}')
    
    def get_trigger_level(self, ich):
        ''' Get trigger level (in V) '''
        if self.get_trigger_source() != ich:
            self.set_trigger_source(ich)
        ttype = self.get_trigger_type()
        out = self.query(f'TRIG:{ttype}:LEV?')
        return float(out)

    def set_trigger_level(self, ich, value):
        ''' Set trigger level (in V) '''
        if self.get_trigger_source() != ich:
            self.set_trigger_source(ich)
        ttype = self.get_trigger_type()
        self.write(f'TRIG:{ttype}:LEV {value}')
    
    def get_trigger_delay(self):
        ''' Get the trigger delay of the specified trigger source (in s) '''
        return float(self.query('TIM:MAIN:OFFS?'))

    def set_trigger_delay(self, value):
        ''' Set the trigger delay (in s) '''
        self.check_trigger_delay(value)
        logger.info(f'setting trigger time delay to {si_format(value, 2)}s')
        self.write(f'TIM:MAIN:OFFS {value}')

    def force_trigger(self):
        ''' Force the instrument to make 1 acquisition '''
        self.write('TFOR')
    
    # --------------------- CURSORS ---------------------
    # TODO: implement cursor functions
    
    # --------------------- ACQUISITION ---------------------
    
    def arm_acquisition(self):
        '''
        Enables the signal acquisition process by changing the acquisition state
        (trigger mode) from "stopped" to "single".
        '''
        self.write('RUN')
 
    def get_nsweeps_per_acquisition(self):
        ''' Get the number of samples to average from for average acquisition.'''
        out = self.query('ACQ:AVER?')
        return int(out)
    
    def set_nsweeps_per_acquisition(self, value):
        ''' Set the number of samples to average from for average acquisition.'''
        if value not in self.NAVGS:
            raise VisaError(f'Not a valid number of sweeps: {value}. Candidates are {self.NAVGS}')
        if value == 1:
            self.set_acquisition_type('NORM')
        else:
            self.set_acquisition_type('AVER')
            self.write(f'ACQ:AVER {value}')
    
    def get_sample_rate(self):
        ''' Get the acquisition sampling rate (in samples/second) '''
        out = self.query('ACQ:SRAT?')
        return int(float(out))
    
    def get_nsamples(self):
        ''' Get the number of samples in memory depth '''
        out = self.query('ACQ:MDEP?')
        if out == 'AUTO':
            logger.warning('auto memory depth enabled -> returning default value')
            return self.SAMPLES_ON_DISPLAY
        else:
            return int(out)

    def set_nsamples(self, value):
        ''' Set the number of samples in memory depth '''
        self.write(f'ACQ:MDEP {value}') 

    def get_acquisition_type(self):
        ''' Get oscilloscope acquisition type '''
        out = self.query('ACQ:TYPE?')
        return out
    
    def set_acquisition_type(self, value):
        ''' Set oscilloscope acquisition type '''
        value = value.upper()
        if value not in self.ACQ_TYPES:
            raise ValueError(
                f'invalid acquisition type: {value} (candidates are {self.ACQ_TYPES})')
        self.write(f'ACQ:TYPE {value}')
    
    def enable_peak_detector(self):
        ''' Turn on peak detector '''
        self.set_acquisition_type('PEAK')

    def disable_peak_detector(self):
        ''' Turn off peak detector '''
        self.set_acquisition_type('NORM')
    
    # --------------------- PARAMETERS ---------------------
    
    def get_parameter_value(self, ich, pkey):
        ''' Query the value of a parameter on a particular channel '''
        raise NotImplementedError    
    
    # --------------------- WAVEFORMS ---------------------

    def set_waveform_source(self, ich):
        ''' Set the waveform source to specific channel '''
        self.check_channel_index(ich)
        self.write(f'WAV:SOUR CHAN{ich}')

    def get_waveform_source(self):
        ''' Get the waveform source '''
        out = self.query('WAV:SOUR?')
        return int(out[-1])

    def set_waveform_reading_mode(self, value):
        ''' Set the waveform reading mode '''
        if value not in self.WAVEFORM_READING_MODES:
            raise VisaError(
                f'{value} not a valid waveform reading mode (candidates are {self.WAVEFORM_READING_MODES})')
        self.write(f'WAV:MODE {value}')
    
    def get_waveform_reading_mode(self):
        ''' Get the waveform reading mode '''
        out = self.query('WAV:MODE?')
        return out
    
    def set_waveform_format(self, value):
        ''' Set the waveform format '''
        if value not in self.WAVEFORM_FORMATS:
            raise VisaError(
                f'{value} not a valid waveform format (candidates are {self.WAVEFORM_FORMATS})')
        self.write(f'WAV:FORM {value}')
    
    def get_waveform_format(self):
        ''' Get the waveform format '''
        out = self.query('WAV:FORM?')
        return out
    
    def set_waveform_start(self, value):
        ''' Set the start point of waveform data reading. '''
        self.write(f'WAV:STAR {int(value)}')
    
    def get_waveform_start(self):
        ''' Query the start point of waveform data reading. '''
        out = self.query('WAV:STAR?')
        return int(out)
    
    def set_waveform_stop(self, value):
        ''' Set the stop point of waveform data reading. '''
        self.write(f'WAV:STOP {int(value)}')

    def get_waveform_stop(self):
        ''' Query the stop point of waveform data reading. '''
        out = self.query('WAV:STOP?')
        return int(out)
    
    def is_running(self):
        ''' Query if acquisition is running '''
        return self.get_trigger_status() in ('TD', 'WAIT', 'RUN', 'AUTO')

    def get_waveform_header(self):
        '''
        Extract a dictionary of values from the waveform header, converted to float
        and int as appropriate.

        :return: dictionary of waveform header values
        '''
        values = self.query('WAV:PRE?')
        values = values.split(',')
        assert len(values) == 10
        fmt, typ, pnts, cnt, xref, yorig, yref  = (int(val) for val in values[:4] + values[6:7] + values[8:10])
        xinc, xorig, yinc = (float(val) for val in values[4:6] + values[7:8])
        return {
            'fmt': fmt,
            'typ': typ,
            'pnts': pnts,
            'cnt': cnt,
            'xinc': xinc,
            'xorig': xorig,
            'xref': xref,
            'yinc': yinc,
            'yorig': yorig,
            'yref': yref
        }

    def get_raw_waveform_buffer(self):
        '''
        Query raw waveform buffer
        
        :return: raw waveform data buffer (in bytes)
        '''
        self.write('WAV:DATA?')
        return self.decode_ieee_block(self.read_raw())
    
    def _get_waveform_bytes(self, ich, mode='NORM'):
        '''
        Internal method to get the waveform data for a specific channel as bytes.

        This function distinguishes between requests for reading the waveform data
        currently being displayed on the screen or if you will be reading the internal 
        memory.
        
        - If you set mode to RAW, the scope will be stopped first and you will get the bytes
        from internal memory. (Please start it again yourself, if you need to, afterwards.)
        - If you set the mode to MAX this function will return the internal memory if the 
        scope is stopped, and the screen memory otherwise.

        In case the internal memory will be read, the data request will automatically be 
        split into chunks if it's impossible to read all bytes at once.

        :return: waveform data in bytes
        '''
        # Cast mode to uppercase
        mode = mode.upper()

        # Set waveform source, mode and format
        self.set_waveform_source(ich)
        self.set_waveform_reading_mode(mode)
        self.set_waveform_format('BYTE')
        
        # If normal acquisition mode, or "max" mode and acquisition is running
        if mode == 'NORM' or (mode == 'MAX' and self.is_running()):
            # Read the waveform data displayed on the screen
            return self._get_waveform_bytes_screen()

        # Otherwise
        else:
            # Read the waveform data in the internal memory
            return self._get_waveform_bytes_internal()

    def _get_waveform_bytes_screen(self):
        '''
        Internal method to extract waveform bytes from the scope if you desire
        to read the bytes corresponding to the screen content.

        :return: waveform data in bytes
        '''
        # Query raw waveform data
        buff = self.get_raw_waveform_buffer()

        # Make sure that the size of output buffer matches the number of points
        if len(buff) != self.get_waveform_header()['pnts']:
            raise VisaError('number of points in waveform buffer does not match header information')
        
        # Return waveform bytes
        return buff

    def _get_waveform_bytes_internal(self):
        '''
        Internal method to extract waveform bytes from the scope if you desire
        to read the bytes corresponding to the internal (deep) memory.
        '''        
        # If acquisition running, stop it 
        if self.is_running():
            self.stop_acquisition()

        # Extract number of points from waveform header
        npts = self.get_waveform_header()['pnts']

        # Initialize empty buffer and set starting position
        buff = b''
        pos = 1

        # Loop until all bytes have been read
        while len(buff) < npts:
            # Set waveform block start and stop position
            self.set_waveform_start(pos)
            self.set_waveform_stop(min(npts, pos + self.MAX_BYTE_LEN - 1))

            # Query waveform block and append to buffer
            buff += self.get_raw_waveform_buffer()

            # Increment position
            pos += self.MAX_BYTE_LEN
            logger.info(f'waveform acquisition: fetched {len(buff)}/{npts} points from internal memory')
        
        # Return waveform bytes
        return buff

    def get_waveform_data(self, ich, **kwargs):
        '''
        Get waveform data from a specific channel
        
        :param ich: channel index
        :return: scaled waveform data (numpy array)
        '''
        # Check channel index
        self.check_channel_index(ich)

        # Get waveform bytes and waveform header
        buff = self._get_waveform_bytes(ich, **kwargs)
        wp = self.get_waveform_header()

        # Convert bytes to samples array and rescale appropriately
        y = np.array(list(struct.unpack(str(len(buff)) + 'B', buff)))
        y = (y - wp['yorig'] - wp['yref']) * wp['yinc']

        # Get time vector
        t = np.arange(y.size) * wp['xinc'] + wp['xorig']  # s

        # Return time and voltage vectors
        return t, y

