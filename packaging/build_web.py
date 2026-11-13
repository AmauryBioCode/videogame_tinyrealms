"""Build the browser version of Tiny Realms, for itch.io.

    python packaging/build_web.py          build dist/TinyRealms-web.zip, ready to upload
    python packaging/build_web.py --test   build, then play it at http://localhost:8000

It uses pygbag (installed automatically), which turns a Pygame game into a web page.
Only what the game needs is copied: the code, assets and trained_ai, not the big
texture_pack or music folders.
"""
import base64
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CODE = ["main.py"]  # it starts the game, whose code is in the game folder
FOLDERS = ["game", "assets", "trained_ai"]
SOURCE = os.path.join(ROOT, "build", "web_src", "tinyrealms")  # what pygbag packs
ZIP = os.path.join(ROOT, "dist", "TinyRealms-web.zip")


def copy_game():
    """A clean folder with only the files the game needs."""
    if os.path.exists(SOURCE):
        shutil.rmtree(SOURCE)
    os.makedirs(SOURCE)
    for name in CODE:
        shutil.copy(os.path.join(ROOT, name), SOURCE)
    for name in FOLDERS:
        shutil.copytree(os.path.join(ROOT, name), os.path.join(SOURCE, name),
                        ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"))
    icon = os.path.join(ROOT, "packaging", "web_icon.png")  # Sir Pebble, in the browser tab
    if not os.path.exists(icon):
        icon = os.path.join(ROOT, "packaging", "icon.png")
    shutil.copy(icon, os.path.join(SOURCE, "favicon.png"))


TEMPLATE = os.path.join(ROOT, "packaging", "web_template.tmpl")  # the page around the game
PAGE = os.path.join(ROOT, "build", "web_page.tmpl")  # the same, with its pictures inside


def data_url(path, kind):
    with open(path, "rb") as f:
        return f"data:{kind};base64," + base64.b64encode(f.read()).decode()


def make_page():
    """The page shown while the game loads: a picture of the menu (packaging/loading.jpg), inside the page."""
    picture = os.path.join(ROOT, "packaging", "loading.jpg")
    with open(TEMPLATE, encoding="utf-8") as f:
        page = f.read()
    page = page.replace("TR_SPLASH_IMAGE", data_url(picture, "image/jpeg") if os.path.exists(picture) else "")
    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(page)


def pygbag(*options):
    """Run pygbag on the clean folder, installing it first if needed."""
    try:
        import pygbag  # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pygbag"])
    icon = os.path.join(SOURCE, "favicon.png")  # given in full: pygbag looks for it in the current folder
    template = ["--template", PAGE] if os.path.exists(PAGE) else []
    subprocess.check_call([sys.executable, "-m", "pygbag", *options, "--title", "Tiny Realms", "--icon", icon,
                           *template, SOURCE])


def make_zip():
    """itch.io wants a zip with index.html at its top."""
    web = os.path.join(SOURCE, "build", "web")
    os.makedirs(os.path.dirname(ZIP), exist_ok=True)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for name in os.listdir(web):
            z.write(os.path.join(web, name), name)
    print(f"\nReady to upload: {ZIP}")


def main():
    copy_game()
    if os.path.exists(TEMPLATE):
        make_page()
    pygbag("--build")
    make_zip()
    if "--test" in sys.argv:
        print("Open http://localhost:8000 in your browser. Stop with Ctrl-C.")
        pygbag()


if __name__ == "__main__":
    main()
