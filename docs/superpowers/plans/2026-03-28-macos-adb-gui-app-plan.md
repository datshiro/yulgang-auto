# macOS ADB GUI App Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an ADB-only macOS GUI (tkinter) that edits devices and run options on-screen, runs the same multi-device automation as `main.py --config`, and can be frozen into a `.app` with PyInstaller including `templates/adb/`.

**Architecture:** Extract **`run_multi_device_adb(...)`** into `core/multi_device_runner.py` with a **`log(line: str)`** callback and optional **`threading.Event`** for cooperative cancel. Move **config file load/save** into `core/config_io.py`. **`gui/`** holds a tkinter main window, a worker thread that calls the runner, and a queue for log lines. **`main.py`** keeps CLI behavior by loading config then calling the runner.

**Tech Stack:** Python 3.12, tkinter (stdlib), `threading`, `queue`, PyInstaller (dev/build), existing `flows` / `core` stack.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `core/multi_device_runner.py` | Create | `_run_for_device`, `run_multi_device_adb`, shared action handler map |
| `core/config_io.py` | Create | `load_device_config(path)`, `dump_device_config(path, data)` — JSON always; YAML load if path ends with `.yaml`/`.yml` and PyYAML installed |
| `main.py` | Modify | Import runner + config_io; `_run_multi_device` becomes thin wrapper; remove duplicated `_run_for_device` body |
| `tests/test_multi_device_runner.py` | Create | Runner exit codes, cancel between loop iterations, empty devices |
| `tests/test_config_io.py` | Create | Round-trip JSON dict schema; invalid file errors |
| `gui/__init__.py` | Create | Package marker |
| `gui/__main__.py` | Create | `python -m gui` entry: `gui.mainwindow.main()` |
| `gui/mainwindow.py` | Create | Window layout, device list, worker hookup, import/export |
| `gui/adb_check.py` | Create | `adb_available() -> tuple[bool, str]` using `subprocess` + `adb version` |
| `yulang_gui.spec` | Create | PyInstaller spec: `datas=[('templates/adb', 'templates/adb')]` (adjust tree name to match `set_template_subdir("adb")` resolution) |
| `README.md` or `docs/BUILD_GUI.md` | Modify or Create | How to run `python -m gui`, how to `pyinstaller yulang_gui.spec`, BYO adb, Gatekeeper note |

**Implementation order:** Task **1** (runner) → Task **3** (`config_io`) → Task **2** (`main.py` delegate) so imports exist before wiring CLI.

**Frozen templates:** `core/screen.py` uses `_get_project_root()` → `Path(__file__).parent.parent`. When frozen, extend it to prefer `Path(sys._MEIPASS)` so bundled `templates/adb` resolves (Task 8).

**Spec alignment:** UI-first devices + options (spec §Goals, §UI responsibilities), structured runner input (§Worker), import/export same schema (§Configuration precedence), BYO adb check (§Error handling), bundled templates (§Bundled assets).

---

### Task 1: `core/multi_device_runner.py` with `run_multi_device_adb`

**Files:**
- Create: `core/multi_device_runner.py`
- Create: `tests/test_multi_device_runner.py`

**Behavior:** Same semantics as current `main.py` `_run_multi_device` + `_run_for_device`: `adb start-server`, `ThreadPoolExecutor`, per-device `ADBBackend` + `set_template_subdir("adb")`, loop with `time.sleep(loop_interval)`, warn when `loop` and action not in `("quick_sell", "do_quest", "run_chuyen_doi_program")`. Replace every `print(x)` with `log(x)` (always add newline in log callback if needed — pass full lines). If `cancel_event` is set before the next loop iteration starts, exit loop and return `0` (same as KeyboardInterrupt path). Between `time.sleep` chunks for long sleep, poll `cancel_event` every **0.5s** so Stop is responsive.

- [ ] **Step 1: Write failing tests**

Create `tests/test_multi_device_runner.py`:

