# lab_instruments

Python package to interface diverse laboratory instruments, including:
- **waveform generators**: Rigol DG 1022Z (`RigolDG1022Z`)
- **oscilloscopes**: B&K Precision 2555 (`BK2555`), Rigol DS 1054Z (`RigolDS1054Z`)
- **micro-manipulators**: Sutter Instruments MP-285A (`SutterMP285A`)
- **infrared cameras**: FLIR cameras (`Camera`)
- **acquisition systems**: NI DAQmx for pulse triggers

## Requirements

- FlyCapture SDK (to use the FLIR camera interface class)
- Anaconda
- Python 3.6 (for compliance with FlyCapture SDK)

## Installation

- Clone this repository: `git clone https://github.com/tjjlemaire/lab_instruments.git`
- Move to that directory (`cd lab_instruments`) and install it as a python package: `pip install -e .`

## Usage

See example scripts are located in the `/scripts` subfolder.
