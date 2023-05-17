# -*- coding: utf-8 -*-
# @Author: Theo Lemaire
# @Email: theo.lemaire@epfl.ch
# @Date:   2017-06-13 09:40:02
# @Last Modified by:   Theo Lemaire
# @Last Modified time: 2023-05-17 10:53:39

import os
from setuptools import setup

readme_file = 'README.md'
req_file = 'requirements.txt'


def readme():
    with open(readme_file, encoding='utf8') as f:
        return f.read()

def getRequirements():
    with open(req_file, encoding='utf8') as f:
        return f.readlines()

def getFiles(path):
    return [f'{path}/{x}' for x in os.listdir(path)]

setup(
    name='labinstruments',
    version='1.0',
    description=readme(),
    url='https://github.com/tjjlemaire/labinstruments',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering :: Physics'
    ],
    keywords=('laboratory instrument interface python'),
    author='Theo Lemaire',
    author_email='theo.lemaire1@gmail.com',
    license='MIT',
    packages=['labinstruments'],
    scripts=getFiles('scripts'),
    install_requires=getRequirements(),
    zip_safe=False
)