# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-03-07 17:11:50
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-11 11:43:32

# Units conversion
MHZ_TO_HZ = 1e6
KHZ_TO_HZ = 1e3
PA_TO_MPA = 1e-6
S_TO_MS = 1e3
MS_TO_S = 1e-3
MV_TO_V = 1e-3
KBS_TO_BS = 1e3
S_TO_MS = 1e3
CELSIUS_TO_KELVIN = 273.15

# Default TTL pulse parameters
TTL_PWIDTH = 1e-5  # width of a nominal TTL pulse (s)
TTL_PAMP = 10.  # amplitude of a nominal TTL pulse (V)

# Regular expressions
SI_REGEXP = '[+-]?\d\.\d+?[Ee][+-]?\d+'
FLOAT_REGEXP = '[+-]?\d*[.]?\d+'
INT_REGEXP = '\d+'