```python
"""Tests for core.multi_device_runner.run_multi_device_adb."""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from core.multi_device_runner import run_multi_device_adb


def test_empty_devices_returns_1():
    logs: list[str] = []

    def log(line: str) -> None:
        logs.append(line)

    rc = run_multi_device_adb(
        devices=[],
        action="quick_sell",
        threshold=0.75,
        stone_tags=None,
        loop=False,
        loop_interval=1.0,
        log=log,
        cancel_event=None,
    )
    assert rc == 1
    assert any("No devices" in x or "no devices" in x.lower() for x in logs)


def test_cancel_event_stops_loop():
    logs: list[str] = []
    cancel = threading.Event()
    call_count = {"n": 0}

    def fake_run_for_device(device_config, action, threshold, stone_tags):
        call_count["n"] += 1
        return (device_config.get("serial", "?"), True, "")

    with patch("core.multi_device_runner._run_for_device", side_effect=fake_run_for_device):
        def run_in_thread():
            return run_multi_device_adb(
                devices=[{"serial": "emulator-5554"}],
                action="quick_sell",
                threshold=0.75,
                stone_tags=None,
                loop=True,
                loop_interval=10.0,
                log=lambda s: logs.append(s),
                cancel_event=cancel,
            )

        t = threading.Thread(target=run_in_thread)
        t.start()
        time.sleep(0.3)
        cancel.set()
        t.join(timeout=5.0)
        assert not t.is_alive(), "worker should exit after cancel"
```

Adjust import path if you name the internal helper differently; the test patches `_run_for_device` on `core.multi_device_runner`.

- [ ] **Step 2: Run tests (expect failure)**

```bash
cd /Users/lap16932/personal/yulangv2 && source venv/bin/activate && pytest tests/test_multi_device_runner.py -v
```

Expected: **ImportError** or **AttributeError** until implementation exists.

- [ ] **Step 3: Implement `core/multi_device_runner.py`**

Move the body of `_run_for_device` from `main.py` into this module as `_run_for_device(...) -> tuple[str, bool, str]`. Implement:

```python
from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

LogFn = Callable[[str], None]


def _run_for_device(
    device_config: dict,
    action: str,
    threshold: float,
    stone_tags: list[str] | None,
) -> tuple[str, bool, str]:
    # (copy from main.py: ADBBackend, set_backend, set_template_subdir, handlers dict)
    ...


def run_multi_device_adb(
    devices: list[dict],
    action: str,
    threshold: float,
    stone_tags: list[str] | None,
    loop: bool,
    loop_interval: float,
    log: LogFn,
    cancel_event: threading.Event | None = None,
) -> int:
    if not devices:
        log("[ERROR] No devices in config")
        return 1

    subprocess.run(["adb", "start-server"], capture_output=True, timeout=10)

    def run_once() -> int:
        log(f"[MULTI] Running '{action}' on {len(devices)} devices...")
        results: list[tuple[str, bool, str]] = []
        with ThreadPoolExecutor(max_workers=len(devices)) as executor:
            futures = {
                executor.submit(_run_for_device, d, action, threshold, stone_tags): d
                for d in devices
            }
            for future in as_completed(futures):
                device_id, success, error = future.result()
                results.append((device_id, success, error))
                status = "OK" if success else "FAIL"
                msg = f"  [{status}] {device_id}"
                if error:
                    msg += f" - {error}"
                log(msg)

        failed = [d for d, s, _e in results if not s]
        if failed:
            log(f"[MULTI] {len(failed)}/{len(devices)} device(s) failed")
            return 1
        log(f"[MULTI] All {len(devices)} device(s) succeeded")
        return 0

    if not loop:
        return run_once()

    if action not in ("quick_sell", "do_quest", "run_chuyen_doi_program"):
        log("[WARN] --loop works best with quick_sell, do_quest, or run_chuyen_doi_program")

    iteration = 0
    while True:
        if cancel_event is not None and cancel_event.is_set():
            log(f"\n[LOOP] Stopped after {iteration} iteration(s).")
            return 0
        iteration += 1
        log(f"[LOOP #{iteration}]")
        rc = run_once()
        if rc != 0:
            return rc
        log(f"[LOOP] Next run in {loop_interval}s")
        end = time.monotonic() + loop_interval
        while time.monotonic() < end:
            if cancel_event is not None and cancel_event.is_set():
                log(f"\n[LOOP] Stopped after {iteration} iteration(s).")
                return 0
            time.sleep(min(0.5, end - time.monotonic()))
```

