# Building the ADB GUI (macOS)

The **ADB-only** desktop UI lives under `gui/`. It uses the same automation core as `main.py --config` and expects **`adb` on your PATH** (Android Platform Tools).

## Run from source

From the repository root (with `venv` activated and dependencies from `requirements.txt` installed):

```bash
cd /Users/lap16932/personal/yulangv2
source venv/bin/activate
python -m gui
```

### `ModuleNotFoundError: No module named '_tkinter'` (macOS + Homebrew Python)

Homebrew’s `python@3.x` does not include Tk until you add the matching bottle:

```bash
brew install python-tk@3.13   # use 3.12 / 3.14 etc. to match `python3 --version`
python3 -c "import tkinter"   # should print nothing if OK
```

Your virtualenv uses the same interpreter, so after this install you usually **do not** need to recreate `venv`. If it still fails, recreate the venv and `pip install -r requirements.txt` again.

## Build `YulangADB.app` with PyInstaller

```bash
pip install pyinstaller
pyinstaller yulang_gui.spec
```

Output: `dist/YulangADB.app`. Open it from Finder; if macOS blocks it, use **System Settings → Privacy & Security → Open Anyway** (or ad-hoc code-sign the bundle for your machine).

Frozen builds resolve templates via `sys._MEIPASS` (see `core/screen.py` `_get_project_root()`). The spec bundles `templates/adb` into `templates/adb` inside the app.

If the app fails to import OpenCV or other native deps, re-run PyInstaller and add any missing modules to `hiddenimports` in `yulang_gui.spec` (PyInstaller’s build log usually lists them).

If PyInstaller logs **“tkinter installation is broken”**, use a Python build that includes Tcl/Tk (e.g. [python.org](https://www.python.org/downloads/) macOS installer) or install `python-tk` for your package manager so `import tkinter` works in the same venv you freeze.

## CLI parity

Export a JSON from the GUI and run:

```bash
python main.py --mode adb --config exported.json --action quick_sell
```

Use the same **checked devices** and options as in the GUI for equivalent runs.
