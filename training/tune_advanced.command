#!/bin/bash
# Double-click to tune the Advanced AI for every kind of game. Close the window (or Ctrl+C) to stop:
# what is tuned is kept, and double-clicking again goes on where it stopped.
cd "$(dirname "$0")"
python3 tune_advanced.py "$@"
