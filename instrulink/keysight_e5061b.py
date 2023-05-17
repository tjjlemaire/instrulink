# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-11-02 12:00:31
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2022-11-02 12:22:59

from .visa_instrument import *

class KeysightE5061B(VisaInstrument):
    ''' Interface Keysight E5061B ENA Network Analyzer using the SCPI command interface '''

    PREFIX = ':'
    USB_ID = 'MY49810002'
    NO_ERROR_CODE = '0,"No error"'  # not sure

    def reset(self):
        pass

    def clear(self):
        pass

    def get_last_error(self):
        pass
    
    def get_trigger_slope(self):
        pass
    
    def lock_front_panel(self):
        pass
    
    def set_trigger_slope(self):
        pass
    
    def unlock_front_panel(self):
        pass
    
    def get_channel_data(self, ich=1):
        '''
        Extract data from a given channel
        
        :param ich: channel index
        :return: 2-tuple with:
            - frequency vector (Hz)
            - values vector (???)
        '''
        self.write('FORM:DATA ASC')
        m = self.ask_for_values(f'CALC{ich}:DATA:FDAT?')
        m = m[::2]
        f = self.ask_for_values(f'SENS{ich}:FREQ:DATA?')
        return f, m

