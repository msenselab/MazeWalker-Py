"""
EEG trigger via LabJack U3 — Windows Debug Version.

Same as trigger.py but FIO1 is always forced ON during every pulse,
providing a visual LED indicator for every trigger sent.

Use this version for hardware debugging only, not for actual EEG recording.
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
TRIG_COLLECT_BASE    = 3
TRIG_TRIAL_COMPLETE  = 11
TRIG_TRIAL_ESCAPE    = 12

_FIO1_BIT = 0x02  # always OR into the value so FIO1 is always ON


def star_trigger(star_index: int) -> int:
    """Return trigger code for collecting a star (0-indexed: star 0 → code 3)."""
    code = TRIG_COLLECT_BASE + star_index
    return min(code, 10)


class EEGTriggerDebug:
    """Debug version of EEGTrigger — FIO1 always lights up on every trigger.

    Args:
        pulse_ms: Trigger pulse duration in milliseconds.
        bits: Number of output bits (4 for Turkey EEG, 8 for full range).
        verbose: Print trigger codes to console.
    """

    def __init__(self, pulse_ms: float = 200.0, bits: int = 4, verbose: bool = True):
        self.pulse_s = pulse_ms / 1000.0
        self.bits = bits
        self.verbose = verbose
        self._device = None
        self._silent = False

        self._mask = (1 << bits) - 1
        self._max_value = self._mask

        if not _U3_AVAILABLE:
            print('[EEGTriggerDebug] LabJackPython not installed — console mode')
            self._silent = True
            return

        try:
            self._device = _u3.U3()
            self._device.configIO(FIOAnalog=0, EIOAnalog=0)
            self._device.getFeedback(_u3.PortDirWrite(
                Direction=[self._mask, 0, 0], WriteMask=[self._mask, 0, 0]))
            self._device.getFeedback(_u3.PortStateWrite(
                State=[0, 0, 0], WriteMask=[self._mask, 0, 0]))
            print(f'[EEGTriggerDebug] LabJack U3 connected ({bits}-bit, FIO1 always ON per trigger)')
        except Exception as e:
            print(f'[EEGTriggerDebug] No LabJack found ({e}) — console mode')
            self._device = None
            self._silent = True

    def send(self, value: int):
        """Send trigger: force FIO1 ON, set value, wait pulse_ms, reset to 0."""
        value = (int(value) | _FIO1_BIT) & self._mask  # force FIO1 always ON
        if self.verbose:
            print(f'[EEGTriggerDebug] TRIGGER {value} (binary {value:04b})')
        if self._silent or self._device is None:
            return
        self._device.getFeedback(_u3.PortStateWrite(
            State=[value, 0, 0], WriteMask=[self._mask, 0, 0]))
        time.sleep(self.pulse_s)
        self._device.getFeedback(_u3.PortStateWrite(
            State=[0, 0, 0], WriteMask=[self._mask, 0, 0]))

    def led_on(self):
        """Turn FIO1 ON and keep it on (no pulse)."""
        if self.verbose:
            print('[EEGTriggerDebug] FIO1 ON')
        if self._silent or self._device is None:
            return
        self._device.getFeedback(_u3.PortStateWrite(
            State=[_FIO1_BIT, 0, 0], WriteMask=[self._mask, 0, 0]))

    def led_off(self):
        """Turn FIO1 OFF."""
        if self.verbose:
            print('[EEGTriggerDebug] FIO1 OFF')
        if self._silent or self._device is None:
            return
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


if __name__ == '__main__':
    import time
    trig = EEGTriggerDebug(pulse_ms=500, bits=4, verbose=True)
    codes = [
        (TRIG_FIXATION,       'Fixation onset'),
        (TRIG_MAZE_START,     'Maze start'),
        (star_trigger(0),     'Star 1'),
        (star_trigger(1),     'Star 2'),
        (star_trigger(2),     'Star 3'),
        (TRIG_TRIAL_COMPLETE, 'Trial complete'),
        (TRIG_TRIAL_ESCAPE,   'Trial escape'),
    ]
    for code, label in codes:
        print(f'--- {label} ---')
        trig.send(code)
        time.sleep(1.0)
    trig.close()
    print('Done')
