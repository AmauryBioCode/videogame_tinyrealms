"""Tiny Realms: start the game with  python main.py

The game's code is in the game folder, its pictures and sounds in assets, the computer players in trained_ai."""
import asyncio  # noqa: F401  the browser version looks here for what the game needs:
import os
import sys

import pygame  # noqa: F401  pygame and asyncio must be imported in this file

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "game"))

import app  # noqa: E402

if __name__ == "__main__":
    app.run()
