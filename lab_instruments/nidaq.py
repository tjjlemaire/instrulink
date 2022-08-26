
from nidaqmx.system import System
from nidaqmx.system.device import Device
from nidaqmx.task import Task
import numpy as np

from .logger import logger


def get_device_names():
    '''  Get NI DAQ device names list '''
    return System().devices.device_names

def get_terminals(device_name):
    ''' Get NI DAQ device output terminals list '''
    return Device(device_name).terminals

def get_co_channels(device_name):
    ''' Get NI DAQ device physical counter output channels list '''
    return Device(device_name).co_physical_chans.channel_names


class PulseTrainGenerator:
    ''' 
    Interface to generate a train of digital output pulses on the NI DAQ with
    specified frequency and initial delay relative to each supplied input triggers
    '''

    timeout = 5

    ######################### CONSTRUCTORS & DESTRUCTORS #########################

    def __init__(self, device_name=None, input_PFI=0, output_PFI=1, output_co=0,
                 freq=1., duty_cycle=0.5, initial_delay=0, npulses=1):
        '''
        Constructor

        :param device_name: DAQmx device name (e.g. "PXI1Slot6")
        :param input_PFI: PFI slot number on which input trigger is received
        :param output_PFI: PFI slot number on which output pulse is generated
        :param output_co: counter output channel number
        :param freq: frequency (in Hz) at which to generate pulses.
        :param duty_cycle: width of pulses divided by the inter-pulse period.
        :param initial_delay: time in seconds to wait before generating the first pulse.
        :param npulses: number of pulses to generate
        '''
        # DAQ parameters 
        self.device_name = device_name
        self.input_PFI = input_PFI
        self.output_PFI = output_PFI
        self.output_co = output_co
        # Pulse train parameters
        self.freq = freq
        self.duty_cycle = duty_cycle
        self.initial_delay = initial_delay
        self.npulses = npulses
        # Create task
        self.create_task()
        # Log upon creation
        logger.info(f'created {self}')
    
    def __del__(self):
        ''' Destructor '''
        # Close underlying task
        logger.info('closing task ...')
        self._task.close()
        del(self._task)
    
    def __repr__(self):
        return f'{self.__class__.__name__}({self.device_name}, PFI_in={self.input_PFI}, PFI_out={self.output_PFI}, CO_out={self.output_co}, freq={self.freq:.2f}Hz, delay={self.initial_delay:.2f}s, npulses={self.npulses})'

    ######################### GETTERS & SETTERS #########################

    @staticmethod
    def validate_attribute(key, val, dtype=float):
        if not isinstance(val, dtype):
            if dtype == float and isinstance(val, int):
                val = float(val)
            else:
                raise ValueError(f'{key} is not a {dtype}')
        if val < 0 or val == np.inf:
            raise ValueError(f'{key} must be a positive finite scalar')

    @property
    def device_name(self):
        return self._device_name
        
    @device_name.setter
    def device_name(self, val):
        if val is None:
            val = get_device_names()[0]
        self._device_name = val
            
    @property
    def input_PFI(self):
        return self._input_PFI
    
    @input_PFI.setter
    def input_PFI(self, val):
        if val is not None:
            self.validate_attribute('input_PFI', val, dtype=int)
        self._input_PFI = val
        self.__update_trigger_props('input_PFI')
    
    @property
    def output_PFI(self):
        return self._output_PFI
    
    @output_PFI.setter
    def output_PFI(self, val):
        if val is not None:
            self.validate_attribute('output_PFI', val, dtype=int)
        self._output_PFI = val
        self.__update_trigger_props('output_PFI')
    
    @property
    def output_co(self):
        return self._output_co
    
    @output_co.setter
    def output_co(self, val):
        if val is not None:
            self.validate_attribute('output_co', val, dtype=int)
        self._output_co = val
        self.__update_trigger_props('output_co')
    
    @property
    def freq(self):
        return self._freq
    
    @freq.setter
    def freq(self, val):
        self.validate_attribute('freq', val)
        self._freq = val
        self.__update_timer_props('freq')
    
    @property
    def duty_cycle(self):
        return self._duty_cycle
    
    @duty_cycle.setter
    def duty_cycle(self, val):
        self.validate_attribute('duty_cycle', val)
        self._duty_cycle = val
        self.__update_timer_props('duty_cycle')
    
    @property
    def initial_delay(self):
        return self._initial_delay
    
    @initial_delay.setter
    def initial_delay(self, val):
        self.validate_attribute('initial_delay', val)
        self._initial_delay = val
        self.__update_timer_props('initial_delay')
    
    @property
    def npulses(self):
        return self._npulses
    
    @npulses.setter
    def npulses(self, val):
        self.validate_attribute('npulses', val, dtype=int)
        self._npulses = val
        self.__update_timer_props('npulses')

    ######################### DERIVED PROPERTIES #########################

    @property
    def task_name(self):
        return self.__class__.__name__

    @property   
    def input_terminal(self):
        if self.input_PFI is None:
            return get_terminals(self.device_name)[0]
        return f'/{self.device_name}/PFI{self.input_PFI}'

    @property   
    def output_terminal(self):
        if self.output_PFI is None:
            return get_terminals(self.device_name)[1]
        return f'/{self.device_name}/PFI{self.output_PFI}'

    @property
    def output_channel(self):
        if self.output_co is None:
            return get_co_channels(self.device_name)[0]
        return f'{self.device_name}/ctr{self.output_co}'
    
    ######################### OTHER METHODS #########################

    def create_task(self):
        ''' Create underlying task '''
        self._task = Task(self.task_name)
        self._task.co_channels.add_co_pulse_chan_freq(
            self.output_channel,
            initial_delay=self.initial_delay,
            freq=self.freq,
            duty_cycle=self.duty_cycle,
        )
        self.__update_timer_props('init')
        self.__update_trigger_props('init')
        
    def check_task_disabled(self, propName):
        ''' Throw error if task is already enabled while trying to set a property '''
        assert self._task.is_task_done(), f'Cannot update property "{propName}" while pulse train generator is enabled'

    def __update_timer_props(self, propName):
        ''' Propagate timing properties to underlying task & channel '''
        # If underlying task exists
        if hasattr(self, '_task'):
            # Check that task is disabled
            self.check_task_disabled(propName)
            # Set Task channel pulse properties: frequency, duty cycle,
            # delay, and number of pulses
            self._task.co_channels[0].co_pulse_freq = self.freq
            self._task.co_channels[0].co_pulse_duty_cyc = self.duty_cycle
            self._task.co_channels[0].co_pulse_freq_initial_delay = self.initial_delay
            self._task.timing.cfg_implicit_timing(samps_per_chan= self.npulses)
            # Ensure that initial delay is conserved upon re-triggering
            self._task.co_channels[0].co_enable_initial_delay_on_retrigger = True
        
    def __update_trigger_props(self, propName):
        ''' Propagate trigger properties to underlying task '''
        # If underlying task exists
        if hasattr(self, '_task'):
            # Check that task is disabled
            self.check_task_disabled(propName)
            # Set the task to start upon acquisition start
            self._task.triggers.start_trigger.cfg_dig_edge_start_trig(self.input_terminal)
            # Set task to be triggerable
            self._task.triggers.start_trigger.retriggerable = True
            # Set pulse output terminal
            self._task.co_channels[0].co_pulse_term = self.output_terminal
    
    def enable(self):
        assert self._task.is_task_done(), 'Pulse train generator is already enabled'
        logger.info('starting task...')
        self._task.start()
        
    def disable(self):
        logger.info('stopping task...')
        self._task.stop()


def trigger_train(delay=0, interval=1., npulses=1):
    '''
    Set up a train of TTL pulses to be triggered upon acquisition 
    
    :param delay: delay in seconds to initiate first pulse (default = 0)
    :param interval: interval in seconds between pulses (default = 1s)
    :param npulses: number of pulses (default = 1)
    :return: PulseTrainGenerator object
    '''    
    # Create PulseTrainGenerator object
    ptg = PulseTrainGenerator(
        device_name='PXI1Slot6', # Device name, 
        input_PFI=0, output_PFI=1, # Input & output PFI slots
        output_co=0,  # output channel
        freq=1 / interval, # frequency set to reciprocal of inter-pulse interval
        duty_cycle= .005 / interval,  # duty cycle set to obtain a constant pusle width of 5 ms
        initial_delay=delay,
        npulses=npulses
    )
    # Start underlying task
    ptg.enable()
    # Enable
    return ptg