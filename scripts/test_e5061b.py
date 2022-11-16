# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-15 15:44:20
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2022-11-02 12:23:14

''' Initiate test sequence with Keysight network analyzer. '''

import logging

from lab_instruments.visa_instrument import VisaError
from lab_instruments.keysight_e5061b import KeysightE5061B
from lab_instruments.logger import logger


logger.setLevel(logging.DEBUG)

try:
    # Grab function generator
    instrument = KeysightE5061B()
    print(instrument)

    instrument.get_channel_data(ich=1)

except VisaError as e:
    logger.error(e)
    quit()