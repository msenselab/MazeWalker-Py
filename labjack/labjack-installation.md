# LabJack U3 Installation Guide

## Hardware

Connect the LabJack U3 via USB. FIO0–FIO7 are used as 8-bit digital output for EEG triggers.

## Driver Installation

### macOS / Linux

Install the Exodriver (USB driver for LabJack):

```bash
# macOS (Homebrew)
brew install libusb
brew install exodriver

# Linux (Debian/Ubuntu)
sudo apt-get install libusb-1.0-0-dev
git clone https://github.com/labjack/exodriver.git
cd exodriver
sudo ./install.sh
```

### Windows

Download and install the [LabJack UD Driver](https://labjack.com/pages/support?doc=/software-driver/installer-downloads/ud-installer-downloads/).

## Python Package

LabJackPython is included as a local copy in `LabJackPython/`. It is installed automatically when you run `setup_env.sh`:

```bash
./setup_env.sh
source .venv/bin/activate
```

Or install manually into your environment:

```bash
pip install ./LabJackPython
```

## Verify Installation

```python
import u3

d = u3.U3()
print(d.configU3())  # should print device info
d.close()
```

## Usage in MazeWalker-Py

```python
from pywalker.trigger import EEGTrigger

trigger = EEGTrigger(pulse_ms=2.0)
trigger.send(10)   # send trigger value 10
trigger.close()
```

If no LabJack is connected, `EEGTrigger` falls back to console-only mode without crashing.

## Trigger Codes

| Code | Event |
|------|-------|
| 1    | Fixation onset |
| 10   | Maze start |
| 20+n | nth star collected |
| 30   | Trial complete |
| 31   | Trial ended (ESC) |
