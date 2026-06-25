# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2021-10-11 13:30:15
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2026-06-25 13:32:10

''' Collection of logging utilities. '''

import sys
import colorlog
import logging
import tqdm

my_log_formatter = colorlog.ColoredFormatter(
    '%(log_color)s %(asctime)s %(message)s',
    datefmt='%d/%m/%Y %H:%M:%S:',
    reset=True,
    log_colors={
        'DEBUG': 'green',
        'INFO': 'white',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'red,bg_white',
    },
    style='%')


def setLogger(name, formatter):
    handler = colorlog.StreamHandler()
    handler.setFormatter(formatter)
    handler.stream = sys.stdout
    logger = colorlog.getLogger(name)
    logger.addHandler(handler)
    return logger


logger = setLogger('instrumentlogger', my_log_formatter)
logger.setLevel(logging.INFO)