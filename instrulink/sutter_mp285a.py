# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-04-27 18:16:34
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-11 16:03:27

import serial
import struct
import time
import numpy as np

from .logger import logger
from .utils import is_within


class SutterError(Exception):
    ''' Custom exception class for Sutter instrument '''
    pass


class SutterMP285A:
    '''' Interface to communicate with Sutter Manipulator 285 '''

    PORT = 'COM2'  # Default port
    BAUDRATE = 9600  # Default baud rate
    INTERCOMMAND_DELAY = 2e-3  # internal delay between commands (s)
    ENC = 'utf-8'
    CR = bytes('\r', ENC)
    XYZ_FMT = 'lll'
    XYZ_LEN = 12  # length (in bytes) of XYZ position
    XYZ_BOUNDS = (-12500, 12500)  # Bounds for XYZ coordinates (um)
    XYZ_TOL = 0.5  # XYZ tolerance (um)
    TREL_MAX = 0.7  # maximal relative move duration w.r.t. timeout duration
    TREL_WARN = 1.8  # critical relative move duration w.r.t. estimate above which to throw a warning
    LOW_RES_SPEED_BOUNDS = (0, 3000)  # Coarse mode travel speed bounds (um/s)
    HIGH_RES_SPEED_BOUNDS = (0, 1310)  # Fine mode travel speed bounds (um/s)
    STATUS_LEN = 32  # length (in bytes) of status information
    STATUS_FIELDS = {
        'FLAGS': 'B',  # Program flags
        'UDIRX': 'B',  # User-defined values for motor axis X
        'UDIRY': 'B',  # User-defined values for motor axis Y
        'UDIRZ': 'B',  # User-defined values for motor axis Z
        'ROE_VARI': 'H',  # u-steps per ROE click
        'UOFFSET': 'H',  # User-defined period start value
        'URANGE': 'H',  # User-defined period range
        'PULSE': 'H',  # Number of u-steps per pulse
        'USPEED': 'H',  # Adjusted pulse speed (u-steps/s)
        'INDEVICE': 'B',  # Input device type
        'FLAGS_2': 'B',  # Program flags
        'JUMPSPD': 'H',  # "Jump to max at" speed
        'HIGHSPD': 'H',  # "Jumped to" speed
        'DEAD': 'H',  # Dead zone, not saved
        'WATCH_DOG': 'H',  # programmer's function
        'STEP_DIV': 'H',  # Divisor yields (u-steps/um)
        'STEP_MUL': 'H',  # Multiplier yields (um/u-steps)
        'XSPEED': 'H',  # Remote speed (um/s) & res. (bit 15)
        'VERSION': 'H'  # Firmware version
    }
    FLAGS_FIELDS = {
        'SETUP': [0, 1, 2, 3],  # Currently loaded setup number.
        'ROE_DIR': 4,  # ROE direction
        'REL_ABS_F': 5,  # Display origin
        'MODE_F': 6,  # Manual mode
        'STORE_F': 7  # Setup condition
    }
    FLAGS_2_FIELDS = [
        'LOOP_MODE',  # Program loops
        'LEARN_MODE',  # Learn mode status
        'STEP_MODE',  # Movement resolution
        'SW2_MODE',  # Enable joy side button
        'SW1_MODE',  # Enable FSR/Joystick
        'SW3_MODE',  # Enable ROE switch
        'SW4_MODE',  # Enable SW 4&5
        'REVERSE_IT',  # Reverse program
    ]
    BIT15 = 2**15  # Bit 15 position value

    def __init__(self, timeout=10., lock=False):
        '''
        Initialization

        :param timeout: commands timeout (s)
        :param lock: whether to lock the instrument during motion (not implemented)
        '''
        self.connect()
        self.timeout = timeout
        self.set_absolute_mode()
        self.update_status()
        self.set_resolution(1)
        self.set_velocity(self.HIGH_RES_SPEED_BOUNDS[1])
    
    def __repr__(self):
        ''' String representation '''
        return f'{self.__class__.__name__}({self.instrument_handle.port})'
    
    def connect(self):
        ''' Attempt serial connection to controller '''
        try:
            self.instrument_handle = serial.Serial(
                port=self.PORT,
                baudrate=self.BAUDRATE,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE)
            print(f'{f" {repr(self)} ":-^100}')
            
        except serial.SerialException:
            self.instrument_handler = None
            raise SutterError(
                f'No connection to {self.__class__.__name__} could be established')
    
    def disconnect(self):
        ''' Disconnect from controller '''
        logger.info(f'disconnecting from {self}')
        self.instrument_handle.close()
        self.instrument_handle = None

    @property
    def is_connected(self):
        ''' Whether the instrument is connected '''
        return self.instrument_handle is not None
    
    @property
    def timeout(self):
        ''' Timeout (s) '''
        return self.instrument_handle.timeout
    
    @timeout.setter
    def timeout(self, value):
        ''' Set timeout (s) '''
        self.instrument_handle.timeout = value

    # def __del__(self):
    #     logger.info(f'releasing {repr(self)} resource')
    #     self.instrument_handle.close() 

    def get_name(self):
        ''' Get controller name '''
        return self.__class__.__name__
    
    def write(self, cmd, convert_to_bytes=True):
        ''' Write a command into the serial instrument '''
        logger.debug(f'WRITE: {cmd}')
        if convert_to_bytes:
            cmd = bytes(cmd, self.ENC)
        self.instrument_handle.write(cmd + self.CR)
        time.sleep(self.INTERCOMMAND_DELAY)
    
    def read(self, n):
        '''
        Read a specific number of bytes from the instrument response
        
        :param n: number of bytes to read
        :return: response bytes sequence
        '''
        return self.instrument_handle.read(n)
    
    def read_until_CR(self, lexp=None):
        '''
        Read instrument response until carriage return character
        
        :param lexp (optional): expected response length (number of bytes)
        :return: response bytes sequence
        '''
        out = self.instrument_handle.read_until(self.CR)[:-1]
        if lexp is not None:
            if len(out) != lexp:
                raise SutterError(f'expected {lexp}-bytes long response, got {len(out)} bytes')
        return out
    
    def write_and_check(self, cmd, **kwargs):
        '''
        Execute "set" type command and check for correct execution
        
        :param cmd: command string
        '''
        tstart = time.time()  # start timer
        self.write(cmd, **kwargs)  # send "set" command to controller
        out = self.read(1)  # read output
        tend = time.time()  # stop timer
        if out != self.CR:  # check that output is expected
            raise SutterError(
                f'command {cmd} did not complete before timeout ({self.timeout} s)')
        logger.debug(f'completed in {tend - tstart:.2f} s')
    
    @property
    def status_fmt(self):
        ''' Format of the status fields for unpacking '''
        return ''.join(self.STATUS_FIELDS.values())
    
    def get_status(self):
        '''
        Query the status of the controller.
        
        :return: status data dictionary
        '''
        # Query status data
        self.write('s')
        # Read status data block
        status_data_block = self.read_until_CR(lexp=self.STATUS_LEN)
        # Unpack block and format into dictionary
        status_data = struct.unpack(self.status_fmt, status_data_block)
        status_data = dict(zip(self.STATUS_FIELDS.keys(), status_data))
        # Post-process specific fields
        status_data['VERSION'] /= 100  # divide version by 100
        status_data['STEP_MUL'] = 10000 / status_data['STEP_MUL']  # convert step_mul to u-steps/um
        status_data['STEP_DIV'] /= 10000  # convert step_div to um/u-steps
        if status_data['XSPEED'] >= self.BIT15:  # if high resolution
            status_data['SPEED_RES'] = 1  # set resolution to high
            status_data['XSPEED'] = status_data['XSPEED'] - self.BIT15  # correct speed
        else:
            status_data['SPEED_RES'] = 0  # set resolution to low
        # Log dict
        status_str = '\n'.join([f'  - {k}: {v}' for k, v in status_data.items()])
        logger.debug(f'status data:\n{status_str}')
        return status_data

    def update_status(self):
        ''' Update controller status '''
        self.status_data = self.get_status()
    
    @property
    def usteps_per_um(self):
        ''' Get u-steps per um '''
        return self.status_data['STEP_MUL']

    def encode_position(self, pos, prefix=None):
        '''
        Encode an XYZ position into bytes
        
        :param pos: position vector (in um)
        '''
        # Convert to u-steps and integers
        pos_usteps = (pos * self.usteps_per_um).astype(int)
        # Pack and return
        bpos = struct.pack(self.XYZ_FMT, *pos_usteps)
        if prefix is not None:
            bpos = bytes(prefix, self.ENC) + bpos
        return bpos

    def decode_position(self):
        '''
        Read and decode an XYZ position
        
        :return: position vector (in um)
        '''
        # Read binary position from controller
        bpos = self.read(self.XYZ_LEN + 1)[:-1]
        # bpos = self.read_until_CR(lexp=self.XYZ_LEN)
        # Decode u-steps position
        pos_usteps = np.array(struct.unpack(self.XYZ_FMT, bpos))
        # Convert to um and return
        return pos_usteps / self.usteps_per_um  # um
    
    def pos_str(self, pos):
        ''' Return a string representation of a position vector '''
        pos_str = ', '.join([f'{x:.2f}' for x in pos])
        return f'[{pos_str}] um'
    
    def get_position(self, verbose=False):
        '''
        Get controller XYZ position (in um)
        
        :return: 1D (X, Y, Z) array (um)
        '''
        # Send commend to get position
        self.write('c')
        # Read position from controller
        pos = self.decode_position()
        logfunc = logger.info if verbose else logger.debug
        logfunc(f'stage position: {self.pos_str(pos)}')
        return pos
    
    def check_coordinate(self, k, v):
        ''' Check that coordinate is within bounds '''
        if not is_within(v, self.XYZ_BOUNDS):
            raise SutterError(f'target {k} coordinate {v:.3f} um is out of bounds {self.XYZ_BOUNDS}')
    
    def check_coordinates(self, cdict):
        ''' Check a dictionary of coordinates '''
        for k, v in cdict.items():
            self.check_coordinate(k, v)
    
    def set_position(self, pos, silent=False):
        '''
        Moves the three axes to specified location (in um).
        
        :param pos: 1D (X, Y, Z) array (um)
        :param silent: whether to log the move
        '''
        # Check validity of target position
        pos = np.asarray(pos)
        if pos.size != 3:
            raise SutterError('input position must be of length 3')
        self.check_coordinates(dict(zip('XYZ', pos)))
        # Compute delta to target
        current_pos = self.get_position()
        delta = pos - current_pos
        dtot = np.linalg.norm(delta)
        # If total distance is zero (no delta), return
        if dtot == 0:
            logger.warning('already at position!')
            return
        # Check if velocity will allow to move there before timeout
        v = self.get_velocity()  # um/s
        tmove_est = dtot / v # s
        # If not, check required speed to achieve it in percentage of timeout
        tcr = self.TREL_MAX * self.timeout
        vreq = None
        if tmove_est > self.timeout:
            vreq = int(np.round(dtot / tcr))
            logger.warning(
                f'increasing velocity temporarily to {vreq} um/s to cover {dtot:.2f} um within {self.TREL_MAX * 1e2:.0f} % of {self.timeout} s timeout')
            self.set_velocity(vreq)
        if not silent:
            logger.info(f'moving to position: {self.pos_str(pos)} (delta = {self.pos_str(delta)})')
        bpos = self.encode_position(pos, prefix='m')  # encode position to bytes
        tmove = time.perf_counter()
        self.write_and_check(bpos, convert_to_bytes=False)  # send position to controller
        tmove = time.perf_counter() - tmove
        # Check that target position has been reached
        new_pos = self.get_position()
        new_delta = pos - new_pos
        if np.sum(np.abs(new_delta)) > self.XYZ_TOL:
            raise SutterError(f'could not reach target position {self.pos_str(pos)} (value = {self.pos_str(new_pos)})')
        if tmove > max(50e-3, self.TREL_WARN * tmove_est):
            logger.warning(f'{delta} move took {tmove * 1e3:.3f} ms ({tmove / tmove_est:.2f} times expected time)')
        if vreq is not None:
            logger.warning(f'resetting velocity to {v} um/s')
            self.set_velocity(v)
    
    def move_to_origin(self):
        ''' Move to origin '''
        self.set_position([0., 0., 0.])
        logger.info('moved to origin!')
    
    def translate(self, v, **kwargs):
        '''
        Translate by some vector
        
        :param v: XYZ translation vector (um) '''
        pos = self.get_position()
        self.set_position(pos + np.asarray(v), **kwargs)
    
    def get_velocity(self, verbose=False):
        ''' Get controller motion velocity (um/s) '''
        v = self.status_data['XSPEED']
        logfunc = logger.info if verbose else logger.debug
        logfunc(f'velocity = {v} um/s')
        return v
    
    def get_resolution(self, verbose=False):
        ''' Get controller motion resolution (0 or 1) '''
        res = self.status_data['SPEED_RES']
        logfunc = logger.info if verbose else logger.debug
        logfunc(f'motion mode: {self.res_str(res)}')
        return res
    
    def encode_velocity_and_resolution(self, v, res):
        '''
        Encode velocity and resolution
        
        :param v: target velocity (um/s)
        :param res: resolution (0 or 1)
        '''
        # Encode speed and resolution into single integer
        vres = int(v) + res * self.BIT15
        # Convert to unsigned short (2 bytes)
        bvres = struct.pack('H', vres)
        # Send command and check response
        self.write_and_check(bytes('V', self.ENC) + bvres, convert_to_bytes=False)
        self.update_status()

    def get_vbounds(self, res):
        '''
        Determine velocity bounds depending on resolution
        
        :param res: resolution (0 or 1)
        :return: velocity bounds
        '''
        if res:
            return self.HIGH_RES_SPEED_BOUNDS
        else:
            return self.LOW_RES_SPEED_BOUNDS
        
    def set_velocity(self, v):
        ''' 
        Set controller motion velocity (um/s)
        
        :param v: target velocity (um/s)
        '''
        # Check that velocity is within bounds
        res = self.get_resolution()
        vbounds = self.get_vbounds(res)
        if not is_within(v, vbounds):
            raise SutterError(
                f'velocity value ({v} um/s) is out of specific bounds ({vbounds} um/s)')
        logger.info(f'setting velocity to {v} um/s')
        self.encode_velocity_and_resolution(v, res)
        vout = self.get_velocity()
        if vout != v:
            raise SutterError(f'could not set motion speed to {v} um/s (value = {vout} um/s)')
    
    def res_str(self, res):
        ''' Return a string representation of controller movement resolution '''
        resmode = {0: 'low', 1: 'high'}[res]
        return f'{resmode}-resolution'
    
    def set_resolution(self, res):
        ''' Set controller motion resolution (0 for low or 1 for high) '''
        logger.info(f'setting motion mode to {self.res_str(res)}')
        self.encode_velocity_and_resolution(self.get_velocity(), res)
        resout = self.get_resolution()
        if resout != res:
            raise SutterError(f'could not set motion mode to {self.res_str(res)} (value = {self.res_str(resout)})')

    def refresh_panel(self):
        ''' Refresh XYZ info on the front panel '''
        self.write_and_check('n')
    
    def set_origin(self):
        ''' Set origin of the coordinate system to the current position '''
        self.write_and_check('o')
        logger.info('origin reset!')
    
    def reset(self):
        ''' Reset controller '''
        self.write('r')  # controller does not reply
    
    def set_absolute_mode(self):
        ''' Set the movement mode to absolute '''
        logger.info('setting absolute movement mode')
        self.write_and_check('a')
    
    def set_relative_mode(self):
        ''' Set the movement mode to relative '''
        logger.info('setting relative movement mode')
        self.write_and_check('b')
