"""
Send trigger value 2 (FIO1) every 1 second. Press Ctrl+C to stop.
"""

import time
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from pywalker.trigger import EEGTrigger

INTERVAL_S = 0.5   # seconds between trigger
VALUE = 10# FIO1 = bit1 = value 2

trig = EEGTrigger(pulse_ms=50.0, bits=8, verbose=True)

print(f'Sending trigger {VALUE} (FIO1) every {INTERVAL_S}s — Ctrl+C to stop')

try:
    count = 0
    while True:
        trig.send(VALUE)
        time.sleep(0.1)
        trig.send(0)  # short delay to ensure trigger is sent
        count += 1
        time.sleep(INTERVAL_S)
except KeyboardInterrupt:
    print(f'\nStopped after {count} trigger(s).')
finally:
    trig.close()
