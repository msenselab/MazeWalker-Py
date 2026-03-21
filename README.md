# MazeWalker-Py

A Python reimplementation of [MazeSuite](http://www.mazesuite.com) MazeWalker for psychology and neuroscience research. Renders 3D mazes from MazeSuite `.maz` files using [Ursina](https://www.ursinaengine.org/) (Panda3D), with experiment control, EEG trigger support, and behavioral data logging.

## Features

- **3D maze rendering** — textured walls, curved boundary walls, floors, skybox, OBJ models
- **First-person navigation** — WASD + mouse, or Xbox/gamepad controller
- **Star collection** — proximity-triggered collectibles with score tracking
- **Trial sequencing** — randomized multi-maze experiments with instruction/fixation/feedback screens
- **Behavioral logging** — per-trial summary CSV and per-frame trajectory CSV
- **Trajectory visualization** — bird's-eye paths, speed/angle plots, collection markers
- **EEG trigger support** — serial port, parallel port, or console output
- **Wall collision** — raycasting collision for flat and curved walls

## Quick Start

```bash
# Set up environment (requires Python 3.11)
./setup_env.sh
source .venv/bin/activate

# Run a single maze
python pywalker/maze_renderer.py maze/Maze220925.maz

# Run an experiment (2 mazes × 2 repeats, randomized)
python pywalker/experiment.py maze/Maze220925.maz maze/Maze260925.maz --repeats 2

# Visualize trajectory data
python pywalker/plot_trajectory.py data/<timestamp>_trajectory.csv --save
```

## Project Structure

```
pywalker/
├── maz_parser.py        # Parse MazeSuite .maz XML files
├── maze_renderer.py     # Ursina 3D renderer (standalone or as module)
├── experiment.py        # Trial sequencer with data logging
└── plot_trajectory.py   # Trajectory visualization

maze/                    # MazeSuite .maz files
Library/                 # Textures, OBJ models, audio (not tracked)
data/                    # Experiment output CSVs (not tracked)
```

## Maze File Format

MazeSuite `.maz` files are XML containing:
- **Walls** — flat quads (4 vertices) with textures
- **CurvedWalls** — arc-shaped boundary walls (triangle mesh geometry)
- **Floors** — ground plane with texture tiling
- **StartPositions** — player spawn point and view angle
- **DynamicObjects** — collectible items (stars) with proximity triggers
- **StaticModels** — OBJ models placed in the scene (chairs, etc.)
- **Global settings** — move speed, skybox, point thresholds, start message

## Controls

| Input | Action |
|---|---|
| W / Left stick up | Move forward |
| S / Left stick down | Move backward |
| A / Left stick left | Strafe left |
| D / Left stick right | Strafe right |
| Mouse / Right stick | Look around |
| ESC | End trial / quit |
| SPACE / A button | Confirm / continue |

## Data Output

**Trial summary** (`*_trials.csv`):
```
trial, maze, duration_s, stars_collected, stars_total, completed
```

**Trajectory** (`*_trajectory.csv`):
```
trial, maze, time_s, x, y, z, angle, event
```

Events: `collect_1`, `collect_2`, etc. when stars are collected.

## Dependencies

- Python 3.11 (PsychoPy requirement)
- Ursina (Panda3D wrapper for 3D rendering)
- PsychoPy (experiment control, EEG triggers)
- pygame (gamepad input on macOS)
- pyserial (serial port triggers)

## Origin

Migrated from the C++ [MazeWalker](https://github.com/AyazLab/MazeSuite) (part of MazeSuite by Ayaz Lab) to enable integration with Python-based experiment tools and EEG/fNIRS systems.
