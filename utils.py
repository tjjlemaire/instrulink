# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-18 14:42:17
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2022-08-15 09:28:52

import numpy as np


def bounds(x):
    '''Get the bounds of an array ''' 
    return np.array([x.min(), x.max()])


def nan_like(x):
    ''' Create array of identicial shape as input, filled with nan values '''
    xnan = np.zeros_like(x)
    xnan[:] = np.nan
    return xnan


def is_within(x, bounds):
    return np.logical_and(x >= bounds[0], x <= bounds[1])
