# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-08-08 10:11:50
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-11 09:28:01

import os
import time
from enum import Enum
from tqdm import tqdm
import numpy as np
import PyCapture2

from .logger import logger
from .constants import *


# Constants
SOFTWARE_TRIGGER = 0x62C
FIRE_VAL = 0x80000000
TRIGGER_INQ = 0x530
CAMERA_POWER = 0x610
POWER_VAL = 0x80000000
CRITICAL_BITRATE = 100  # Critical bitrate (in kb/s) for H264 writing above which some frames are lost
DEFAULT_BITRATE = 80  # Default bitrate (in kb/s) for H264 writing
DEFAULT_JPEG_COMPRESSION = 75  # Default JPEG compression quality (0-100) for MPEG encoding
SHUTTER_TO_FRAME_INTERVAL_RATIO = 0.9  # Ratio of shutter to frame interval to ensure acquisition at specified FPS
CHECK_INTERVAL = 1.  # Interval at which the camera checks for acquisition of interruption (in s)


class TriggerMode(Enum):
    ''' Descriptors of camera trigger modes '''
    STANDARD = 0  # Acquisition starts on trigger and lasts 1 shutter exposure time
    BULB = 1  # Acquisition starts on trigger and lasts trigger width
    SKIP_FRAMES = 3  # Same as STANDARD, but camera transmits 1 out of N frames
    MULTI_EXP_PRESET = 4  # Image readout starts after N expositions lasting each 1 shutter exposure time
    MULTI_EXP_WITDH = 5  # Image readout starts after N expositions lasting each 1 trigger width
    LOW_SMEAR = 13  # Same as STANDARD, but exposure is preceded by CCD fast dump in order to reduce the time each pixel data collects smear
    OVERLAPPED_EXP = 14  # Same as STANDARD, but allows triggering at faster frame rates
    MULTI_SHOT = 15  # Acquire a stream of N images (exposure determined by shutter) upon trigger


class TriggerSource(Enum):
    ''' Descriptors of camera trigger sources '''
    EXTERNAL = 2  # GPIO 2 pin (to adapt to connectics)
    SOFTWARE = 7  # Software


class VideoFormat(Enum):
    ''' Descriptors of video formats '''
    AVI = 0
    MJPG = 1
    H264 = 2


class GrabMode(Enum):
    ''' Descriptors of grab modes '''
    BUFFER_FRAMES = 1
    DROP_FRAMES = 0
    UNSPECIFIED_GRAB_MODE = 2


class CameraError(Exception):
    pass


def log_build_info():
    ''' Log PyCapture build info '''
    lib_ver = PyCapture2.getLibraryVersion()
    logger.info(
        f'PyCapture2 library version: {lib_ver[0]}.{lib_ver[1]}.{lib_ver[2]}.{lib_ver[3]}')


def grab_camera():
    ''' Grab the first detected camera '''
    # Get camera BUS Manager
    bus = PyCapture2.BusManager()
    # Extract number of connected cameras
    ncams = bus.getNumOfCameras()
    # If no camera connected, raise error 
    if ncams == 0:
        raise CameraError(
            'No camera detected. Make sure your camera is connected via a USB3 port')
    # Select camera on 0th index
    cam = Camera()
    cam.connect(bus.getCameraFromIndex(0))
    # Return cam object
    return cam


