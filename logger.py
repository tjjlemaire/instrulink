# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2021-10-11 13:30:15
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2022-03-16 13:02:25

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


def setHandler(logger, handler):
    for h in logger.handlers:
        logger.removeHandler(h)
    logger.addHandler(handler)
    return logger


def setLogger(name, formatter):
    handler = colorlog.StreamHandler()
    handler.setFormatter(formatter)
    handler.stream = sys.stdout
    logger = colorlog.getLogger(name)
    logger.addHandler(handler)
    return logger


class TqdmHandler(logging.StreamHandler):

    def __init__(self, formatter):
        logging.StreamHandler.__init__(self)
        self.setFormatter(formatter)

    def emit(self, record):
        msg = self.format(record)
        tqdm.write(msg)


logger = setLogger('mylogger', my_log_formatter)
logger.setLevel(logging.INFO)