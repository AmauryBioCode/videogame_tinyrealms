# PyInstaller recipe: builds "Tiny Realms" as a Mac app or a Windows program.
# Run from the game folder:  pyinstaller packaging/tiny_realms.spec
import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ICON = os.path.join(SPECPATH, "icon.png")

a = Analysis(
    [os.path.join(ROOT, "main.py")],
    pathex=[ROOT, os.path.join(ROOT, "game")],
    datas=[(os.path.join(ROOT, "assets"), "assets"), (os.path.join(ROOT, "trained_ai"), "trained_ai")],
    excludes=["pytest", "tkinter", "numpy"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Tiny Realms", console=False, icon=ICON)
coll = COLLECT(exe, a.binaries, a.datas, name="Tiny Realms")
if sys.platform == "darwin":
    app = BUNDLE(coll, name="Tiny Realms.app", icon=ICON, bundle_identifier="com.amaury.tinyrealms",
                 info_plist={"NSHighResolutionCapable": True, "CFBundleShortVersionString": "1.0"})
