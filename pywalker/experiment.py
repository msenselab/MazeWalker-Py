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
from pywalker.trigger import (
    EEGTrigger,
    TRIG_FIXATION, TRIG_MAZE_START_EASY, TRIG_MAZE_START_HARD,
    TRIG_TRIAL_COMPLETE, TRIG_TRIAL_ESCAPE,
    TRIG_BLOCK_REST_START, TRIG_BLOCK_REST_END,
    star_trigger,
)

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
STATE_BLOCK_REST = 'block_rest'


N_BLOCKS         = 3
EASY_PER_BLOCK   = 3
HARD_PER_BLOCK   = 3
TRIALS_PER_BLOCK = EASY_PER_BLOCK + HARD_PER_BLOCK  # 6


def build_trial_list(easy_dir: str, hard_dir: str) -> list[dict]:
    """Build 3 blocks x 6 trials (3 easy + 3 hard), randomized within block.

    Each trial dict: {'condition': 'easy'|'hard', 'maze_file': str, 'block': int}
    Draws without replacement from each pool across all blocks.
    """
    easy_files = sorted(Path(easy_dir).glob('*.maz'))
    hard_files = sorted(Path(hard_dir).glob('*.maz'))

    needed_easy = N_BLOCKS * EASY_PER_BLOCK  # 9
    needed_hard = N_BLOCKS * HARD_PER_BLOCK  # 9

    if len(easy_files) < needed_easy:
        raise ValueError(f'Need {needed_easy} easy mazes, found {len(easy_files)}')
    if len(hard_files) < needed_hard:
        raise ValueError(f'Need {needed_hard} hard mazes, found {len(hard_files)}')

    easy_pool = random.sample(easy_files, needed_easy)
    hard_pool = random.sample(hard_files, needed_hard)

    trials = []
    for b in range(N_BLOCKS):
        block_trials = []
        for i in range(EASY_PER_BLOCK):
            block_trials.append({
                'condition': 'easy',
                'maze_file': str(easy_pool[b * EASY_PER_BLOCK + i]),
                'block': b + 1,
            })
        for i in range(HARD_PER_BLOCK):
            block_trials.append({
                'condition': 'hard',
                'maze_file': str(hard_pool[b * HARD_PER_BLOCK + i]),
                'block': b + 1,
            })
        random.shuffle(block_trials)
        trials.extend(block_trials)
    return trials


