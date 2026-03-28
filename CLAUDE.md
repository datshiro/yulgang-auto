# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**macOS requirement:** Grant Accessibility permission to Terminal (System Settings → Privacy & Security → Accessibility) for PyAutoGUI clicks to work.

## Running

```bash
# Single action, Mac mode (default)
python main.py --action quick_sell
python main.py --action open_inventory
python main.py --action complete_quest
python main.py --action do_quest
python main.py --action teleport_to_huyen_bot
python main.py --action open_menu_chuyen_doi --stones noi,2,3,huyet
python main.py --action run_chuyen_doi_program --stones noi,2,3,huyet

# ADB mode (BlueStacks/emulator)
python main.py --action quick_sell --mode adb
python main.py --action quick_sell --mode adb --adb-device emulator-5554

# Multi-device parallel via config file
python main.py --action quick_sell --config devices.json

# Loop mode
python main.py --action quick_sell --loop --loop-interval 10

# Utilities
python main.py --action list_devices
python scripts/list_apps.py --filter yulang   # find --game-app value
python scripts/adb_screenshot.py              # capture ADB screenshot for template debugging
python scripts/template_debug.py             # debug template matching
```

Key flags: `--threshold 0.65` (lower if templates don't match), `--background-capture` (screenshot without focus switch), `--no-restore-focus`.

## Architecture

**Backend abstraction** (`core/backend.py`): `MacBackend` and `ADBBackend` both implement the `Backend` protocol (capture + click). The active backend is set globally via `core.screen.set_backend()` at startup.

**Coordinate systems differ by backend:**
- `MacBackend` full-screen: PyAutoGUI screenshot coords need Retina scaling for clicks
- `MacBackend` with `window_id`: window-space coords need `_window_to_screen_coords()` conversion
- `ADBBackend`: screenshot coords = tap coords (no conversion; `uses_direct_coords = True`)

**Template resolution** (`core/screen.py`): Template names are resolved under `templates/` by default. When `--mode adb` is used, `set_template_subdir("adb")` redirects lookups to `templates/adb/`. Stone templates live in `templates/adb/stones/` and are referenced as `stones/{tag}.png`.

**Flow structure**: Each `flows/*.py` implements a single game action as a sequence of `click_template_with_retry()` / `click_template_wait_for()` calls. Flows return `bool` (success/failure). `programs/*.py` wrap flows into looping programs (e.g., `run_chuyen_doi_program` loops `run_open_menu_chuyen_doi` until failure).

**Click helper hierarchy** (`core/actions.py`):
- `click_template_wait_for()` — polls until button appears, then clicks (preferred; no fixed delay)
- `click_template_with_retry()` — retries N times with fixed delay
- `click_template()` — single attempt

**Multi-device** (`main.py`): `--config devices.json` loads a list of `{serial: "..."}` entries and runs the action in parallel via `ThreadPoolExecutor`. Each thread sets its own backend independently via `set_backend()` (note: this is a global — parallel threads sharing it may have races; each worker re-calls `set_backend` before the action).

**Mac focus management** (`core/window.py`): `run_with_game_focus()` activates the game, runs the action, then restores the previous app. `run_transient_focus()` is used per-click in background-capture mode.

## Adding New Flows

1. Create `flows/my_flow.py` with a `run_my_flow(threshold: float = 0.75) -> bool` function
2. Export it from `flows/__init__.py`
3. Add it to `handlers` dict in `main.py` and to the `--action` choices
4. Add template images to `templates/` (Mac) and/or `templates/adb/` (ADB)

## Template Images

Templates must match the game's resolution at the time of capture. Mac and ADB templates are separate (`templates/` vs `templates/adb/`). The ADB backend uses multi-scale matching (±10%) to tolerate minor resolution differences.
