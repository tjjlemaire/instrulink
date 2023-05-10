# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-04-07 17:51:29
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-10 18:56:47
# @Last Modified time: 2022-04-08 21:17:22

import abc
import re
import io
from PIL import Image
import matplotlib.pyplot as plt

from .constants import *
from .si_utils import *
from .utils import is_within
from .visa_instrument import *


class Oscilloscope(VisaInstrument):
    ''' Base class for oscilloscopes. '''
    
    # --------------------- REQUIRED ATTRIBUTES ---------------------
    
    @property
    @abc.abstractmethod
    def CHANNELS(self):
        ''' Available channel indexes '''
        raise NotImplementedError
    
    @property
    @abc.abstractmethod
    def NHDIVS(self):
        ''' Number of horizontal divisions '''
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def NVDIVS(self):
        ''' Number of vertical divisions '''
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def MAX_VDIV(self):
        ''' Max voltage per division (V) '''
        raise NotImplementedError
    
    @property
    @abc.abstractmethod
    def COUPLING_MODES(self):
        ''' Available coupling modes '''
        raise NotImplementedError
    
    @property
    @abc.abstractmethod
    def ACQ_TYPES(self):
        ''' Acquisition types '''
        raise NotImplementedError
        
    @property
    @abc.abstractmethod
    def NAVGS(self):
        ''' Number of samples to average for average acquisition '''
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def TRIGGER_MODES(self):
        ''' Available trigger modes '''
        raise NotImplementedError
    
    @property
    @abc.abstractmethod
    def TRIGGER_COUPLING_MODES(self):
        ''' Available trigger coupling modes '''
        raise NotImplementedError
    
    @property
    @abc.abstractmethod
    def TRIG_TYPES(self):
        ''' Available trigger types '''
        raise NotImplementedError
    
    @property
    @abc.abstractmethod
    def TRIGGER_SLOPES(self):
        ''' Available trigger slopes '''
        raise NotImplementedError
    
    @property
    @abc.abstractmethod
    def INTERP_TYPES(self):
        ''' Available interpolation types '''
        raise NotImplementedError
    
    # --------------------- MISCELLANEOUS ---------------------

    @abc.abstractmethod
    def calibrate(self):
        ''' Calibrate oscilloscope '''
        raise NotImplementedError
    
    # --------------------- DISPLAY ---------------------

    @abc.abstractmethod
    def show_trace(self, ich):
        ''' Enable trace display on specific channel '''
        raise NotImplementedError

    @abc.abstractmethod
    def hide_trace(self, ich):
        ''' Disable trace display on specific channel '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def is_trace(self, ich):
        ''' Query trace display on specific channel '''
        raise NotImplementedError
    
    def restrict_traces(self, ichs):
        ''' Restrict trace display to specific channels '''
        # Show traces for speficied channels
        for ich in ichs:
            self.show_trace(ich)
        # Hide traces for all other channels
        for ich in list(set(self.CHANNELS) - set(ichs)):
            if self.is_trace(ich):
                self.hide_trace(ich)
    
    @abc.abstractmethod
    def get_screen_binary_img(self):
        ''' Extract screen capture image in binary format '''
        raise NotImplementedError

    def capture_screen(self):
        '''
        Capture screen information in image format
        
        :return: PIL image object representing the screenshot
        '''
        # Extract binary image
        binary_img = self.get_screen_binary_img()
        # Convert image to PIL readable object and return
        return Image.open(io.BytesIO(binary_img))

    # --------------------- SCALES / OFFSETS ---------------------

    @abc.abstractmethod
    def auto_setup(self):
        ''' Perform auto-setup. '''
        raise NotImplementedError

    @abc.abstractmethod
    def set_temporal_scale(self, value):
        ''' Set the temporal scale (in s/div) '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def get_temporal_scale(self):
        ''' Get the temporal scale (in s/div) '''
        raise NotImplementedError
    
    def get_temporal_range(self):
        ''' Get temporal display range at current temporal scale range (in s) '''
        halfrange = self.get_temporal_scale() * self.NHDIVS / 2
        return (-halfrange, halfrange)
    
    @abc.abstractmethod
    def set_vertical_scale(self, ich, value):
        ''' Set the vertical sensitivity of the specified channel (in V/div) '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_vertical_scale(self, ich):
        ''' Get the vertical sensitivity of the specified channel (in V/div) '''
        raise NotImplementedError

    @abc.abstractmethod
    def set_vertical_offset(self, ich, value):
        ''' Set the vertical offset of the specified channel (in V) '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_vertical_offset(self, ich):
        ''' Get the vertical offset of the specified channel (in V) '''
        raise NotImplementedError
    
    # --------------------- FILTERS ---------------------

    @abc.abstractmethod
    def enable_bandwith_filter(self, ich):
        ''' Turn on bandwidth-limiting low-pass filter for specific channel '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def disable_bandwith_filter(self, ich):
        ''' Turn off bandwidth-limiting low-pass filter for specific channel '''
        raise NotImplementedError

    @abc.abstractmethod    
    def is_bandwith_filter_enabled(self, ich):
        ''' Query bandwidth-limiting low-pass filter for specific channel '''
        raise NotImplementedError
    
    # --------------------- PROBES & COUPLING ---------------------

    @abc.abstractmethod
    def get_probe_attenuation(self, ich):
        ''' Get the vertical attenuation factor of a specific channel '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def set_probe_attenuation(self, ich, value):
        ''' Set the vertical attenuation factor of a specific channel '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def get_coupling_mode(self, ich):
        ''' Get the coupling mode of a specific channel '''
        raise NotImplementedError

    @abc.abstractmethod
    def set_coupling_mode(self, ich, value):
        ''' Set the coupling mode of a specific channel '''
        raise NotImplementedError

    # --------------------- TRIGGER ---------------------

    @abc.abstractmethod
    def get_trigger_mode(self):
        ''' Get trigger mode '''
        raise NotImplementedError
     
    @abc.abstractmethod 
    def set_trigger_mode(self, value):
        ''' Set trigger mode '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_trigger_coupling_mode(self, *args, **kwargs):
        ''' Get trigger coupling mode. '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def set_trigger_coupling_mode(self, *args, **kwargs):
        ''' Set trigger coupling mode. '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def get_trigger_type(self):
        ''' Get trigger type '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def set_trigger_type(self, val):
        ''' Set trigger type '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def get_trigger_source(self):
        ''' Get trigger source channel index '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def set_trigger_source(self, ich):
        ''' Set trigger source channel index '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_trigger_level(self, *args, **kwargs):
        ''' Get trigger level (in V) '''
        raise NotImplementedError

    @abc.abstractmethod
    def set_trigger_level(self, *args, **kwargs):
        ''' Set trigger level (in V) '''
        raise NotImplementedError

    def check_trigger_delay(self, value):
        ''' Check that trigger delay value falls within current temporal range '''    
        tbounds = self.get_temporal_range()
        if not is_within(value, tbounds):
            logger.warning(
                f'target temporal delay ({si_format(value, 2)}s) outside of current display temporal bounds (+/- {si_format(tbounds[1], 2)}s) -> restricting')
            value = np.sign(value) * np.abs(tbounds[0])
        return value
    
    @abc.abstractmethod
    def get_trigger_delay(self):
        ''' Get trigger delay (in s) '''
        raise NotImplementedError

    @abc.abstractmethod
    def set_trigger_delay(self, value):
        ''' Set trigger delay (in s) '''
        raise NotImplementedError

    @abc.abstractmethod
    def force_trigger(self):
        ''' Force the instrument to make 1 acquisition '''
        raise NotImplementedError
    
    # --------------------- ACQUISITION ---------------------
    
    @abc.abstractmethod
    def arm_acquisition(self):
        '''
        Enables the signal acquisition process by changing the acquisition state
        (trigger mode) from "stopped" to "single".
        '''
        raise NotImplementedError
    
    def stop_acquisition(self):
        '''
        Immediately stops the acquisition of a signal (if the trigger mode is
        AUTO or NORM).
        '''
        self.write('STOP')

    @abc.abstractmethod
    def get_nsweeps_per_acquisition(self):
        ''' Get the number of samples to average from for average acquisition.'''
        raise NotImplementedError

    @abc.abstractmethod    
    def set_nsweeps_per_acquisition(self, value):
        ''' Set the number of samples to average from for average acquisition.'''
        raise NotImplementedError
    
    def get_acquisition_status(self):
        ''' Get the acquisition status of the oscilloscope '''
        out = self.query('SAST?')
        mo = re.match('SAST (.+)', out)
        return mo[1]
    
    @abc.abstractmethod
    def get_sample_rate(self):
        ''' Get the acquisition sampling rate (in samples/second) '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def get_nsamples(self, *args, **kwargs):
        ''' Get the number of samples per acquisition '''
        raise NotImplementedError

    @abc.abstractmethod
    def enable_peak_detector(self):
        ''' Turn on peak detector '''
        raise NotImplementedError

    @abc.abstractmethod
    def disable_peak_detector(self):
        ''' Turn off peak detector '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_acquisition_type(self):
        ''' Get oscilloscope acquisition type '''
        raise NotImplementedError
    
    @abc.abstractmethod
    def set_acquisition_type(self, value):
        ''' Set oscilloscope acquisition type '''
        raise NotImplementedError
    
    # --------------------- WAVEFORMS ---------------------

    @abc.abstractmethod
    def get_waveform_data(self, ich):
        '''
        Get waveform data from a specific channel
        
        :param ich: channel index
        :return: 2-tuple of numpy arrays with:
            - t: time signal (s)
            - y: waveform signal (V)
        '''
        raise NotImplementedError
    
    # --------------------- PLOTTING ---------------------
    
    def plot_waveform_data(self, *args, **kwargs):
        '''
        Acquire and plot waveform data
        
        :param ich: channel index
        :return: figure handle
        '''
        t, y = self.get_waveform_data(*args, **kwargs)
        fig, ax = plt.subplots()
        for k in ['right', 'top']:
            ax.spines[k].set_visible(False)
        ax.set_xlabel('time (ms)')
        ax.set_ylabel('voltage (V)')
        ax.set_title('waveform data')
        ax.plot(t * 1e3, y, label=f'ch{1}')
        ax.axvline(0, c='k', ls='--')
        ax.axhline(0, c='k', ls='--')
        return fig
    
    def plot_screen_capture(self):
        '''
        Acquire and render screen capture
        
        :return: figure handle
        '''
        img = self.capture_screen()
        fig, ax = plt.subplots()
        ax.imshow(img)
        ax.axis('off')
        return fig