CLI passes `cancel_event=None` → loop runs forever until process kill (same as today). GUI passes a real `Event` so **Stop** exits between iterations during the sleep polling.

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_multi_device_runner.py -v
```

Expected: **PASS**

- [ ] **Step 5: Commit**

```bash
git add core/multi_device_runner.py tests/test_multi_device_runner.py
git commit -m "feat: extract ADB multi-device runner with log callback and cancel"
```

---

### Task 2: Wire `main.py` to use `run_multi_device_adb`

**Files:**
- Modify: `main.py` (remove in-file `_run_for_device`; change `_run_multi_device`)

- [ ] **Step 1: Refactor `_run_multi_device`**

- Import `run_multi_device_adb` from `core.multi_device_runner` and keep `_load_config` in `main.py` **or** move load to Task 3 first — order: complete Task 3 `config_io` and then replace `_load_config` with `load_device_config` import.

**Recommended order:** Implement Task 3 next, then in one commit refactor `main.py` to:

```python
from core.config_io import load_device_config
from core.multi_device_runner import run_multi_device_adb

def _run_multi_device(args: argparse.Namespace) -> int:
    try:
        devices, config_options = load_device_config(args.config)
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}")
        return 1

    stone_tags = _parse_stone_tags(args.stones)
    if stone_tags is None and isinstance(config_options.get("stones"), str):
        stone_tags = _parse_stone_tags(config_options["stones"])

    loop = args.loop or bool(config_options.get("loop", False))
    loop_interval = float(config_options["loop_interval"]) if "loop_interval" in config_options else args.loop_interval
    threshold = float(config_options["threshold"]) if "threshold" in config_options else args.threshold

    return run_multi_device_adb(
        devices=devices,
        action=args.action,
        threshold=threshold,
        stone_tags=stone_tags,
        loop=loop,
        loop_interval=loop_interval,
        log=print,
        cancel_event=None,
    )
```

Delete the old `_run_for_device` function from `main.py`.

- [ ] **Step 2: Regression test existing CLI**

```bash
pytest tests/ -v
python main.py --action list_devices --mode adb
```

(Requires adb; skip if no devices — at least no traceback on import.)

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "refactor: delegate multi-device CLI to run_multi_device_adb"
```

---

### Task 3: `core/config_io.py` load + dump

**Files:**
- Create: `core/config_io.py`
- Create: `tests/test_config_io.py`
- Modify: `main.py` to use `load_device_config` instead of inline `_load_config`

- [ ] **Step 1: Write tests**

`tests/test_config_io.py`:

```python
import json
import tempfile
from pathlib import Path

from core.config_io import dump_device_config, load_device_config


def test_load_dump_roundtrip_dict_with_devices():
    data = {
        "threshold": 0.8,
        "loop": True,
        "loop_interval": 5,
        "devices": [{"serial": "emulator-5554"}, {"serial": "emulator-5564"}],
    }
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "cfg.json"
        dump_device_config(str(p), data)
        devices, options = load_device_config(str(p))
        assert len(devices) == 2
        assert devices[0]["serial"] == "emulator-5554"
        assert options.get("threshold") == 0.8
        assert options.get("loop") is True


def test_load_top_level_list():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "list.json"
        p.write_text(json.dumps([{"serial": "a"}], indent=2))
        devices, options = load_device_config(str(p))
        assert devices == [{"serial": "a"}]
        assert options == {}
```

- [ ] **Step 2: Implement `core/config_io.py`**

