# instrulink

This python package provides built-in classes to interface diverse laboratory instruments, including:
- **waveform generators**: [Rigol DG 1022Z](https://www.rigolna.com/products/waveform-generators/dg1000z/) (`RigolDG1022Z`)
- **oscilloscopes**: [B&K Precision 2555](https://www.bkprecision.com/products/oscilloscopes/2555) (`BK2555`), [Rigol DS 1054Z](https://www.rigolna.com/products/digital-oscilloscopes/1000z/) (`RigolDS1054Z`)
- **micro-manipulators**: [Sutter Instruments MP-285A](https://www.sutter.com/MICROMANIPULATION/mp285_frame.html) (`SutterMP285A`)
- **infrared cameras**: FLIR cameras (`Camera`)
- **acquisition systems**: [NI DAQmx](https://www.ni.com/docs/en-US/bundle/ni-daqmx/page/daqhelp/nidaqoverview.html) for pulse triggers

## Software dependencies

To interface VISA instruments (i.e., waveforms generators and oscilloscopes), you will need to:
- Download and install [IVI Compliance Package 21.0](https://www.ni.com/en-us/support/downloads/drivers/download.ivi-compliance-package.html#460618)
  When installing, opt to include .NET Adapters and COM adapters as well (these are not selected by default)
- Download and install the [NI Package Manager](https://www.ni.com/en-us/support/downloads/software-products/download.package-manager.html#322516). Through the NI package manager, also install the NI-VISA Driver.

To interface Rigol instruments specifically, you will also need to download and install the associated [Rigol driver](https://www.rigolna.com/products/waveform-generators/dg1000z/)

To interface FLIR cameras, you will need to download and install the [FlyCapture SDK](https://www.flir.com/products/flycapture-sdk/)

You will also need to install `Python 3.6` (for compliance with FlyCapture SDK), preferably as part of an environment manager such as [Anaconda](https://www.anaconda.com/products/individual).

## Installation

This package can be directly installed from PyPI:

```pip install instrulink```

However, if you wish to amend the package code, you can also clone this repo and install it locally as an editable package: 

```
git clone https://github.com/tjjlemaire/instrulink.git
cd instrulink
pip install -e .
```

## Usage

### Connecting to instruments

Instruments can be easily connected to via generic `grab_camera`, `grab_generator`, `grab_oscilloscope` and `grab_manipulator` functions. By default, these functions will automatically detect the first available instrument connected to the PC. Optionally, you can also provide an instrument `key` to connect to a specific model type (e.g. `grab_osciloscope(key='bk')` to specifically connect to a B&K Precision oscilloscope).

### Using instruments

Example scripts are located in the `/scripts` subfolder.
