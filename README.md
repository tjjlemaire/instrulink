# instrulink

This python package provides built-in classes to interface diverse laboratory instruments, including:
- **waveform generators**: [Rigol DG 1022Z](https://www.rigolna.com/products/waveform-generators/dg1000z/) (`RigolDG1022Z`)
- **oscilloscopes**: [B&K Precision 2555](https://www.bkprecision.com/products/oscilloscopes/2555) (`BK2555`), [Rigol DS 1054Z](https://www.rigolna.com/products/digital-oscilloscopes/1000z/) (`RigolDS1054Z`)
- **micro-manipulators**: [Sutter Instruments MP-285A](https://www.sutter.com/MICROMANIPULATION/mp285_frame.html) (`SutterMP285A`)
- **infrared cameras**: FLIR cameras (`Camera`)
- **acquisition systems**: [NI DAQmx](https://www.ni.com/docs/en-US/bundle/ni-daqmx/page/daqhelp/nidaqoverview.html) for pulse triggers

## Requirements

- [FlyCapture SDK](https://www.flir.com/products/flycapture-sdk/) (to use the FLIR camera interface class)
- Anaconda
- Python 3.6 (for compliance with FlyCapture SDK)

## Installation

- Clone this repository: `git clone https://github.com/tjjlemaire/instrulink.git`
- Move to that directory (`cd instrulink`) and install it as a python package: `pip install -e .`

## Usage

Instruments can be easily accessed via generic `grab_camera`, `grab_generator`, `grab_oscilloscope` and `grab_manipulator` functions. By default, these functions will automatically detect the first available instrument connected to the PC. Optionally, you can also provide an instrument `key` to connect to a specific model type (e.g. `grab_osciloscope(key='bk')` to specifically connect to a B&K Precision oscilloscope).

Example scripts are located in the `/scripts` subfolder.
