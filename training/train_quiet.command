#!/bin/bash
# Double-click to train quietly: only the small efficient cores, cool and silent but slower.
cd "$(dirname "$0")"
python3 train_long.py --quiet "$@"
