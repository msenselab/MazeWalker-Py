"""
Proof-of-concept: PsychoPy + Ursina coexistence for maze experiments.

Flow:
  1. PsychoPy shows instruction screen, sends EEG trigger
  2. PsychoPy window closes
  3. Ursina opens 3D maze for navigation
  4. After maze ends (ESC), Ursina closes
  5. PsychoPy reopens for feedback / next trial

EEG triggers:
  - Uses serial port (pyserial) or parallel port when available
  - Falls back to console logging for testing without hardware

Usage:
  .venv/bin/python pywalker/experiment.py maze/Maze220925.maz
"""

import sys
import os
import time as pytime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# EEG Trigger abstraction
# ---------------------------------------------------------------------------

class TriggerPort:
    """Abstract trigger interface. Sends integer codes to EEG system."""

    def send(self, code: int):
        raise NotImplementedError


class SerialTrigger(TriggerPort):
    """Send triggers via serial port (e.g., USB-to-serial adapter)."""

    def __init__(self, port='/dev/tty.usbserial', baudrate=115200):
        import serial
        self.ser = serial.Serial(port, baudrate, timeout=0.1)

    def send(self, code: int):
        self.ser.write(bytes([code]))
        print(f"[SERIAL] Trigger: {code}")


class ParallelTrigger(TriggerPort):
    """Send triggers via parallel port (psychopy.parallel)."""

    def __init__(self, address=0x0378):
        from psychopy import parallel
        self.port = parallel.ParallelPort(address=address)

    def send(self, code: int):
        self.port.setData(code)
        pytime.sleep(0.005)  # 5ms pulse
        self.port.setData(0)
        print(f"[PARALLEL] Trigger: {code}")


class ConsoleTrigger(TriggerPort):
    """Fallback: print trigger codes to console for testing."""

    def send(self, code: int):
        print(f"[TRIGGER] code={code} t={pytime.time():.3f}")


def get_trigger(method='console', **kwargs) -> TriggerPort:
    """Factory for trigger ports."""
    if method == 'serial':
        return SerialTrigger(**kwargs)
    elif method == 'parallel':
        return ParallelTrigger(**kwargs)
    else:
        return ConsoleTrigger()


# ---------------------------------------------------------------------------
# Trigger codes (customize for your EEG setup)
# ---------------------------------------------------------------------------
TRIG_EXPERIMENT_START = 1
TRIG_INSTRUCTIONS_ON = 10
TRIG_MAZE_START = 20
TRIG_MAZE_END = 21
TRIG_FEEDBACK_ON = 30
TRIG_EXPERIMENT_END = 99


# ---------------------------------------------------------------------------
# PsychoPy phases
# ---------------------------------------------------------------------------

def show_instructions(trigger: TriggerPort, message: str = ""):
    """Show instruction screen using PsychoPy. Returns when participant presses SPACE."""
    from psychopy import visual, event, core

    win = visual.Window(
        size=(800, 600),
        fullscr=False,
        color='black',
        title='Maze Experiment - Instructions',
    )

    if not message:
        message = (
            "Welcome to the Maze Experiment!\n\n"
            "Use W/A/S/D to walk through the maze.\n"
            "Use mouse to look around.\n"
            "Press ESC to end the maze trial.\n\n"
            "Press SPACE to start."
        )

    text = visual.TextStim(
        win, text=message,
        color='white', height=0.06, wrapWidth=1.5,
    )

    trigger.send(TRIG_INSTRUCTIONS_ON)

    text.draw()
    win.flip()

    event.waitKeys(keyList=['space'])

    win.close()
    core.wait(0.3)  # brief pause for GL context cleanup


def show_feedback(trigger: TriggerPort, maze_duration: float):
    """Show feedback screen using PsychoPy after maze completion."""
    from psychopy import visual, event, core

    win = visual.Window(
        size=(800, 600),
        fullscr=False,
        color='black',
        title='Maze Experiment - Feedback',
    )

    trigger.send(TRIG_FEEDBACK_ON)

    text = visual.TextStim(
        win,
        text=(
            f"Maze completed!\n\n"
            f"Time: {maze_duration:.1f} seconds\n\n"
            "Press SPACE to continue or Q to quit."
        ),
        color='white', height=0.06, wrapWidth=1.5,
    )

    text.draw()
    win.flip()

    keys = event.waitKeys(keyList=['space', 'q'])
    win.close()
    core.wait(0.3)

    return 'q' not in keys


# ---------------------------------------------------------------------------
# Ursina maze phase
# ---------------------------------------------------------------------------

def run_maze_trial(maz_filepath: str, trigger: TriggerPort) -> float:
    """
    Run a single maze trial in Ursina.

    Returns the duration in seconds.
    """
    from pywalker.maz_parser import parse_maz
    from ursina import (
        Ursina, Entity, Mesh, Vec3 as UVec3, Text,
        color, camera, window, application,
        held_keys, time, invoke, destroy,
    )
    from pywalker.maze_renderer import (
        build_maze_scene,
    )

    maze_data = parse_maz(maz_filepath)

    app = Ursina(title='Maze Trial', borderless=False, size=(1024, 768))
    window.color = color.rgb(135, 206, 235)

    player = build_maze_scene(maze_data)

    # HUD
    pos_text = Text(text='', position=(-0.85, 0.45), scale=1)
    timer_text = Text(text='', position=(0.65, 0.45), scale=1.2)

    trigger.send(TRIG_MAZE_START)
    start_time = pytime.time()

    # Track state within closure
    state = {'running': True}

    original_update = player.update.__func__ if hasattr(player.update, '__func__') else None

    def custom_update(self_player):
        if original_update:
            original_update(self_player)
        elapsed = pytime.time() - start_time
        pos_text.text = f'x={self_player.x:.1f}  z={self_player.z:.1f}'
        timer_text.text = f'{elapsed:.1f}s'

    import types
    player.update = types.MethodType(custom_update, player)

    app.run()

    duration = pytime.time() - start_time
    trigger.send(TRIG_MAZE_END)

    return duration


# ---------------------------------------------------------------------------
# Main experiment loop
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python experiment.py <file.maz> [trigger_method]")
        print("  trigger_method: console (default), serial, parallel")
        sys.exit(1)

    maz_file = sys.argv[1]
    trigger_method = sys.argv[2] if len(sys.argv) > 2 else 'console'

    trigger = get_trigger(trigger_method)
    trigger.send(TRIG_EXPERIMENT_START)

    # --- Phase 1: Instructions (PsychoPy) ---
    show_instructions(trigger)

    # --- Phase 2: Maze navigation (Ursina) ---
    duration = run_maze_trial(maz_file, trigger)

    # --- Phase 3: Feedback (PsychoPy) ---
    cont = show_feedback(trigger, duration)

    trigger.send(TRIG_EXPERIMENT_END)
    print(f"\nExperiment finished. Maze duration: {duration:.1f}s")


if __name__ == "__main__":
    main()
