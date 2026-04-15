# Easy/Hard Difficulty Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add easy (1 star) and hard (3 stars) difficulty conditions to the maze experiment, structured as 3 blocks × 6 trials (3 easy + 3 hard per block, randomized within block), with updated EEG trigger codes that encode condition.

**Architecture:** Two separate maze pools are generated (easy: 1 star, hard: 3 stars, both 6×6). The experiment trial list is built block-by-block, with 3 easy + 3 hard trials per block drawn randomly from their respective pools and shuffled within each block. A rest screen with block-start/end triggers separates blocks. The old/new context logic is removed entirely.

**Tech Stack:** Python 3.11, Ursina (Panda3D), LabJack U3 (pylabjack), CSV logging

---

## Trigger Code Reference (4-bit, max 15)

| Value | Event |
|-------|-------|
| 1  | Fixation onset |
| 2  | Maze start — easy |
| 3  | Maze start — hard |
| 4  | Easy: star 1 collected |
| 5  | Hard: star 1 collected |
| 6  | Hard: star 2 collected |
| 7  | Hard: star 3 collected |
| 8  | Trial complete |
| 9  | Trial escaped (ESC) |
| 10 | Block rest start |
| 11 | Block rest end |

---

## Task 1: Update trigger constants in trigger.py and trigger_debug.py

**Files:**
- Modify: `pywalker/trigger.py:48-53`
- Modify: `pywalker/trigger_debug.py:18-23`

**Step 1: Update trigger.py constants**

Replace the block starting at line 48 in `pywalker/trigger.py`:

```python
# Trigger code constants (4-bit compatible: 1-15)
TRIG_FIXATION         = 1
TRIG_MAZE_START_EASY  = 2
TRIG_MAZE_START_HARD  = 3
TRIG_EASY_STAR_1      = 4   # easy condition: only 1 star
TRIG_HARD_STAR_1      = 5   # hard condition: star 1 of 3
TRIG_HARD_STAR_2      = 6
TRIG_HARD_STAR_3      = 7
TRIG_TRIAL_COMPLETE   = 8
TRIG_TRIAL_ESCAPE     = 9
TRIG_BLOCK_REST_START = 10
TRIG_BLOCK_REST_END   = 11


def star_trigger(condition: str, star_index: int) -> int:
    """Return trigger code for collecting a star.

    condition: 'easy' or 'hard'
    star_index: 0-indexed (0 = first star)
    """
    if condition == 'easy':
        return TRIG_EASY_STAR_1
    else:
        return [TRIG_HARD_STAR_1, TRIG_HARD_STAR_2, TRIG_HARD_STAR_3][min(star_index, 2)]
```

**Step 2: Mirror same constants in trigger_debug.py**

Replace lines 18-23 in `pywalker/trigger_debug.py` with the same constants block as above (same names, same values). Also update the `star_trigger` function to match.

**Step 3: Update the `__main__` test block in trigger_debug.py**

Replace the `codes` list at the bottom of `trigger_debug.py` with:

```python
codes = [
    (TRIG_FIXATION,         'Fixation onset'),
    (TRIG_MAZE_START_EASY,  'Maze start — easy'),
    (TRIG_MAZE_START_HARD,  'Maze start — hard'),
    (TRIG_EASY_STAR_1,      'Easy: star 1'),
    (TRIG_HARD_STAR_1,      'Hard: star 1'),
    (TRIG_HARD_STAR_2,      'Hard: star 2'),
    (TRIG_HARD_STAR_3,      'Hard: star 3'),
    (TRIG_TRIAL_COMPLETE,   'Trial complete'),
    (TRIG_TRIAL_ESCAPE,     'Trial escape'),
    (TRIG_BLOCK_REST_START, 'Block rest start'),
    (TRIG_BLOCK_REST_END,   'Block rest end'),
]
```

**Step 4: Verify trigger_debug.py runs without error**

```bash
cd D:/MazeWalker-Py
maze/.venv/Scripts/python pywalker/trigger_debug.py
```

Expected: 11 trigger lines printed to console, no errors.

**Step 5: Commit**

```bash
git add pywalker/trigger.py pywalker/trigger_debug.py
git commit -m "feat: update trigger constants for easy/hard + block rest"
```

---

## Task 2: Add --num-stars to generate_mazes.py

**Files:**
- Modify: `GenerateNewMazes/generate_mazes.py`

**Step 1: Add --num-stars argument**

In the `main()` function, add after the existing `ap.add_argument('--tolerance', ...)` line:

```python
ap.add_argument('--num-stars', type=int, default=3,
                help='Number of stars per maze (default: 3)')
```

**Step 2: Pass num_stars through to generation**

Replace the module-level `NUM_STARS = 3` constant with a parameter passed through the call chain. The cleanest approach is to keep the module-level default but override it in `main()` before generation:

After `args = ap.parse_args()`, add:

