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
import math
import random
import time as pytime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ursina import (
    Ursina, Entity, Text,
    color, window, application, camera,
    held_keys, destroy, invoke,
)
from pywalker.maz_parser import parse_maz, resolve_assets
from pywalker.maze_renderer import build_maze_scene, clear_maze_scene, load_model


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

    def __init__(self, maze_files: list[str], repeats: int = 1, **kwargs):
        super().__init__(**kwargs)

        # Build trial list: each maze repeated, then shuffled
        self.trial_list = maze_files * repeats
        random.shuffle(self.trial_list)

        self.trial_index = 0
        self.state = STATE_INSTRUCTIONS
        self.player = None
        self.collectibles = []
        self.maze_data = None

        # Timing
        self.trial_start_time = 0
        self.state_start_time = 0
        self.trial_log = []  # list of dicts

        # HUD elements (persistent across states)
        self.message_text = Text(
            text='',
            origin=(0, 0),
            scale=1.5,
            color=color.white,
        )
        self.score_text = Text(
            text='',
            position=(-0.85, 0.45),
            scale=1.5,
            color=color.yellow,
        )
        self.info_text = Text(
            text='',
            position=(-0.85, 0.40),
            scale=1,
            color=color.white,
        )

        # Points state
        self.points = 0
        self.exit_threshold = 0
        self.completed = False

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
        trial_num = self.trial_index + 1
        total = len(self.trial_list)
        maze_name = Path(self.trial_list[self.trial_index]).stem

        self.message_text.text = (
            f'Trial {trial_num} / {total}\n'
            f'Maze: {maze_name}\n\n'
            f'Collect all stars!\n'
            f'WASD to move, mouse to look\n\n'
            f'Press SPACE to start'
        )
        self.score_text.text = ''
        self.info_text.text = ''

    def _show_fixation(self):
        """Show fixation cross before trial starts."""
        self.state = STATE_FIXATION
        self.state_start_time = pytime.time()
        self.message_text.text = '+'
        self.message_text.scale = 3
        # Auto-advance after 1 second
        invoke(self._start_maze, delay=1.0)

    def _start_maze(self):
        """Load and start a maze trial."""
        self.state = STATE_MAZE
        self.message_text.text = ''
        self.message_text.scale = 1.5

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

        if self.maze_data.settings.start_message:
            self.message_text.text = self.maze_data.settings.start_message
            invoke(setattr, self.message_text, 'text', '', delay=2.0)

    def _show_feedback(self, duration: float):
        """Show post-trial feedback."""
        self.state = STATE_FEEDBACK
        self.state_start_time = pytime.time()

        trial_num = self.trial_index + 1
        status = 'Complete!' if self.completed else 'Time up'
        self.message_text.text = (
            f'Trial {trial_num} — {status}\n'
            f'Stars: {self.points} / {self.exit_threshold}\n'
            f'Time: {duration:.1f}s\n\n'
            f'Press SPACE to continue'
        )
        self.score_text.text = ''
        self.info_text.text = ''

        # Log trial
        self.trial_log.append({
            'trial': trial_num,
            'maze': Path(self.trial_list[self.trial_index]).stem,
            'duration': duration,
            'points': self.points,
            'completed': self.completed,
        })

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
            if held_keys['space']:
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
                    print(f'  Collected! {self.points}/{self.exit_threshold}')

                    if self.points >= self.exit_threshold:
                        self.completed = True
                        self.score_text.text = f'COMPLETE! All {self.exit_threshold} Stars!'
                        self.score_text.color = color.lime
                        duration = pytime.time() - self.trial_start_time
                        # Brief delay then show feedback
                        invoke(self._end_maze_with_feedback, duration, delay=1.5)

            # HUD
            if self.player:
                self.info_text.text = (
                    f'x={self.player.x:.1f}  z={self.player.z:.1f}  '
                    f'angle={self.player.rotation_y:.0f}'
                )

            # ESC during maze = skip trial
            if held_keys['escape']:
                duration = pytime.time() - self.trial_start_time
                self._end_maze_with_feedback(duration)

        # --- Feedback: wait for SPACE ---
        elif self.state == STATE_FEEDBACK:
            if held_keys['space']:
                self._end_trial()

        # --- Done: wait for ESC ---
        elif self.state == STATE_DONE:
            if held_keys['escape']:
                application.quit()

    def _end_maze_with_feedback(self, duration):
        """Transition from maze to feedback."""
        if self.state != STATE_MAZE:
            return  # guard against double-invoke
        clear_maze_scene()
        self.player = None
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
    window.color = color.rgb(30, 30, 30)  # dark background between trials
    window.fps_counter.enabled = True

    from ursina import mouse
    mouse.locked = False
    mouse.visible = True

    Experiment(maze_files=args.mazes, repeats=args.repeats)
    app.run()


if __name__ == '__main__':
    main()