Move JSON/YAML branching from `main.py` `_load_config` into `load_device_config(path: str) -> tuple[list[dict], dict]`. Implement `dump_device_config(path: str, data: dict) -> None` writing **pretty JSON** (indent=2). For `.yaml`/`.yml` dump, use `yaml.safe_dump` if PyYAML is installed; else write JSON only or raise clear error.

- [ ] **Step 3: Run tests**

```bash
pytest tests/test_config_io.py -v
```

- [ ] **Step 4: Commit**

```bash
git add core/config_io.py tests/test_config_io.py main.py
git commit -m "feat: add config_io for device JSON/YAML load and dump"
```

---

### Task 4: `gui/adb_check.py`

**Files:**
- Create: `gui/adb_check.py`
- Create: `tests/test_adb_check.py` (optional: mock subprocess)

```python
# gui/adb_check.py
from __future__ import annotations

import subprocess


def adb_available(timeout: float = 5.0) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["adb", "version"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if r.returncode == 0:
            return True, ""
        return False, r.stderr or r.stdout or "adb returned non-zero"
    except FileNotFoundError:
        return False, "adb not found on PATH. Install Android Platform Tools."
    except subprocess.TimeoutExpired:
        return False, "adb version timed out."
    except OSError as e:
        return False, str(e)
```

- [ ] **Step 1:** Add file, run `python -c "from gui.adb_check import adb_available; print(adb_available())"`

- [ ] **Step 2: Commit** — `feat: add gui adb availability check`

---

### Task 5: `gui/mainwindow.py` skeleton + worker thread

**Files:**
- Create: `gui/__init__.py` (empty)
- Create: `gui/__main__.py`
- Create: `gui/mainwindow.py`

**`gui/__main__.py`:**

```python
from gui.mainwindow import main

if __name__ == "__main__":
    main()
```

**`gui/mainwindow.py` outline:**

- `tkinter` + `ttk` + `scrolledtext` for log.
- `queue.Queue` for log lines; `after(100, drain_queue)` to append to `ScrolledText`.
- Fields: `threshold` (`DoubleVar` default 0.75), `stones` (`StringVar`), `loop` (`BooleanVar`), `loop_interval` (`DoubleVar` default 10.0), `action` (`StringVar` or `Combobox` values = action list from spec excluding `list_devices` as primary run action — use **Refresh** for devices instead).
- **Run** button: validate at least one device row checked with non-empty serial; call `_start_worker`.
- **Stop** sets `cancel_event`.
- Worker thread:

```python
import threading
import queue

def worker():
    try:
        rc = run_multi_device_adb(
            devices=selected_devices,
            action=action,
            threshold=...,
            stone_tags=parse_stones(stones_str) or None,
            loop=...,
            loop_interval=...,
            log=lambda line: log_queue.put(line),
            cancel_event=cancel_event,
        )
        log_queue.put(f"\n[EXIT] code {rc}\n")
    finally:
        log_queue.put(None)  # sentinel to re-enable Run
```

- [ ] **Step 1:** Implement minimal window (no device table yet — single hardcoded device list) to prove thread + log works.

- [ ] **Step 2:** `python -m gui` from repo root with `PYTHONPATH=.` or install editable — document `python -m gui` requires running from project root:

```bash
cd /Users/lap16932/personal/yulangv2 && source venv/bin/activate && python -m gui
```

- [ ] **Step 3: Commit** — `feat: add gui skeleton with worker and log`

---

### Task 6: Device table — refresh, checkboxes, add/remove rows

**Files:**
- Modify: `gui/mainwindow.py`

- Use `ttk.Treeview` with columns `(selected, serial, status)` where `selected` is checkbox via separate controls or use a `Frame` of rows (`Checkbutton` + `Label` + `Entry` for serial). Simpler: **list of frames**, each row: `Checkbutton`, `Entry` (serial), `Label` (status from refresh).
- **Refresh** calls `get_adb_devices()` from `core.backend` (same as CLI list_devices). For each connected serial, merge into rows: if serial exists, update status; if new, append row (checked by default). Manual rows keep user text until refresh conflicts (document: refresh adds/updates known devices only).
- **Add row** appends empty unchecked row.
- **Remove row** deletes selected row widget.

