#!/bin/bash
cd "$(dirname "$0")"
python3 -c "import pygame" 2>/dev/null || python3 -m pip install pygame-ce
python3 main.py
