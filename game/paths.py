"""Where the game's folders are: the assets and trained_ai folders sit next to this game folder."""
import os
import sys

# the Mac or Windows app keeps everything in one folder (sys._MEIPASS); otherwise, one level above game/
ROOT = getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
