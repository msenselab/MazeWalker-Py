"""
Trial-sequenced maze experiment using Ursina.

Presents multiple mazes in randomized order with repeats.
All trials run within a single Ursina app instance, with
between-trial screens (instructions, fixation, feedback) shown
as Ursina Text overlays.

Usage:
  .venv/bin/python pywalker/experiment.py maze/Maze220925.maz maze/Maze260925.maz
  .venv/bin/python pywalker/experiment.py maze/Maze220925.maz --repeats 2
"""

import sys
import os
import csv
import math
import random
import time as pytime
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ursina import (
    Ursina, Entity, Text,
    color, window, application, camera,
    held_keys, destroy, invoke,
)
from pywalker.maz_parser import parse_maz, resolve_assets
from pywalker.maze_renderer import build_maze_scene, clear_maze_scene, load_model
from pywalker.trigger_debug import EEGTriggerDebug as EEGTrigger, TRIG_FIXATION, TRIG_MAZE_START, TRIG_COLLECT_BASE, TRIG_TRIAL_COMPLETE, TRIG_TRIAL_ESCAPE

# --- Gamepad confirm button (pygame, since Panda3D doesn't detect on macOS) ---
import pygame
pygame.init()
pygame.joystick.init()
_joy = pygame.joystick.Joystick(0) if pygame.joystick.get_count() > 0 else None
if _joy:
    _joy.init()

# Xbox A button = button 0 on most mappings
_CONFIRM_BUTTON = 0


def confirm_pressed() -> bool:
    """Check if SPACE or gamepad A button is pressed."""
    if held_keys['space']:
        return True
    if _joy:
        pygame.event.pump()
        return _joy.get_button(_CONFIRM_BUTTON)
    return False


# ---------------------------------------------------------------------------
# Experiment states
# ---------------------------------------------------------------------------
STATE_INSTRUCTIONS = 'instructions'
STATE_FIXATION = 'fixation'
STATE_MAZE = 'maze'
STATE_FEEDBACK = 'feedback'
STATE_DONE = 'done'


