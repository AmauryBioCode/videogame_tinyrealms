"""The player's settings: music and sound volumes, which music plays, and the colorblind help.
They are saved like the achievements: in a file on a computer, in the browser's storage online."""
import json
import os
import sys

WEB = sys.platform == "emscripten"
PATH = os.path.join(os.path.expanduser("~"), ".tiny_realms", "settings.json")
WEB_KEY = "tiny_realms_settings"
DEFAULTS = {"music": 0.5, "sounds": 0.7, "track": "usual", "colorblind": False}
TRACKS = [("usual", "Peaceful Town"), ("quiet_lake", "Quiet Lake")]  # "usual": the game's own piece


def load():
    """The saved settings, with the defaults for anything not saved yet."""
    data = {}
    try:
        if WEB:
            from platform import window  # the browser's page, in the web version
            text = window.localStorage.getItem(WEB_KEY)
        else:
            with open(PATH) as f:
                text = f.read()
        data = json.loads(text) if text else {}
    except Exception:
        pass  # nothing saved yet, or the save can't be read
    return {key: type(value)(data.get(key, value)) if isinstance(data.get(key, value), (int, float, str, bool))
            else value for key, value in DEFAULTS.items()}


def save(settings):
    """Keep the settings for the next time the game is opened."""
    text = json.dumps(settings, indent=1)
    try:
        if WEB:
            from platform import window
            window.localStorage.setItem(WEB_KEY, text)
        else:
            os.makedirs(os.path.dirname(PATH), exist_ok=True)
            with open(PATH, "w") as f:
                f.write(text)
    except Exception:
        pass  # can't save: the settings still work until the game is closed