- [ ] **Step 1:** Implement refresh + selection gathering for `Run`.

- [ ] **Step 2: Commit** — `feat: gui device list with refresh and selection`

---

### Task 7: Import / Export config

**Files:**
- Modify: `gui/mainwindow.py`

- **Import:** `filedialog.askopenfilename` → `load_device_config` → populate threshold/loop/stones/devices table (all devices from file shown; default checked all).
- **Export:** Build `dict` with `devices=[{"serial": s} for s in ... all rows or only checked — spec says export **current on-screen state**; include **all rows** in `devices` list, and optionally persist **checked** state with a key like `"selected_serials": [...]` **not** read by current CLI — **YAGNI:** export only **`devices` as list of `{serial}` for every row with non-empty serial** so CLI `main.py --config` works; user re-selects checkboxes after import from file. Alternatively export only checked serials as `devices` so file matches next CLI run exactly — **spec:** "Export writes the current on-screen state" — use **checked rows only** in `devices` array for CLI parity with what Run would use.

- [ ] **Step 1:** Implement Export JSON; YAML export optional (`.yaml` extension uses PyYAML if installed).

- [ ] **Step 2: Commit** — `feat: gui import export device config`

---

### Task 8: PyInstaller spec + build doc

**Files:**
- Create: `yulang_gui.spec`
- Create or modify: `docs/BUILD_GUI.md`

**Datas:** Include entire `templates/adb` directory. PyInstaller one-folder or one-file — **one-folder** (`COLLECT`) is easier for large cv2.

**Hidden imports:** Often need `cv2`, `PIL`, `pyobjc` frameworks — follow PyInstaller warnings from a trial build.

Example spec fragment:

```python
# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs

block_cipher = None
datas = [("templates/adb", "templates/adb")]
# datas += collect_data_files("cv2")  # if hook misses

a = Analysis(
    ["gui/__main__.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=["cv2", "PIL._tkinter_finder"],
    ...
)
```

**Entry:** Use a small `gui_launcher.py` at repo root that sets resource path if needed, or configure `core/screen.py` template base path to use `sys._MEIPASS` when frozen (add task if templates not found — **detect** `getattr(sys, "frozen", False)` and prepend `sys._MEIPASS` to template root).

- [ ] **Step 1:** Add `sys._MEIPASS` handling in `core/screen.py` (or wherever template root is resolved) so frozen app finds bundled `templates/adb`.

- [ ] **Step 2:** Document:

```bash
pip install pyinstaller
pyinstaller yulang_gui.spec
open dist/YulangGUI/YulangGUI.app   # name per spec
```

- [ ] **Step 3: Commit** — `docs: PyInstaller spec and frozen template path`

---

## Spec coverage (self-review)

| Spec requirement | Task(s) |
|------------------|---------|
| ADB-only GUI | Task 5–7 (no Mac mode in UI) |
| All ADB actions + refresh | Task 5–6 (action combobox); refresh uses `get_adb_devices` |
| Devices/on-screen edit | Task 6 |
| Import/export schema | Task 3, 7 |
| BYO adb + clear errors | Task 4 + banner in Task 5 window on startup |
| Bundled templates | Task 8 + template root fix |
| Log + Stop (cooperative) | Task 1 cancel + Task 5 worker |
| CLI parity | Task 2, 7 export = checked devices |

**Placeholder scan:** None intentional; adjust PyInstaller `hiddenimports` against real trial build output.

**Type consistency:** `run_multi_device_adb` signature matches GUI worker call in Task 5; `load_device_config` return shape matches `main.py` and GUI import.

---

**Plan complete and saved to `docs/superpowers/plans/2026-03-28-macos-adb-gui-app-plan.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach do you want?**
