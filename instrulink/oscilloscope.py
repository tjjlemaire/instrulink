# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-04-07 17:51:29
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2025-04-03 16:03:47
# @Last Modified time: 2022-04-08 21:17:22

import abc
import re
import io
from PIL import Image
import matplotlib.pyplot as plt

from .constants import *
from .si_utils import *
from .visa_instrument import *


class Oscilloscope(VisaInstrument):
    ''' Base class for oscilloscopes. '''

    TIMEOUT_SECONDS = 5. # 20.  # long timeout to allow slow commands (e.g. auto-setup)
    
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
    def MIN_VDIV(self):
        ''' Min voltage per division (V) '''
        return NotImplementedError
    
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
    
    @property
    @abc.abstractmethod
    def UNITS_PER_PARAM(self):
        ''' Units per parameter dictionary '''
        raise NotImplementedError
    
    # --------------------- MISCELLANEOUS ---------------------

    @abc.abstractmethod
    def calibrate(self):
        ''' Calibrate oscilloscope '''
        raise NotImplementedError
    
    # --------------------- DISPLAY ---------------------

    @abc.abstractmethod
    def display_menu(self):
        ''' Display menu '''
        raise NotImplementedError

    @abc.abstractmethod
    def hide_menu(self):
        ''' Hide menu '''
        raise NotImplementedError

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
        return self.get_temporal_scale() * self.NHDIVS
    
    @abc.abstractmethod
    def set_vertical_scale(self, ich, value, verbose=True):
        ''' Set the vertical sensitivity of the specified channel (in V/div) '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_vertical_scale(self, ich):
        ''' Get the vertical sensitivity of the specified channel (in V/div) '''
        raise NotImplementedError
    
    def get_vertical_range(self, ich):
        ''' Get vertical display range at current vertical scale (in V) '''
        return self.get_vertical_scale(ich) * self.NVDIVS
    
    def get_target_vertical_scale(self, ich, value, target_yrel=0.7, max_yrel=0.9):
        '''
        Determine target vertical scale (in V/div) division to accurately acquire a signal of specific amplitude
        
        :param ich: channel index
        :param value: target signal amplitude (in V)
        :param target_yrel: target relative amplitude for signal (default: 70% of full scale)
        :param max_yrel: maximum relative amplitude for signal (default: 90% of full scale)
        '''
        # Compute peak-to-peak range from signal amplitude
        p2pval = 2 * value
        # Get current vertical scale and peak-to-peak vertical range of oscilloscope
        vscale = self.get_vertical_scale(ich)
        vrange = self.get_vertical_range(ich)
        # Compute fraction of vertical range taken by signal
        p2pfrac = p2pval / vrange
        # If fraction exceeds max allowed fraction, double vertical scale
        if p2pfrac > max_yrel:
            logger.warning(f'target signal amplitude ({value:.3f} V) takes more than {max_yrel * 1e2:.0f} % of current vertical range ({vrange:.3f} V)')
            target_vscale = vscale * 2
        # Otherwise, adjust vertical scale to match target fraction
        else:
            target_vscale = vscale * p2pfrac / target_yrel
        # Clip output to valid range
        return np.clip(
            target_vscale, 
            self.MIN_VDIV, self.MAX_VDIV)

    def adjust_vertical_scale(self, ich, value, rtol=.1, **kwargs):
        '''
        Adjust vertical scale to accurately acquire a signal of specific amplitude
        
        :param ich: channel index
        :param value: target signal amplitude (in V)
        :param rtol: relative tolerance for vertical scale adjustment
        '''
        # Compute target vertical scale
        target_vdiv = self.get_target_vertical_scale(ich, value, **kwargs)
        # Get current vertical scale        
        vdiv = self.get_vertical_scale(ich)
        # Compute ratio of target vertical scale to current vertical scale
        vdiv_ratio = target_vdiv / vdiv
        # If ratio is outside of tolerance
        if not (1 - rtol) < vdiv_ratio < (1 + rtol):
            # If current vertical scale is already at limit, do nothing
            if vdiv == self.MIN_VDIV and (1 + rtol) < vdiv_ratio < 1.5:
                logger.debug('minimum vertical scale reached')
            elif vdiv == self.MAX_VDIV and (1 - rtol) > vdiv_ratio > 0.5:
                logger.debug('maximum vertical scale reached')
            # Otherwise, adjust vertical scale
            else:
                self.log(f'adjusting channel {ich} vertical range to detected signal amplitude ({value:.4f} V) -> vdiv = {target_vdiv:.3f} V/div')
                self.set_vertical_scale(ich, target_vdiv, verbose=False)
        return self.get_vertical_scale(ich)

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
    
    def set_filter(self, *args, **kwargs):
        logger.warning('no filter capabilities')
    
    def enable_filter(self, ich):
        logger.warning('no filter capabilities')

    def is_filter_enabled(self, ich):
        return False
    
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
    def set_single_trigger(self):
        ''' Set trigger mode to single acquisition '''
        raise NotImplementedError

    def set_normal_trigger(self):
        ''' Set trigger mode to normal '''
        self.set_trigger_mode('NORM')

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
        thalfrange = self.get_temporal_range() / 2
        if np.abs(value) > thalfrange:
            logger.warning(
                f'target temporal delay ({si_format(value, 2)}s) outside of current display temporal bounds (+/- {si_format(thalfrange, 2)}s) -> restricting')
            value = np.sign(value) * thalfrange
        return value
    
    @abc.abstractmethod
    def get_trigger_delay(self):
        ''' Get trigger delay (in s) '''
        raise NotImplementedError

    @abc.abstractmethod
    def set_trigger_delay(self, value):
        ''' Set trigger delay (in s) '''
        raise NotImplementedError
    
    def set_relative_trigger_delay(self, value):
        ''' Set trigger delay as a fraction of the current temporal scale '''
        tdiv = self.get_temporal_scale()
        self.set_trigger_delay(value * tdiv) 

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
    
    # --------------------- PARAMETERS ---------------------

    @abc.abstractmethod
    def get_parameter_value(self, ich, pkey):
        ''' Query the value of a parameter on a particular channel '''
        raise NotImplementedError
    
    # --------------------- WAVEFORMS ---------------------

    def set_waveform_settings(self, *args, **kwargs):
        ''' Set waveform settings '''
        pass

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
    
    def plot_waveform_data(self, *args, n=1, **kwargs):
        '''
        Acquire and plot waveform data
        
        :param n: number of acquisitions to plot
        :return: figure handle
        '''
        fig, ax = plt.subplots()
        for k in ['right', 'top']:
            ax.spines[k].set_visible(False)
        ax.set_xlabel('time (ms)')
        ax.set_ylabel('voltage (V)')
        ax.set_title('waveform data')
        for i in range(n):
            t, y = self.get_waveform_data(*args, **kwargs)
            ax.plot(t * 1e3, y, label=f'acq{i + 1}')
        ax.axvline(0, c='k', ls='--')
        ax.axhline(0, c='k', ls='--')
        if n > 1:
            ax.legend()
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
    
    # --------------------- MULTI-CHANNEL SETTING ---------------------

    def set_multichannel_vscale(self, vscales):
        ''' 
        Set vertical scales on multiple channels
        
        :param vscales: dictionary of (channel index: vertical scale) pairs. 
            Vertical scales should be provided in (V/div). If "TRIG" is provided 
            instead of a vertical scale, the channel vertical scale and trigger settings
            will be automatically adjusted to detect the default TTL pulse amplitude, and 
            the trigger soruce will be set to this channel. If no "TRIG" is provided, the
            first channel with a non-"TRIG" vertical scale will be set as the trigger source. 
        '''
        # Set "is_trigger_source_set" flag to False
        is_trigger_source_set = False

        # Loop over all input channels
        for ich, vscale in vscales.items():
            
            # If vscale is 'TRIG', set detection level to TTL / 2 and 
            # set trigger source to this channel
            if isinstance(vscale, str):
                if vscale.upper() == 'TRIG':
                    vscale = TTL_PAMP // 2
                    self.set_trigger_level(ich, vscale)
                    self.set_trigger_source(ich)
                    is_trigger_source_set = True
                else:
                    raise VisaError(f'invalid vscale value: {vscale}')

            # Otherwise, if trigger source is not set, assign it to this channel 
            elif not is_trigger_source_set:
                self.set_trigger_source(ich)
                is_trigger_source_set = True

            # In any case, set the vertical scale
            self.set_vertical_scale(ich, vscale)

