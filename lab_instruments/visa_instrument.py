# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-15 09:26:06
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-04-25 14:57:48

import abc
import pyvisa
import time
import re
import threading

from .logger import logger


class VisaError(Exception):
    ''' Custom exception class for VISA instrument '''
    pass


class VisaInstrument(metaclass=abc.ABCMeta):
    ''' Generic interface to a VISA instrument using the SCPI command interface '''

    PREFIX = ''
    _lock = threading.Lock()

    def __init__(self, testmode=False, lock=False):
        ''' Initialization. '''
        self.instrument_handle = None
        self.testmode = testmode
        self.lock = lock
        if not testmode:
            self.connect()

    def __repr__(self):
        ''' String representation '''
        return f'{self.__class__.__name__}: {self.get_idn()}'

    def __del__(self):
        ''' Destruction. '''
        if self.is_connected():
            logger.info(f'releasing {self.__class__.__name__} resource')
    
    # --------------------- MISCELLANEOUS ---------------------

    def connect(self):
        ''' Connect to instrument. '''
        # Detect instrument and store its handle
        rm = pyvisa.ResourceManager()
        resources = rm.list_resources()
        if len(resources) == 0:
            raise VisaError('no instrument detected')
        res_id = next((item for item in resources if re.search(self.USB_ID, item) is not None), None)
        if res_id is None:
            res_str = '\n'.join([f'  - {r}' for r in resources])
            raise VisaError(
                f'instrument ID "{self.USB_ID}" not detected in USB resources:\n{res_str}.\
                \nPlease check the USB connection or update the instrument USB ID.')
        self.instrument_handle = rm.open_resource(res_id)
        # Reset instrument, clear error queue and disable all outputs
        self.reset()
        self.clear()
        print(f'{f" {repr(self)} ":-^100}')

    def disconnect(self):
        ''' Disconnect from instrument. '''
        self.instrument_handle = None

    def is_connected(self):
        ''' Check if instrument is connected. '''
        return self.instrument_handle is not None
    
    def process_text(self, text):
        if not text.startswith('*'):
            return f'{self.PREFIX}{text}'
        return text
    
    def query(self, text):
        ''' Query instrument and return response. '''
        if self.lock:
            self._lock.acquire()
        text = self.process_text(text)
        logger.debug(f'QUERY: {text}')
        if not self.testmode:
            out = self.instrument_handle.query(text)[:-1]
        else: 
            out = None
        if self.lock:
            self._lock.release()
        return out
    
    def query_binary_values(self, text, *args, **kwargs):
        if self.lock:
            self._lock.acquire()
        text = self.process_text(text)
        logger.debug(f'QUERY_BINARY_VALUES: {text}')
        if not self.testmode:
            out = self.instrument_handle.query_binary_values(text, *args, **kwargs)
        else:
            out = None
        if self.lock:
            self._lock.release()
        return out

    def write(self, text):
        ''' Send command to instrument. '''
        if self.lock:
            self._lock.acquire()
        text = self.process_text(text)
        logger.debug(f'WRITE: {text}')
        if not self.testmode:
            self.instrument_handle.write(f'{text}')
        if self.lock:
            self._lock.release()
    
    def read_raw(self):
        ''' Read the raw binary content of an instrument answer '''
        if self.lock:
            self._lock.acquire()
        out = self.instrument_handle.read_raw()
        if self.lock:
            self._lock.release()
        return out

    def reset(self):
        ''' Reset the function generator to its factory default state '''
        self.write('*RST')
    
    def clear(self):
        ''' Clear the error queue. '''
        self.write('*CLS')
    
    def get_idn(self):
        '''
        Get instrument ID string.

        :return: string consisting of 4 parts separated by commas:
            - the 1st part is the manufacturer name
            - the 2nd part is the instrument model name
            - the 3rd part is the instrument serial number
            - the 4th part is the digital board version number or some other
            information about the instrument
        '''
        try:
            return self.query('*IDN?')
        except pyvisa.errors.VisaIOError as e:
            return None
    
    def get_name(self):
        ''' Get a simplified manufacturer-model string representation of the instrument '''
        idn = self.get_idn()
        if idn is None:
            return None
        else:
            manufacturer, model, _, _ = idn.split(',')
            return f'{manufacturer} {model}'
    
    def is_operation_complete(self):
        ''' Query whether the previous operations are completed. '''
        return bool(int(self.query('*OPC?')))
    
    abc.abstractmethod
    def wait(self, *args, **kwargs):
        ''' Wait for previous command to finish. '''
        raise NotImplementedError

    @property
    def timeout(self):
        ''' Get I/O operations timeout paramerer (in ms) '''
        return self.instrument_handle.timeout
    
    @timeout.setter
    def timeout(self, value):
        ''' Set I/O operations timeout paramerer (in ms) '''
        self.instrument_handle.timeout = value
    
    # --------------------- ERRORS ---------------------

    @property
    @abc.abstractmethod
    def NO_ERROR_CODE(self):
        ''' String returned when no error has occurred '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_error(self):
        ''' Get last entry in error queue. '''
        raise NotImplementedError
    
    def check_error(self):
        ''' Check if error was generated. '''
        err_msg = self.get_last_error()
        if err_msg != self.NO_ERROR_CODE:
            raise VisaError(err_msg)
        
    # --------------------- FRONT PANEL & DISPLAY ---------------------

    @abc.abstractmethod
    def lock_front_panel(self):
        raise NotImplementedError

    @abc.abstractmethod
    def unlock_front_panel(self):
        raise NotImplementedError
    
    #--------------------- CHAINING ---------------------

    def chain(self, func1, func2, interval=1.):
        ''' Call 2 functions separated by a given interval (in s). '''
        if interval <= 0:
            raise VisaError(f'interval must be strictly positive')
        def func2wrap():
            time.sleep(interval)
            func2()
        func1()
        if interval == 0.:
            func2()
        else:
            thread = threading.Thread(target=func2wrap)
            thread.start()
    
    #--------------------- TRIGGER ---------------------

    def trigger(self):
        self.write('*TRG')

    @abc.abstractmethod
    def set_trigger_slope(self, *args, **kwargs):
        ''' Select the trigger slope. '''
        raise NotImplementedError

    @abc.abstractmethod
    def get_trigger_slope(self, *args, **kwargs):
        ''' Get the trigger slope. '''
        raise NotImplementedError

    #--------------------- CHANNELS ---------------------

    def check_channel_index(self, ich):
        if ich not in self.CHANNELS:
            raise VisaError(f'{ich} is not a channel index (values are {self.CHANNELS})')

    #--------------------- DATA TRANSFER ---------------------

    @property
    def chunk_size(self):
        ''' Get data transfer chunk size (in bytes) '''
        return self.instrument_handle.chunk_size

    @chunk_size.setter
    def chunk_size(self, value):
        ''' Set data transfer chunk size (in bytes) '''
        self.instrument_handle.chunk_size = value