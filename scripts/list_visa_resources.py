# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Date:   2022-08-15 10:21:10
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2022-08-15 10:21:18

import pyvisa

# Detect instrument and store its handle
rm = pyvisa.ResourceManager()
resources = rm.list_resources()
res_str = '\n'.join([f'  - {r}' for r in resources])
print(f'VISA resources:\n{res_str}')