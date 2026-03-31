"""
EEG trigger via LabJack U3.

Sends an 8-bit value on FIO0–FIO7, holds for pulse_ms, then resets to 0.
Falls back to console print if LabJack is not connected or not installed.

Trigger codes (suggested):
    1  — fixation onset
    10 — maze start
    20 — first star collected  (20 + n for nth star)
    30 — trial complete (all stars)
    31 — trial ended via ESC
"""

import time

try:
    import u3 as _u3
    _U3_AVAILABLE = True
except ImportError:
    _U3_AVAILABLE = False

# Trigger code constants
TRIG_FIXATION        = 1
TRIG_MAZE_START      = 10
TRIG_COLLECT_BASE    = 20   # + star number (1-indexed)
TRIG_TRIAL_COMPLETE  = 30
TRIG_TRIAL_ESCAPE    = 31


class EEGTrigger:
    """Send EEG triggers via LabJack U3 FIO0–FIO7 pins."""

    def __init__(self, pulse_ms: float = 2.0, verbose: bool = True):
        self.pulse_s = pulse_ms / 1000.0
        self.verbose = verbose
        self._device = None
        self._silent = False

        if not _U3_AVAILABLE:
            print('[EEGTrigger] LabJackPython not installed — console mode')
            self._silent = True
            return

        try:
            self._device = _u3.U3()
            # All FIO as digital I/O
            self._device.configIO(FIOAnalog=0, EIOAnalog=0)
            # Set FIO0-FIO7 as output
            self._device.getFeedback(_u3.PortDirWrite(
                Direction=[0xFF, 0, 0], WriteMask=[0xFF, 0, 0]))
            # Reset to 0
            self._device.getFeedback(_u3.PortStateWrite(
                State=[0, 0, 0], WriteMask=[0xFF, 0, 0]))
            print('[EEGTrigger] LabJack U3 connected')
        except Exception as e:
            print(f'[EEGTrigger] No LabJack found ({e}) — console mode')
            self._device = None
            self._silent = True

    def send(self, value: int):
        """Send trigger: set FIO = value, wait pulse_ms, reset to 0."""
        value = int(value) & 0xFF
        if self.verbose:
            print(f'[EEGTrigger] TRIGGER {value}')
        if self._silent or self._device is None:
            return
        self._device.getFeedback(_u3.PortStateWrite(
            State=[value, 0, 0], WriteMask=[0xFF, 0, 0]))
        time.sleep(self.pulse_s)
        self._device.getFeedback(_u3.PortStateWrite(
            State=[0, 0, 0], WriteMask=[0xFF, 0, 0]))

    def close(self):
        """Reset pins and close device."""
        if self._device:
            try:
                self._device.getFeedback(_u3.PortStateWrite(
                    State=[0, 0, 0], WriteMask=[0xFF, 0, 0]))
                self._device.close()
            except Exception:
                pass
            self._device = None

    def __del__(self):
        self.close()
