"""
Cycle through all 4-bit trigger codes (1–15) on LabJack U3 FIO0-FIO3.

Sends trigger -> waits -> sends 0 -> repeats, one code every 500 ms total.
Loops indefinitely until Ctrl+C.
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from pywalker.trigger import EEGTrigger

PULSE_MS   = 2.0   # trigger pulse duration (ms)
GAP_S      = 0.05   # gap between trigger and send-0
INTERVAL_S = 4   # gap after send-0 before next trigger
                   # total per step ≈ PULSE_MS/1000 + GAP_S + INTERVAL_S ≈ 500 ms
BITS       = 4     # 4-bit mode: FIO0–FIO3, values 1–15

trig = EEGTrigger(pulse_ms=PULSE_MS, bits=BITS, verbose=True)

print(f'Cycling triggers 1–{(1 << BITS) - 1}, ~500 ms per trigger. Ctrl+C to stop.\n')

loop = 0
try:
    while True:
        loop += 1
        print(f'--- Loop {loop} ---')
        for value in range(1, 1 << BITS):   # 1 … 15
            trig.send(value)
            time.sleep(GAP_S)
            trig.send(0)
            time.sleep(INTERVAL_S)

except KeyboardInterrupt:
    print(f'\nStopped after {loop} loop(s).')

finally:
    trig.close()
