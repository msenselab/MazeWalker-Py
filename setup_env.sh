#!/bin/bash
# Set up the Python virtual environment for MazeWalker-Py
#
# Requirements: Python 3.11 (PsychoPy does not yet support 3.12+)
#
# Usage:
#   ./setup_env.sh          # uses uv if available, falls back to pip
#   source .venv/bin/activate
#   python pywalker/maze_renderer.py maze/Maze220925.maz

set -e

PYTHON=${PYTHON:-python3.11}

# Check Python version
if ! command -v "$PYTHON" &>/dev/null; then
    echo "Error: $PYTHON not found. Install Python 3.11 first."
    echo "  brew install python@3.11   # macOS"
    echo "  uv python install 3.11     # or via uv"
    exit 1
fi

echo "Using $($PYTHON --version)"

# Create venv
if command -v uv &>/dev/null; then
    echo "Creating venv with uv..."
    uv venv .venv --python 3.11
    echo "Installing dependencies with uv..."
    uv pip install --python .venv/bin/python -r requirements.txt
else
    echo "Creating venv with venv module..."
    $PYTHON -m venv .venv
    echo "Installing dependencies with pip..."
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
fi

echo ""
echo "Done! Activate with:"
echo "  source .venv/bin/activate"
echo ""
echo "Run a maze:"
echo "  python pywalker/maze_renderer.py maze/Maze220925.maz"