```python
import GenerateNewMazes.generate_mazes as _gm
_gm.NUM_STARS = args.num_stars
```

Actually, since the script is run directly (not imported), use a simpler approach: just reassign the global at the top of `main()` before the calibration phase:

```python
global NUM_STARS, MIN_STAR_SEPARATION, MIN_STAR_DISTANCE
NUM_STARS = args.num_stars
if NUM_STARS == 1:
    MIN_STAR_SEPARATION = 0   # irrelevant with 1 star
    MIN_STAR_DISTANCE   = 2   # easier to place 1 star
```

**Step 3: Generate the two pools**

Run both commands from `GenerateNewMazes/`:

```bash
cd D:/MazeWalker-Py/GenerateNewMazes
python generate_mazes.py --num-stars 1 --count 50 --output-dir mazes/easy
python generate_mazes.py --num-stars 3 --count 50 --output-dir mazes/hard
```

Expected: `mazes/easy/Easy001.maz … Easy050.maz` and `mazes/hard/Hard001.maz … Hard050.maz`.

Wait — note the filename prefix comes from the loop `f'Maze{i:03d}.maz'`. Add a `--prefix` argument too:

```python
ap.add_argument('--prefix', default='Maze',
                help='Filename prefix (default: Maze)')
```

Then change the path line in the generation loop to:
```python
path = out / f'{args.prefix}{i:03d}.maz'
```

Rerun:
```bash
python generate_mazes.py --num-stars 1 --count 50 --output-dir mazes/easy --prefix Easy
python generate_mazes.py --num-stars 3 --count 50 --output-dir mazes/hard --prefix Hard
```

**Step 4: Verify output**

```bash
ls mazes/easy/ | wc -l   # should be 50
ls mazes/hard/ | wc -l   # should be 50
```

**Step 5: Commit**

```bash
cd D:/MazeWalker-Py
git add GenerateNewMazes/generate_mazes.py GenerateNewMazes/mazes/
git commit -m "feat: add --num-stars and --prefix to generate_mazes; generate easy/hard pools"
```

---

## Task 3: Rewrite experiment.py trial sequencing

**Files:**
- Modify: `pywalker/experiment.py`

This is the largest change. The old/new context logic is removed and replaced with condition-based block sequencing.

**Step 1: Update imports**

Replace the trigger import line (line 32) with:

```python
from pywalker.trigger import (
    EEGTrigger,
    TRIG_FIXATION, TRIG_MAZE_START_EASY, TRIG_MAZE_START_HARD,
    TRIG_TRIAL_COMPLETE, TRIG_TRIAL_ESCAPE,
    TRIG_BLOCK_REST_START, TRIG_BLOCK_REST_END,
    star_trigger,
)
```

**Step 2: Add a helper to build the trial list**

Add this function just above the `Experiment` class definition:

```python
N_BLOCKS          = 3
EASY_PER_BLOCK    = 3
HARD_PER_BLOCK    = 3
TRIALS_PER_BLOCK  = EASY_PER_BLOCK + HARD_PER_BLOCK  # 6


def build_trial_list(easy_dir: str, hard_dir: str) -> list[dict]:
    """Build 3 blocks × 6 trials (3 easy + 3 hard), randomized within block.

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
```

**Step 3: Update Experiment.__init__ signature and trial list**

Change the `__init__` signature from:

```python
def __init__(self, maze_files: list[str], repeats: int = 1, trigger: EEGTrigger = None, **kwargs):
```

to:

```python
def __init__(self, easy_dir: str, hard_dir: str, trigger: EEGTrigger = None, seed: int = None, **kwargs):
```

Remove all old/new context logic. Replace the trial list construction with:

```python
if seed is not None:
    random.seed(seed)
self.trial_list = build_trial_list(easy_dir, hard_dir)
self.trial_index = 0
self.current_block = 1
```

**Step 4: Add block rest state**

Add a new state constant at the top with the other states:

```python
STATE_BLOCK_REST = 'block_rest'
```

Add the `_show_block_rest()` method:

```python
def _show_block_rest(self):
    """Show rest screen between blocks."""
    self.state = STATE_BLOCK_REST
    self.state_start_time = pytime.time()
    block_done = self.current_block
    block_next = block_done + 1
    self.message_text.text = (
        f'Block {block_done} / {N_BLOCKS} complete\n\n'
        f'Take a short break.\n\n'
        f'Press SPACE or A to start Block {block_next}'
    )
    self.trigger.send(TRIG_BLOCK_REST_START)
```

**Step 5: Update _end_trial to insert block rest**

In `_end_trial()`, replace the current advance logic with:

```python
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
        # Moving to a new block — show rest screen first
        self.current_block = next_trial['block']
        self._show_block_rest()
    else:
        self._show_instructions()
```

**Step 6: Update update() to handle STATE_BLOCK_REST**