class Experiment(Entity):
    """
    Manages the trial sequence within a single Ursina app.

    Flow per trial:
      INSTRUCTIONS → FIXATION → MAZE → FEEDBACK → (next trial or DONE)
    """

    def __init__(self, easy_dir: str, hard_dir: str, trigger: EEGTrigger = None, seed: int = None, **kwargs):
        super().__init__(**kwargs)
        self.trigger = trigger or EEGTrigger()

        if seed is not None:
            random.seed(seed)
        self.trial_list = build_trial_list(easy_dir, hard_dir)
        self.trial_index = 0
        self.current_block = 1
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
            w.writerow(['block', 'trial_in_block', 'condition', 'maze', 'duration_s', 'stars_collected', 'stars_total', 'completed'])
        with open(self.traj_csv_path, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['trial', 'maze', 'time_s', 'x', 'y', 'z', 'angle', 'event'])

        self._traj_writer = None
        self._traj_file = None
        print(f"  Data: {self.trials_csv_path}")
        print(f"  Traj: {self.traj_csv_path}")

        # Start
        print(f"\n=== Experiment loaded: {len(self.trial_list)} trials ({N_BLOCKS} blocks x {TRIALS_PER_BLOCK}) ===")
        self._show_instructions()

    def _show_instructions(self):
        """Show pre-trial instructions."""
        self.state = STATE_INSTRUCTIONS
        self.state_start_time = pytime.time()
        self.message_text.scale = 1
        trial = self.trial_list[self.trial_index]
        trial_in_block = (self.trial_index % TRIALS_PER_BLOCK) + 1
        self.message_text.text = (
            f'Block {trial["block"]} / {N_BLOCKS}  —  Trial {trial_in_block} / {TRIALS_PER_BLOCK}\n'
            f'Difficulty: {trial["condition"].upper()}\n\n'
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

        maz_file = self.trial_list[self.trial_index]['maze_file']
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
        condition = self.trial_list[self.trial_index]['condition']
        trig_start = TRIG_MAZE_START_EASY if condition == 'easy' else TRIG_MAZE_START_HARD
        self.trigger.send(trig_start)

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

        trial = self.trial_list[self.trial_index]
        trial_in_block = (self.trial_index % TRIALS_PER_BLOCK) + 1
        status = 'Complete!' if self.completed else 'Time up'
        self.message_text.text = (
            f'Trial {trial_in_block} / {TRIALS_PER_BLOCK} — {status}\n'
            f'Condition: {trial["condition"].upper()}\n'
            f'Stars: {self.points} / {self.exit_threshold}\n'
            f'Time: {duration:.1f}s\n\n'
            f'Press SPACE or A to continue'
        )
        self.score_text.text = ''
        self.info_text.text = ''

        # Log trial
        maze_name = Path(self.trial_list[self.trial_index]['maze_file']).stem
        self.trial_log.append({
            'trial': self.trial_index + 1,
            'maze': maze_name,
            'duration': duration,
            'points': self.points,
            'completed': self.completed,
        })
        # Write trial summary row
        with open(self.trials_csv_path, 'a', newline='') as f:
            csv.writer(f).writerow([
                trial['block'],
                trial_in_block,
                trial['condition'],
                maze_name,
                f'{duration:.3f}',
                self.points,
                self.exit_threshold,
                self.completed,
            ])

    def _show_block_rest(self):
        """Show rest screen between blocks."""
        self.state = STATE_BLOCK_REST
        self.state_start_time = pytime.time()
        block_done = self.current_block - 1
        block_next = self.current_block
        self.message_text.text = (
            f'Block {block_done} / {N_BLOCKS} complete\n\n'
            f'Take a short break.\n\n'
            f'Press SPACE or A to start Block {block_next}'
        )
        self.score_text.text = ''
        self.info_text.text = ''
        self.trigger.send(TRIG_BLOCK_REST_START)

    def _end_trial(self):
        """Clean up current maze and advance to next trial or block rest."""
        clear_maze_scene()
        self.player = None
        self.collectibles = []
        self.trial_index += 1

        if self.trial_index >= len(self.trial_list):
            self._show_done()
            return

        next_trial = self.trial_list[self.trial_index]
        if next_trial['block'] > self.current_block:
            self.current_block = next_trial['block']
            self._show_block_rest()
        else:
            self._show_instructions()

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
                    condition = self.trial_list[self.trial_index]['condition']
                    self.trigger.send(star_trigger(condition, self.points - 1))
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

        # --- Block rest: wait for SPACE ---
        elif self.state == STATE_BLOCK_REST:
            if confirm_pressed():
                self.trigger.send(TRIG_BLOCK_REST_END)
                self._show_instructions()

        # --- Done: wait for ESC ---
        elif self.state == STATE_DONE:
            if held_keys['escape']:
                application.quit()

    def input(self, key):
        pass  # reserved for future key handling

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
    parser = argparse.ArgumentParser(description='Maze experiment — easy/hard conditions')
    parser.add_argument('--easy-dir', default='GenerateNewMazes/mazes/easy',
                        help='Directory of easy maze files (1 star)')
    parser.add_argument('--hard-dir', default='GenerateNewMazes/mazes/hard',
                        help='Directory of hard maze files (3 stars)')
    parser.add_argument('--seed', type=int, default=None, help='Random seed')
    args = parser.parse_args()

    print(f'\n=== Experiment: {N_BLOCKS} blocks x {TRIALS_PER_BLOCK} trials = {N_BLOCKS * TRIALS_PER_BLOCK} total ===')
    print(f'  Easy dir: {args.easy_dir}')
    print(f'  Hard dir: {args.hard_dir}')

    app = Ursina(title='Maze Experiment', borderless=False, size=(1024, 768))
    window.fps_counter.enabled = False
    # Set dark background via Panda3D native API
    application.base.setBackgroundColor(0.12, 0.12, 0.12, 1)

    from ursina import mouse
    mouse.locked = False
    mouse.visible = True

    trigger = EEGTrigger()
    exp = Experiment(easy_dir=args.easy_dir, hard_dir=args.hard_dir,
                     trigger=trigger, seed=args.seed)
    try:
        app.run()
    finally:
        trigger.close()


if __name__ == '__main__':
    main()