class Experiment(Entity):
    """
    Manages the trial sequence within a single Ursina app.

    Flow per trial:
      INSTRUCTIONS → FIXATION → MAZE → FEEDBACK → (next trial or DONE)
    """

    def __init__(self, maze_files: list[str], repeats: int = 1, trigger: EEGTrigger = None, **kwargs):
        super().__init__(**kwargs)
        self.trigger = trigger or EEGTrigger()

        # Build trial list: each maze repeated, then shuffled
        self.trial_list = maze_files * repeats
        random.shuffle(self.trial_list)

        self.trial_index = 0
        self.state = STATE_INSTRUCTIONS
        self.player = None
        self.collectibles = []
        self.maze_data = None
        self._space_prev = False  # for spacebar press detection

        # Timing
        self.trial_start_time = 0
        self.state_start_time = 0
        self.trial_log = []  # list of dicts

        # HUD elements (persistent across states)
        self.message_text = Text(
            text='',
            parent=camera.ui,
            origin=(0, 0),
            scale=1,
            color=color.white,
        )
        self.score_text = Text(
            text='',
            parent=camera.ui,
            position=(-0.85, 0.45),
            scale=1,
            color=color.yellow,
        )
        self.info_text = Text(
            text='',
            parent=camera.ui,
            position=(-0.85, 0.40),
            scale=0.8,
            color=color.white,
        )

        # Points state
        self.points = 0
        self.exit_threshold = 0
        self.completed = False

        # --- Data logging ---
        data_dir = Path('data')
        data_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.trials_csv_path = data_dir / f'{timestamp}_trials.csv'
        self.traj_csv_path = data_dir / f'{timestamp}_trajectory.csv'

        # Write CSV headers
        with open(self.trials_csv_path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['trial', 'maze', 'duration_s', 'stars_collected', 'stars_total', 'completed'])
        with open(self.traj_csv_path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['trial', 'maze', 'time_s', 'x', 'y', 'z', 'angle', 'event'])

        self._traj_writer = None
        self._traj_file = None
        print(f"  Data: {self.trials_csv_path}")
        print(f"  Traj: {self.traj_csv_path}")

        # Start
        print(f"\n=== Experiment: {len(self.trial_list)} trials ===")
        print(f"  Mazes: {maze_files}")
        print(f"  Repeats: {repeats}")
        print(f"  Order: {[Path(f).stem for f in self.trial_list]}")
        self._show_instructions()

    def _show_instructions(self):
        """Show pre-trial instructions."""
        self.state = STATE_INSTRUCTIONS
        self.state_start_time = pytime.time()
        self.message_text.scale = 1
        trial_num = self.trial_index + 1
        total = len(self.trial_list)
        maze_name = Path(self.trial_list[self.trial_index]).stem

        self.message_text.text = (
            f'Trial {trial_num} / {total}\n'
            f'Maze: {maze_name}\n\n'
            f'Collect all stars!\n'
            f'WASD / Left stick to move\n'
            f'Mouse / Right stick to look\n\n'
            f'Press SPACE or A to start'
        )
        self.score_text.text = ''
        self.info_text.text = ''

    def _show_fixation(self):
        """Show fixation cross before trial starts."""
        self.state = STATE_FIXATION
        self.state_start_time = pytime.time()
        self.message_text.text = '+'
        self.message_text.scale = 2
        self.trigger.send(TRIG_FIXATION)
        # Auto-advance after 1 second
        invoke(self._start_maze, delay=1.0)

    def _start_maze(self):
        """Load and start a maze trial."""
        self.state = STATE_MAZE
        self.message_text.text = ''
        self.message_text.scale = 1

        maz_file = self.trial_list[self.trial_index]
        print(f"\n--- Trial {self.trial_index + 1}: {Path(maz_file).stem} ---")

        # Parse and build scene
        self.maze_data = parse_maz(maz_file)
        resolve_assets(self.maze_data, maz_file)
        self.player, self.collectibles = build_maze_scene(self.maze_data)

        # Reset game state
        self.points = 0
        self.exit_threshold = self.maze_data.settings.exit_threshold
        self.completed = False
        self.trial_start_time = pytime.time()

        self.score_text.text = f'Stars: 0 / {self.exit_threshold}'
        self.trigger.send(TRIG_MAZE_START)

        # Open trajectory file for appending during this trial
        self._traj_file = open(self.traj_csv_path, 'a', newline='')
        self._traj_writer = csv.writer(self._traj_file)
        self._current_maze_name = Path(maz_file).stem

        if self.maze_data.settings.start_message:
            self.message_text.text = self.maze_data.settings.start_message
            invoke(setattr, self.message_text, 'text', '', delay=2.0)

    def _show_feedback(self, duration: float):
        """Show post-trial feedback."""
        self.state = STATE_FEEDBACK
        self.state_start_time = pytime.time()
        self.message_text.scale = 1

        trial_num = self.trial_index + 1
        status = 'Complete!' if self.completed else 'Time up'
        self.message_text.text = (
            f'Trial {trial_num} — {status}\n'
            f'Stars: {self.points} / {self.exit_threshold}\n'
            f'Time: {duration:.1f}s\n\n'
            f'Press SPACE or A to continue'
        )
        self.score_text.text = ''
        self.info_text.text = ''

        # Log trial
        maze_name = Path(self.trial_list[self.trial_index]).stem
        self.trial_log.append({
            'trial': trial_num,
            'maze': maze_name,
            'duration': duration,
            'points': self.points,
            'completed': self.completed,
        })
        # Write trial summary row
        with open(self.trials_csv_path, 'a', newline='') as f:
            csv.writer(f).writerow([
                trial_num, maze_name, f'{duration:.3f}',
                self.points, self.exit_threshold, self.completed,
            ])

    def _end_trial(self):
        """Clean up current maze and advance."""
        clear_maze_scene()
        self.player = None
        self.collectibles = []
        self.trial_index += 1

        if self.trial_index < len(self.trial_list):
            self._show_instructions()
        else:
            self._show_done()

    def _show_done(self):
        """Show experiment complete screen."""
        self.state = STATE_DONE
        self.message_text.scale = 1
        summary = '\n'.join(
            f'  {t["trial"]}. {t["maze"]}: {t["points"]}pts, {t["duration"]:.1f}s'
            for t in self.trial_log
        )
        self.message_text.text = (
            f'Experiment Complete!\n\n'
            f'{summary}\n\n'
            f'Press ESC to exit'
        )
        print('\n=== Experiment Complete ===')
        for t in self.trial_log:
            print(f'  Trial {t["trial"]}: {t["maze"]} — {t["points"]}pts, {t["duration"]:.1f}s')

    def update(self):
        # --- Instructions: wait for SPACE ---
        if self.state == STATE_INSTRUCTIONS:
            if confirm_pressed():
                self._show_fixation()

        # --- Fixation: auto-advances via invoke ---
        elif self.state == STATE_FIXATION:
            pass

        # --- Maze: game loop ---
        elif self.state == STATE_MAZE:
            # Collectible proximity check
            for item in self.collectibles[:]:
                entity, dobj = item
                dx = self.player.x - entity.x
                dz = self.player.z - entity.z
                dist = math.sqrt(dx * dx + dz * dz)
                if dist < dobj.trigger_radius:
                    self.points += dobj.points_granted
                    self.score_text.text = f'Stars: {self.points} / {self.exit_threshold}'
                    destroy(entity)
                    self.collectibles.remove(item)
                    self.trigger.send(TRIG_COLLECT_BASE + self.points)
                    print(f'  Collected! {self.points}/{self.exit_threshold}')
                    # Log collection event
                    if self._traj_writer:
                        t = pytime.time() - self.trial_start_time
                        self._traj_writer.writerow([
                            self.trial_index + 1,
                            self._current_maze_name,
                            f'{t:.3f}',
                            f'{self.player.x:.4f}',
                            f'{self.player.y:.4f}',
                            f'{self.player.z:.4f}',
                            f'{self.player.rotation_y:.2f}',
                            f'collect_{self.points}',
                        ])

                    if self.points >= self.exit_threshold:
                        self.completed = True
                        self.score_text.text = f'COMPLETE! All {self.exit_threshold} Stars!'
                        self.score_text.color = color.lime
                        duration = pytime.time() - self.trial_start_time
                        self.trigger.send(TRIG_TRIAL_COMPLETE)
                        # Brief delay then show feedback
                        invoke(self._end_maze_with_feedback, duration, delay=1.5)

            # HUD + trajectory logging
            if self.player:
                self.info_text.text = (
                    f'x={self.player.x:.1f}  z={self.player.z:.1f}  '
                    f'angle={self.player.rotation_y:.0f}'
                )
                # Write trajectory row each frame
                if self._traj_writer:
                    t = pytime.time() - self.trial_start_time
                    self._traj_writer.writerow([
                        self.trial_index + 1,
                        self._current_maze_name,
                        f'{t:.3f}',
                        f'{self.player.x:.4f}',
                        f'{self.player.y:.4f}',
                        f'{self.player.z:.4f}',
                        f'{self.player.rotation_y:.2f}',
                        '',
                    ])

            pass  # spacebar LED handled via input()

            # ESC during maze = skip trial
            if held_keys['escape']:
                duration = pytime.time() - self.trial_start_time
                self.trigger.send(TRIG_TRIAL_ESCAPE)
                self._end_maze_with_feedback(duration)

        # --- Feedback: wait for SPACE ---
        elif self.state == STATE_FEEDBACK:
            if confirm_pressed():
                self._end_trial()

        # --- Done: wait for ESC ---
        elif self.state == STATE_DONE:
            if held_keys['escape']:
                application.quit()

    def input(self, key):
        """Handle key events for debug LED."""
        if self.state == STATE_MAZE:
            if key == 'space':
                self.trigger.led_on()
            elif key == 'space up':
                self.trigger.led_off()

    def _reset_to_menu(self):
        """Reset window state after maze ends (camera, mouse, background)."""
        from ursina import mouse, scene
        # Restore camera to default (unparent from destroyed player)
        camera.parent = scene
        camera.position = (0, 0, 0)
        camera.rotation = (0, 0, 0)
        camera.fov = 90
        # Restore UI camera scale (gets disrupted when FPC is destroyed)
        camera.ui.scale = (20, 20, 1)
        # Unlock mouse for menu screens
        mouse.locked = False
        mouse.visible = True
        # Dark background via Panda3D native clear color
        try:
            application.base.setBackgroundColor(0.12, 0.12, 0.12, 1)
        except Exception:
            pass

    def _close_traj_file(self):
        """Flush and close the trajectory file for this trial."""
        if self._traj_file:
            self._traj_file.close()
            self._traj_file = None
            self._traj_writer = None

    def _end_maze_with_feedback(self, duration):
        """Transition from maze to feedback."""
        if self.state != STATE_MAZE:
            return  # guard against double-invoke
        self._close_traj_file()
        clear_maze_scene()
        self.player = None
        self._reset_to_menu()
        self.score_text.color = color.yellow
        self._show_feedback(duration)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Maze experiment with trial sequencing')
    parser.add_argument('mazes', nargs='+', help='One or more .maz files')
    parser.add_argument('--repeats', type=int, default=2, help='Number of repetitions (default: 2)')
    parser.add_argument('--seed', type=int, default=None, help='Random seed for reproducibility')
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    app = Ursina(title='Maze Experiment', borderless=False, size=(1024, 768))
    window.fps_counter.enabled = False
    # Set dark background via Panda3D native API
    application.base.setBackgroundColor(0.12, 0.12, 0.12, 1)

    from ursina import mouse
    mouse.locked = False
    mouse.visible = True

    trigger = EEGTrigger()
    exp = Experiment(maze_files=args.mazes, repeats=args.repeats, trigger=trigger)
    try:
        app.run()
    finally:
        trigger.close()


if __name__ == '__main__':
    main()
