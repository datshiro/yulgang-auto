# Parallel ADB Execution Fix + Command-Level Retry

**Date:** 2026-03-28
**Status:** Approved

## Problem

Two independent bugs make multi-device parallel execution unreliable:

1. **Thread-safety bug** — `_backend` and `_template_subdir` in `core/screen.py` are module-level globals. When `ThreadPoolExecutor` runs `_run_for_device` in parallel, threads overwrite each other's backend, causing device A to accidentally use device B's ADB connection.

2. **Transient ADB command failures** — While a device remains visible in `adb devices`, individual `screencap` and `input tap` commands can fail silently (empty output, non-zero exit). The current code has no retry at the command level, so one transient glitch fails the entire action.

## Design

### 1. Thread-local backend (`core/screen.py`)

Replace:
```python
_backend: Backend | None = None
_template_subdir: str | None = None
```

With:
```python
import threading
_thread_local = threading.local()
```

Update all accessors:
- `set_backend(backend)` → `_thread_local.backend = backend`
- `set_template_subdir(subdir)` → `_thread_local.template_subdir = subdir`
- `_get_backend()` → reads `getattr(_thread_local, 'backend', None)`, creates default `MacBackend` if unset
- `_get_template_subdir()` (inline where used) → `getattr(_thread_local, 'template_subdir', None)`

Each worker thread in `_run_for_device` calls `set_backend(ADBBackend(device_id))` and `set_template_subdir("adb")` — these writes are now isolated to that thread.

### 2. ADB command retry (`core/backend.py`)

Add module-level constants:
```python
_ADB_CMD_RETRIES = 3
_ADB_RETRY_DELAY = 0.5  # seconds between retries
```

Add a device ping helper:
```python
def _ping_device(device: str) -> None:
    """Run adb get-state to nudge a stalled connection. Result ignored."""
    subprocess.run(
        ["adb", "-s", device, "get-state"],
        capture_output=True, timeout=3,
    )
```

**`_capture_exec_out()`** — wrap existing logic in a retry loop:
- On success (valid image decoded), return immediately
- On failure (returncode != 0, output too short, decode error): call `_ping_device()`, sleep `_ADB_RETRY_DELAY`, retry
- After all retries exhausted, return `None` (falls through to `_capture_pull()` as before)

**`click()`** — wrap existing `subprocess.run` in a retry loop:
- On success (returncode == 0), return `True` as before
- On failure: call `_ping_device()`, sleep `_ADB_RETRY_DELAY`, retry
- After all retries exhausted, return `False`

### 3. No changes to config/parallel logic

`_run_multi_device` and `_run_for_device` in `main.py` are correct. The `ThreadPoolExecutor` parallelism already works — it only fails due to the shared global. No config schema changes.

## Files Changed

| File | Change |
|------|--------|
| `core/screen.py` | Replace globals with `threading.local()` |
| `core/backend.py` | Add `_ping_device()`, retry loops in `_capture_exec_out()` and `click()` |

## Non-Goals

- Action-level retry (reconnect + re-run entire flow)
- Changes to `adb devices` refresh or device discovery
- Mac backend changes
