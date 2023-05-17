# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-15 15:44:20
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-17 10:54:14

''' Initiate test sequence with Keysight network analyzer. '''

import logging

from instrulink import VisaError, logger
from instrulink.keysight_e5061b import KeysightE5061B


logger.setLevel(logging.DEBUG)

try:
    # Grab function generator
    instrument = KeysightE5061B()
    print(instrument)

    instrument.get_channel_data(ich=1)

except VisaError as e:
    logger.error(e)
    quit()