In the `update()` method, add a new elif branch:

```python
elif self.state == STATE_BLOCK_REST:
    if confirm_pressed():
        self.trigger.send(TRIG_BLOCK_REST_END)
        self._show_instructions()
```

**Step 7: Update _start_maze trigger**

In `_start_maze()`, replace:

```python
self.trigger.send(TRIG_MAZE_START)
```

with:

```python
condition = self.trial_list[self.trial_index]['condition']
trig_start = TRIG_MAZE_START_EASY if condition == 'easy' else TRIG_MAZE_START_HARD
self.trigger.send(trig_start)
```

**Step 8: Update star collection trigger**

In the collectible proximity check in `update()`, replace:

```python
self.trigger.send(TRIG_COLLECT_BASE + self.points)
```

with:

```python
condition = self.trial_list[self.trial_index]['condition']
self.trigger.send(star_trigger(condition, self.points - 1))
```

**Step 9: Update CSV headers and trial row**

In `__init__`, change the trials CSV header from:

```python
w.writerow(['trial', 'maze', 'duration_s', 'stars_collected', 'stars_total', 'completed'])
```

to:

```python
w.writerow(['block', 'trial', 'condition', 'maze', 'duration_s', 'stars_collected', 'stars_total', 'completed'])
```

In `_show_feedback()`, change the writerow call to:

```python
csv.writer(f).writerow([
    trial_num_in_block,
    trial['block'],
    trial['condition'],
    maze_name,
    f'{duration:.3f}',
    self.points,
    self.exit_threshold,
    self.completed,
])
```

Where `trial_num_in_block` = `(self.trial_index % TRIALS_PER_BLOCK) + 1` and `trial` = `self.trial_list[self.trial_index]`.

**Step 10: Update _show_instructions to show condition**

In `_show_instructions()`, update the message text to include condition:

```python
condition = self.trial_list[self.trial_index]['condition']
self.message_text.text = (
    f'Block {trial["block"]} — Trial {trial_num_in_block} / {TRIALS_PER_BLOCK}\n'
    f'Difficulty: {condition.upper()}\n\n'
    f'Collect all stars!\n'
    f'WASD / Left stick to move\n'
    f'Mouse / Right stick to look\n\n'
    f'Press SPACE or A to start'
)
```

**Step 11: Update main() argument parser**

Replace the current argument parser in `main()` with:

```python
parser = argparse.ArgumentParser(description='Maze experiment — easy/hard conditions')
parser.add_argument('--easy-dir', default='GenerateNewMazes/mazes/easy',
                    help='Directory of easy maze files (1 star)')
parser.add_argument('--hard-dir', default='GenerateNewMazes/mazes/hard',
                    help='Directory of hard maze files (3 stars)')
parser.add_argument('--seed', type=int, default=None, help='Random seed')
args = parser.parse_args()
```

And update the `Experiment(...)` call to:

```python
exp = Experiment(easy_dir=args.easy_dir, hard_dir=args.hard_dir,
                 trigger=trigger, seed=args.seed)
```

**Step 12: Smoke-test the experiment**

```bash
cd D:/MazeWalker-Py
maze/.venv/Scripts/python pywalker/experiment.py
```

Expected: instruction screen for Block 1 appears, condition shown, can navigate through trials, rest screen appears after trial 6, experiment ends after trial 18.

**Step 13: Commit**

```bash
git add pywalker/experiment.py
git commit -m "feat: replace old/new context with easy/hard blocks (3x6 trials)"
```

---

## Task 4: Remove old trigger imports / dead code cleanup

**Files:**
- Modify: `pywalker/experiment.py`

**Step 1: Remove unused imports**

Remove `TRIG_COLLECT_BASE` from any remaining import lines in `experiment.py` (it no longer exists in trigger.py after Task 1).

Grep to confirm nothing old remains:

```bash
grep -n "TRIG_COLLECT_BASE\|old_context\|new_context\|repeats" pywalker/experiment.py
```

Expected: no output.

**Step 2: Commit**

```bash
git add pywalker/experiment.py
git commit -m "chore: remove dead code after easy/hard refactor"
```

---

## Final verification checklist

- [ ] `python pywalker/trigger_debug.py` prints 11 trigger lines cleanly
- [ ] `GenerateNewMazes/mazes/easy/` contains 50 `.maz` files
- [ ] `GenerateNewMazes/mazes/hard/` contains 50 `.maz` files  
- [ ] Running `experiment.py` shows Block/condition on instruction screen
- [ ] Trial list is 18 entries (9 easy + 9 hard across 3 blocks)
- [ ] Rest screen appears after trial 6 and trial 12
- [ ] CSV output contains columns: `block, trial, condition, maze, duration_s, stars_collected, stars_total, completed`
- [ ] Easy maze start fires trigger 2, hard fires trigger 3
- [ ] Star collection fires correct code per condition
