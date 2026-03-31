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
from pywalker.trigger import EEGTrigger, star_trigger, TRIG_MAZE_START

# 4-bit mode (default) for Turkey EEG system (4 DC ports, max value 15)
trigger = EEGTrigger(pulse_ms=2.0, bits=4)

# 8-bit mode for systems with 8 DC ports (max value 255)
# trigger = EEGTrigger(pulse_ms=2.0, bits=8)

trigger.send(TRIG_MAZE_START)   # send trigger value 2
trigger.send(star_trigger(0))   # first star collected → code 3
trigger.close()
```

If no LabJack is connected, `EEGTrigger` falls back to console-only mode without crashing.

## Trigger Codes (4-bit scheme)

For systems with limited DC ports (e.g., Turkey EEG with 4 ports), use 4-bit mode (max value 15):

| Code | Event |
|------|-------|
| 1    | Fixation onset |
| 2    | Maze start |
| 3-10 | Star 1-8 collected (3 + star_index) |
| 11   | Trial complete (all stars) |
| 12   | Trial ended (ESC) |

Use `star_trigger(index)` helper for star collection codes (0-indexed).
