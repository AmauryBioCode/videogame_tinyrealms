#!/bin/bash
# Double-click to train the computer players. Close the window (or Ctrl+C) to stop: the best players are kept.
cd "$(dirname "$0")"
python3 train_long.py "$@"
