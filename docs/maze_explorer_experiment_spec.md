# Maze Explorer Experiment Specification

## 1. Purpose
This document defines the current implementation of the procedural Maze Explorer experiment in `pywalker/Maze explore.py`, including software dependencies, environment versions, experiment flow, trigger mapping, and behavioral outputs.

## 2. Software Requirements

### 2.1 Python
- Python 3.11 (recommended for this repository)

### 2.2 Required Packages
From `requirements.txt`:

- `ursina>=7.0.0`
- `pyserial`
- `pillow`
- `pygame`
- `./LabJackPython` (local package path in this repo)

Notes:
- `pyserial`, `pillow`, and `pygame` are currently unpinned in `requirements.txt`.
- For strict reproducibility, pin exact versions after environment lock/testing.

### 2.3 Rendering/Engine Stack
- Ursina engine (built on Panda3D)
- First-person controller from `ursina.prefabs.first_person_controller`

## 3. Run Instructions

From repository root:

```bash
python pywalker/"Maze explore.py"
```

Control scheme during TASK:
- `W/A/S/D`: Move
- Mouse: Look
- `Space`: Advance from instruction/feedback/rest screens
- `Esc`: Skip current trial
- `Shift+Q`: Exit (after completion)

## 4. Experiment Design

## 4.1 Conditions
Two difficulty conditions are used:
- `easy`: 1 star target
- `hard`: 3 star targets

Current maze dimensions:
- Easy: `6 x 6`
- Hard: `6 x 6`

## 4.2 Block and Trial Structure
The experiment is generated as:
- `3` blocks total
- Per block: `3 easy + 3 hard` trials
- `6` trials per block
- `18` trials total

Randomization policy:
- Within each block, easy and hard trials are shuffled.
- Block order is fixed (Block 1 -> Block 2 -> Block 3).

## 4.3 State Machine
Per trial lifecycle:
1. `INSTRUCTION`
2. `FIXATION`
3. `TASK`
4. `FEEDBACK`
5. `BLOCK_REST` (only at block boundaries)
6. `DONE` (after final trial)

Fixation duration:
- 1 second before TASK start.

## 4.4 Difficulty Logic for Star Placement
- Easy: random sampling of 1 star from non-start cells.
- Hard: random sampling with minimum inter-star distance constraint.

Hard-mode spacing rule:
- `HARD_MIN_STAR_CELL_DIST = 3.0` (Euclidean distance in cell grid coordinates)
- If random retries fail, a greedy max-spacing fallback is used.

## 5. Trigger Code Map (4-bit Compatible)

- `1`: Fixation onset
- `2`: Maze start (easy)
- `3`: Maze start (hard)
- `4`: Easy star 1 collected
- `5`: Hard star 1 collected
- `6`: Hard star 2 collected
- `7`: Hard star 3 collected
- `8`: Trial complete
- `9`: Trial escaped/skipped
- `10`: Block rest start
- `11`: Block rest end

## 6. Behavioral and Task Output Files

At runtime, three CSV files are written in the current working directory:

### 6.1 Trial Summary
File: `maze_experiment.csv`

Columns:
- `trial`
- `block`
- `condition`
- `rows`
- `cols`
- `n_stars`
- `collected`
- `duration_s`
- `completed` (1 = completed, 0 = skipped)

Write timing:
- One row at trial end.

### 6.2 Trajectory Log
File: `trajectory.csv`

Columns:
- `trial`
- `time_s`
- `x`
- `z`
- `event`

Write timing:
- Every 0.1 s during TASK (`event` is empty for regular samples)
- Extra event row on collection (`collect_1`, `collect_2`, `collect_3`)

### 6.3 Maze Geometry Log
File: `maze_walls.csv`

Columns:
- `trial`
- `x`
- `z`
- `sx`
- `sz`

Write timing:
- At TASK start, after maze generation.

## 7. Current Interaction and Movement Parameters

- Cell size: `CELL = 5`
- Wall height: `WALL_HEIGHT = 5`
- Wall thickness: `WALL_THICK = 0.32`
- Player speed: `6`
- Player gravity: `1`
- Camera near clip: `0.005`
- Mouse sensitivity: `Vec2(60, 60)`

These values were tuned to improve movement smoothness while reducing wall clipping artifacts.

## 8. Reproducibility Recommendations

To improve reproducibility for formal experiments:
- Set and log a random seed per participant/session.
- Pin package versions in `requirements.txt`.
- Archive this spec together with the exact script commit hash.
- Save outputs with timestamped filenames per session.

## 9. Suggested Session Metadata (Optional)

For analysis-ready datasets, store a sidecar metadata file (JSON/CSV) with:
- Subject ID
- Session date/time
- Script version/commit hash
- Random seed
- Display resolution and refresh rate
- Input device (mouse/controller)
- Trigger backend mode (mock/serial/LabJack)