class Camera(PyCapture2.Camera):
    ''' Interface to FLIR Camera '''

    def __init__(self, *args, **kwargs):
        '''
        Constructor
        
        :param cam: camera object
        '''
        super().__init__(*args, **kwargs)
        self.is_capturing = False
        self.video_stream = None
        self.video_name = None
    
    @property
    def settings(self):
        ''' Get camera settings dictionary '''
        cam_info = self.getCameraInfo()
        return {
            'Serial number' : cam_info.serialNumber,
            'Camera model' : cam_info.modelName.decode('utf-8'),
            'Camera vendor' : cam_info.vendorName.decode('utf-8'),
            'Sensor' : cam_info.sensorInfo.decode('utf-8'),
            'Resolution' : cam_info.sensorResolution.decode('utf-8'),
            'Firmware version' : cam_info.firmwareVersion.decode('utf-8'),
            'Firmware build time' : cam_info.firmwareBuildTime.decode('utf-8'),
            'Frame dimensions': f'{self.ncols} x {self.nrows}',
            'Frame rate': f'{self.get_framerate()} FPS'
        }
    
    def __str__(self):
        ''' String representation: camera model '''
        return self.settings['Camera model']
    
    def connect(self, guid):
        ''' 
        Connect to camera object

        :param guid: Global Unique IDentifier for the camera physical object 
        '''
        logger.info(f'connecting to camera with GUID {guid} ...')
        super().connect(guid)
        # Get frame dimensions 
        self.get_frame_dimensions()
        # Set shutter time < 1 / FPS to enable stable capture at FPS
        self.set_shutter(SHUTTER_TO_FRAME_INTERVAL_RATIO / self.get_framerate() * S_TO_MS)
        # Log settings
        self.log_settings()

    def disconnect(self):
        logger.info(f'disconnecting from {self} camera')
        super().disconnect()

    def log_settings(self):
        ''' Log camera settings '''
        cam_info_str = '\n'.join([f'   - {k}: {v}' for k, v in self.settings.items()])
        logger.info(f'*** CAMERA SETTINGS ***\n{cam_info_str}')
    
    @property
    def config(self):
        ''' Camera configuration '''
        config_prop = self.getConfiguration()
        keys = [
            'asyncBusSpeed ',
            'bandwidthAllocation ', 
            'grabMode ',
            'grabTimeout ', 
            'isochBusSpeed ', 
            'minNumImageNotifications ', 
            'numBuffers ', 
            'numImageNotifications ', 
            'registerTimeout', 
            'registerTimeoutRetries ']
        config_dict = {k.strip(): getattr(config_prop, k) for k in keys}
        config_dict['grabMode'] = GrabMode(config_dict['grabMode'])
        return config_dict

    def log_config(self):
        ''' Log camera configuration '''
        cam_config_str = '\n'.join([f'   - {k}: {v}' for k, v in self.config.items()])
        logger.info(f'*** CAMERA CONFIGURATION ***\n{cam_config_str}')

    def get_grabmode(self):
        '''
        Get frames grab mode
        
        :return: GrabMode enum
        '''
        return self.config['grabMode']
    
    def set_grabmode(self, grabmode):
        ''' 
        Set frames grab mode
        
        :param grabmode: GrabMode enum
        '''
        self.setConfiguration(grabMode=grabmode.value)

    def get_grabtimeout(self):
        ''' 
        Get timeout that will wait for an image before timing out and returning.

        :return: timeout (ms)
        '''
        return self.config['grabTimeout']
    
    def set_grabtimeout(self, timeout=None):
        ''' 
        Set timeout that camera will wait for an image before timing out and returning.

        :param timeout: timeout (ms)
        '''
        if timeout is None: # no timeout case
            timeout = -1
        self.setConfiguration(grabTimeout=timeout)

    def get_framerate(self):
        ''' Get the camera frame rate (in fps) '''
        return self.getProperty(PyCapture2.PROPERTY_TYPE.FRAME_RATE).absValue
    
    def set_framerate(self, fps):
        ''' Set the camera frame rate (in fps) '''
        raise CameraError('Acquisition frame rate cannot be set at the moment')
        # self.setProperty(type=PyCapture2.PROPERTY_TYPE.FRAME_RATE, absValue=fps)

    def get_shutter(self):
        ''' Get camera shutter exposure time (in ms) '''
        return self.getProperty(PyCapture2.PROPERTY_TYPE.SHUTTER).absValue
    
    def set_shutter(self, shutter):
        ''' Set camera shutter exposure time (in ms) '''
        # Ensure that shutter time is compatible with camera frame rate
        fps = self.get_framerate()  # Hz
        if shutter > S_TO_MS / fps:
            raise CameraError(
                f'target shutter time ({shutter:.2f} ms) exceeds inter-frame interval ({S_TO_MS / fps:.2f} ms)')
        logger.info(f'setting shutter time to {shutter:.2f} ms ...')
        self.setProperty(type=PyCapture2.PROPERTY_TYPE.SHUTTER, absValue=shutter)
        s = self.get_shutter()
        logger.info(f'shutter time set to {s:.2f} ms')

    def get_exposure(self):
        ''' Get the automatically adjusted exposure value of the camera '''
        return self.getProperty(PyCapture2.PROPERTY_TYPE.AUTO_EXPOSURE).absValue
    
    def get_temperature(self):
        ''' Get the camera temperature (in dwegrees Celsius) '''
        return self.getProperty(PyCapture2.PROPERTY_TYPE.TEMPERATURE).absValue * 100 - CELSIUS_TO_KELVIN
    
    def get_frame_dimensions(self):
        ''' Get frame dimensions (in pixels) '''
        logger.info('getting frames dimensions...')
        self.disable_trigger(verbose=False)
        self.startCapture(verbose=False)
        img = self.grab_frame()
        self.ncols, self.nrows = img.getCols(), img.getRows()
        self.stopCapture(verbose=False)
    
    def get_format7_settings(self):
        ''' Get format7 settings '''
        fmt7_info, supported = self.getFormat7Info(0)
        return {
            'Supported': supported,
            'Max image pixels': (fmt7_info.maxWidth, fmt7_info.maxHeight),
            'Image unit size': (fmt7_info.imageHStepSize, fmt7_info.imageVStepSize),
            'Offset unit size': (fmt7_info.offsetHStepSize, fmt7_info.offsetVStepSize),
            'Pixel format bitfield': fmt7_info.pixelFormatBitField,
        }
    
    def log_format7_settings(self):
        ''' Log format7 settings '''
        fmt7_settings_dict = self.get_format7_settings()
        fmt7_str = '\n'.join([f'   - {k}: {v}' for k, v in fmt7_settings_dict.items()])
        logger.info(f'*** FORMAT7 SETTINGS ***\n{fmt7_str}')

    def get_image_settings(self):
        ''' Get image settings information dictionary '''
        img_settings, packet_size, pct = self.getFormat7Configuration()
        keys = ['mode', 'width', 'height', 'offsetX', 'offsetY', 'pixelFormat']
        img_settings_dict = {k: getattr(img_settings, k) for k in keys}
        img_settings_dict['packetSize'] = packet_size
        img_settings_dict['packetSizePct'] = pct
        return img_settings_dict

    def log_image_settings(self):
        ''' Log image settings '''
        image_settings_dict = self.get_image_settings()
        image_str = '\n'.join([f'   - {k}: {v}' for k, v in image_settings_dict.items()])
        logger.info(f'*** IMAGE SETTINGS ***\n{image_str}')

    def power_up(self, nretries=10, sleeptime=.1):
        ''' 
        Power up camera

        :param nretries: number of power-up
        :param sleeptime: sleeping time between each attempt (s)
        '''
        # Waiting for Camera to power up
        self.writeRegister(CAMERA_POWER, POWER_VAL)
        for i in range(nretries):
            time.sleep(sleeptime)
            # Camera might not respond to register reads during powerup.
            try:
                reg_val = self.readRegister(CAMERA_POWER)
            except PyCapture2.Fc2error:
                pass
            awake = True
            if reg_val == POWER_VAL:
                break
            awake = False
        if not awake:
            raise CameraError(f'could not wake {self}.')

    def startCapture(self, verbose=True, **kwargs):
        ''' Start video capture and wait for frames to arrive '''
        if verbose:
            logger.info('starting capture')
        super().startCapture(**kwargs)
        self.is_capturing = True
    
    def stopCapture(self, verbose=True):
        ''' Stop video capture '''
        if verbose:
            logger.info('stopping capture')
        super().stopCapture()
        self.is_capturing = False
        # Close video stream and remove incomplete files if they exist
        if self.video_stream is not None:
            logger.info('closing video stream')
            self.video_stream.close()
            if os.path.isfile(self.video_name):
                logger.info(f'deleting incomplete video file {self.video_name}')
                os.remove(self.video_name)
            self.video_stream = None
            self.video_name = None
    
    def grab_frame(self, verbose=False):
        ''' 
        Wrapper around retrieveBuffer that enables checking for camera status
        at regular time intervals (set by grab timeout)
        
        :param verbose: whether to log grab attempts or not
        :return: image object
        '''
        # Execute only if camera acquisition is enabled
        if self.is_capturing:
            # Try to retrieve frame from buffer
            try:
                return self.retrieveBuffer()
            # If PyCapture2 raises error
            except PyCapture2.Fc2error as err:
                # If timeout error, keep trying within recursive call
                if str(err)[2:-2] == 'Timeout error':
                    if verbose:
                        logger.info('camera timed out, re-trying to capture frame ...')
                    return self.grab_frame(verbose=verbose)
                # Otherwise, disable capturing and raise error
                else:
                    self.stopCapture()
                    raise err
       
    def check_software_trigger_presence(self):
        ''' Check if asnychronous trigger is implemented on camera '''
        if self.readRegister(TRIGGER_INQ) & 0x10000 != 0x10000:
            raise (f'SOFT_ASYNC_TRIGGER is not implemented on {self}')
    
    def get_trigger_settings(self):
        ''' Get camera trigger settings dictionary '''
        trigger_settings = self.getTriggerMode()
        trigger_keys = ['mode', 'onOff', 'parameter', 'polarity', 'source']
        trigger_settings_dict = {k: getattr(trigger_settings, k) for k in trigger_keys}
        trigger_settings_dict['mode'] = str(TriggerMode(trigger_settings_dict['mode']))
        trigger_settings_dict['source'] = str(TriggerSource(trigger_settings_dict['source']))
        return trigger_settings_dict

    def log_trigger_settings(self):
        ''' Log camera trigger settings '''
        trigger_settings_dict = self.get_trigger_settings()
        trigger_str = '\n'.join([f'   - {k}: {v}' for k, v in trigger_settings_dict.items()])
        logger.info(f'*** TRIGGER SETTINGS ***\n{trigger_str}')
  
    def set_trigger_settings(self, trigger=True, nframes=0, mode=TriggerMode.MULTI_SHOT,
                             source=TriggerSource.SOFTWARE, verbose=True):
        ''' 
        Configure camera trigger settings
        
        :param trigger: whether to configure the camera to be triggered or not 
        :param nframes: number of frames to capture on trigger (default = infinite)
        :param mode: integer indicating the trigger mode (default = multi-shot)
        :param source: trigger source mode (default = software trigger)
        '''
        # Get trigger settings property
        trigger_settings = self.getTriggerMode()
        # Set trigger ON/OFF
        trigger_settings.onOff = trigger
        # If trigger set to ON, set other properties
        if trigger:
            trigger_settings.mode = mode.value
            trigger_settings.parameter = nframes
            # If trigger source set to software, check that it is enabled on camera
            if source == TriggerSource.SOFTWARE:
                self.check_software_trigger_presence()
            trigger_settings.source = source.value
        # Set trigger settings property
        self.setTriggerMode(trigger_settings)
        if verbose:
            self.log_trigger_settings()
        # If trigger source is software, poll until ready for software trigger
        if trigger and source == TriggerSource.SOFTWARE:
            self.poll_for_software_trigger()

    def wait_for_trigger(self, **kwargs):
        ''' Wrapper around set_trigger_settings with trigger enabled '''
        self.set_trigger_settings(trigger=True, **kwargs)
    
    def disable_trigger(self, **kwargs):
        ''' Wrapper around set_trigger_settings with trigger disabled '''
        self.set_trigger_settings(trigger=False, **kwargs)

    def poll_for_software_trigger(self):
        ''' Poll until the camera is ready for a software trigger '''
        while True:
            reg_val = self.readRegister(SOFTWARE_TRIGGER)
            if not reg_val:
                break
        logger.info(f'{self} is ready for software trigger.')

    def fire_software_trigger(self):
        ''' Fire a software trigger '''
        self.writeRegister(SOFTWARE_TRIGGER, FIRE_VAL)
    
    def open_video_file_stream(self, filename, fmt=VideoFormat.H264, 
                               bitrate=DEFAULT_BITRATE, jpeg_compression=75):
        '''
        Open video stream to file
        
        :param fname: name of file to stream to
        :param fmt: video format (default = H264)
        :param bitrate: H264 bitrate in kb/s (default = 200)
        :param jpeg_compression: JPEG compression quality (1-100, default = 75)
        :return: video stream object
        '''
        # Convert filename to UTF8
        fname = filename.encode('utf-8')
        # Get camera frame rate
        fps = self.get_framerate()
        # Create video object and appropriate file stream
        video = PyCapture2.FlyCapture2Video()
        if fmt == VideoFormat.AVI:
            video.AVIOpen(fname, fps)
        elif fmt == VideoFormat.MJPG:
            video.MJPGOpen(fname, fps, jpeg_compression)
        elif fmt == VideoFormat.H264:
            if bitrate > CRITICAL_BITRATE:
                raise CameraError(
                    f'specified H.264 encoding bitrate ({bitrate} kb/s) will likely induce some frame loss')
            video.H264Open(fname, fps, self.ncols, self.nrows, bitrate * KBS_TO_BS)
        else:
            raise CameraError(f'{fmt} video format not available.')
        return video

    def save_video_to_file(self, filename, nframes, verbose=False, **kwargs):
        '''
        Save current video acquisition to file
        
        :param filename: output filename
        :param nframes: number of frames to save 
        '''
        # Open video stream to output file
        self.video_stream = self.open_video_file_stream(filename, **kwargs)
        self.video_name = filename
        # Log start
        logger.info(f'saving {nframes} frames to {filename} ...')
        # Loop until all frames have been acquired
        ngrabbed = 0
        pbar = None
        while ngrabbed < nframes:
            try:
                # Grab frame
                img = self.grab_frame(verbose=verbose)
                # Append image to video stream (only if True image object was returned)
                if img is not None:
                    self.video_stream.append(img)
                # On first frame, create progress bar and set acquisition start
                if pbar is None:
                    tstart = time.perf_counter()
                    pbar = tqdm(total=nframes)
                # Increment progress bar and ngrabbed counter
                ngrabbed += 1
                pbar.update()
            except PyCapture2.Fc2error as fc2Err:
                logger.error(f'error retrieving buffer: {str(fc2Err)}')
                continue
        # Close progress bar and stop acquisition time
        tacq = time.perf_counter() - tstart
        pbar.close()
        # Log acquisition time
        logger.info(f'acquisition time: {tacq:.2f} s')
        # Close video object
        self.video_stream.close()
        self.video_stream = None
        self.video_name = None

    def acquire(self, filename, duration, nacqs=1, 
                trigger_source=TriggerSource.SOFTWARE, verbose=False, **kwargs):
        '''
        Acquire video(s) and save to file(s)
        
        :param filename: output filename(s)
        :param duration: duration of each acquisition (in s)
        :param nacqs: number of successive acquisitions
        :param trigger source: trigger source (default = software)
        '''
        # Determine output file names
        if nacqs > 1:
            root, ext = os.path.splitext(filename)
            fnames = [f'{root}_{i + 1:05}{ext}' for i in range(nacqs)]
        else:
            fnames = [filename]
        # Determine number of frames to save according to specified duration & FPS
        nframes = int(np.ceil(duration * self.get_framerate()))
        # Ensure full capture even in case of frame loss
        nframes_capture = nframes # int(np.ceil(nframes * 1.1))  
        logger.info(f'number of frames per acquisition: {nframes}')
        # Set frames grabbing settings
        self.set_grabtimeout(CHECK_INTERVAL * S_TO_MS)
        self.set_grabmode(GrabMode.BUFFER_FRAMES)
        # Wait for appropriate trigger
        self.wait_for_trigger(nframes=nframes_capture, source=trigger_source)
        # For each acquisition
        for iacq, fname in enumerate(fnames):
            # Start capture (& open buffer)
            self.startCapture(verbose=verbose)
            # If trigger source set to software, fire trigger
            if trigger_source == TriggerSource.SOFTWARE:
                self.fire_software_trigger()
            # Acquire video and save to file
            logger.info(f'starting acqusition {iacq + 1}/{nacqs}')
            self.save_video_to_file(fname, nframes, verbose=verbose, **kwargs)
            # Stop capture (& clear buffer)
            self.stopCapture(verbose=verbose)
    