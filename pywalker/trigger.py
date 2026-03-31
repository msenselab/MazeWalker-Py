"""
EEG trigger via LabJack U3.

Sends an N-bit value on FIO pins, holds for pulse_ms, then resets to 0.
Falls back to console print if LabJack is not connected or not installed.

Trigger codes (4-bit scheme, max value 15):
    1     — fixation onset
    2     — maze start
    3-10  — star 1-8 collected (3 + star_index, 0-indexed)
    11    — trial complete (all stars)
    12    — trial ended via ESC
"""

import time

try:
    import u3 as _u3
    _U3_AVAILABLE = True
except ImportError:
    _U3_AVAILABLE = False

# Trigger code constants (4-bit compatible: 1-15)
TRIG_FIXATION        = 1
TRIG_MAZE_START      = 2
TRIG_COLLECT_BASE    = 3    # + star_index (0-indexed), so star 1 = 3, star 8 = 10
TRIG_TRIAL_COMPLETE  = 11
TRIG_TRIAL_ESCAPE    = 12


def star_trigger(star_index: int) -> int:
    """Return trigger code for collecting a star (0-indexed: star 0 → code 3)."""
    code = TRIG_COLLECT_BASE + star_index
    if code > 10:
        # Clamp to max star code if more than 8 stars
        return 10
    return code


class EEGTrigger:
    """Send EEG triggers via LabJack U3 FIO pins.
    
    Args:
        pulse_ms: Trigger pulse duration in milliseconds.
        bits: Number of output bits (4 for Turkey EEG, 8 for full range).
        verbose: Print trigger codes to console.
    """

    def __init__(self, pulse_ms: float = 2.0, bits: int = 4, verbose: bool = True):
        self.pulse_s = pulse_ms / 1000.0
        self.bits = bits
        self.verbose = verbose
        self._device = None
        self._silent = False
        
        # Compute mask based on bit count
        self._mask = (1 << bits) - 1  # 4 bits → 0x0F, 8 bits → 0xFF
        self._max_value = self._mask

        if not _U3_AVAILABLE:
            print('[EEGTrigger] LabJackPython not installed — console mode')
            self._silent = True
            return

        try:
            self._device = _u3.U3()
            # All FIO as digital I/O
            self._device.configIO(FIOAnalog=0, EIOAnalog=0)
            # Set FIO0-FIO(bits-1) as output
            self._device.getFeedback(_u3.PortDirWrite(
                Direction=[self._mask, 0, 0], WriteMask=[self._mask, 0, 0]))
            # Reset to 0
            self._device.getFeedback(_u3.PortStateWrite(
                State=[0, 0, 0], WriteMask=[self._mask, 0, 0]))
            print(f'[EEGTrigger] LabJack U3 connected ({bits}-bit mode, max={self._max_value})')
        except Exception as e:
            print(f'[EEGTrigger] No LabJack found ({e}) — console mode')
            self._device = None
            self._silent = True

    def send(self, value: int):
        """Send trigger: set FIO pins = value, wait pulse_ms, reset to 0."""
        value = int(value) & self._mask
        if self.verbose:
            print(f'[EEGTrigger] TRIGGER {value}')
        if self._silent or self._device is None:
            return
        self._device.getFeedback(_u3.PortStateWrite(
            State=[value, 0, 0], WriteMask=[self._mask, 0, 0]))
        time.sleep(self.pulse_s)
        self._device.getFeedback(_u3.PortStateWrite(
            State=[0, 0, 0], WriteMask=[self._mask, 0, 0]))

    def close(self):
        """Reset pins and close device."""
        if self._device:
            try:
                self._device.getFeedback(_u3.PortStateWrite(
                    State=[0, 0, 0], WriteMask=[self._mask, 0, 0]))
                self._device.close()
            except Exception:
                pass
            self._device = None

    def __del__(self):
        self.close()
