# LabJack EEG Trigger Code

MATLAB code for sending EEG triggers via LabJack U3.

## Files

- `labJack.m` — Main class for LabJack U3 communication (cross-platform)
- `sendTrigger.m` — Helper function with proper pulse timing

## Requirements

### macOS / Linux
```bash
# Install via Homebrew (macOS)
brew install libusb exodriver --universal

# Or follow LabJack instructions for Linux
```

### Windows
Use LabJack UD driver instead (see CLabJack.m in original folder).

## Usage

```matlab
% Initialize LabJack
lj = labJack('verbose', true);

% Send trigger value (0-255)
sendTrigger(lj, 10);   % Sends trigger code 10

% In your experiment loop:
sendTrigger(lj, 1);    % Stimulus onset
% ... present stimulus ...
sendTrigger(lj, 2);    % Response
```

## How It Works

1. `sendTrigger(lj, value)` sets FIO port to `value`
2. Waits 2ms (safe for ≥500 Hz EEG sampling)
3. Resets FIO port to 0

The 2ms pulse ensures the EEG system captures the trigger edge.

## Trigger Values

| Event | Suggested Code |
|-------|----------------|
| Trial start | 1 |
| Stimulus onset | 10-99 (by condition) |
| Response | 100-109 (by button) |
| Feedback | 200-209 |
| Trial end | 255 |

## Hardware Notes

- LabJack U3 uses **3.3V logic**
- If EEG requires 5V TTL, use a level shifter
- Connect via FIO pins (DB15 connector)

## Original Source

From Siyi Chen's EEG experiment code (2019).
Added to EyeCon project: March 2026.
