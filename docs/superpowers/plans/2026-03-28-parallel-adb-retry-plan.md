# Parallel ADB Execution Fix + Command-Level Retry — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two bugs that break multi-device parallel execution: a global backend race condition and silent transient ADB command failures.

**Architecture:** Replace module-level globals in `core/screen.py` with `threading.local()` so each thread owns its own backend. Add retry loops with a `_ping_device()` nudge inside `ADBBackend._capture_exec_out()` and `ADBBackend.click()` in `core/backend.py`.

**Tech Stack:** Python 3.12, `threading.local`, `subprocess`, `unittest.mock`, `pytest`

---

## File Map

| File | Action | What changes |
|------|--------|--------------|
| `core/screen.py` | Modify | Replace `_backend`/`_template_subdir` globals with `_thread_local = threading.local()` |
| `core/backend.py` | Modify | Add `_ADB_CMD_RETRIES`, `_ADB_RETRY_DELAY`, `_ping_device()`, retry loops in `_capture_exec_out()` and `click()` |
| `tests/test_screen_threading.py` | Create | Thread-isolation test for `set_backend` / `_get_backend` |
| `tests/test_adb_retry.py` | Create | Retry tests for `_capture_exec_out` and `click` |

---

### Task 1: Thread-safe backend in `core/screen.py`

**Files:**
- Modify: `core/screen.py:20-51`
- Create: `tests/test_screen_threading.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_screen_threading.py`:

```python
"""Test that set_backend / _get_backend are thread-isolated."""
import threading
from unittest.mock import MagicMock

import pytest


def test_backends_are_thread_isolated():
    """Two threads must not share backends set via set_backend()."""
    # Import fresh to get current state
    import core.screen as screen

    results = {}

    backend_a = MagicMock(name="BackendA")
    backend_b = MagicMock(name="BackendB")

    barrier = threading.Barrier(2)

    def run_thread(name, backend, other_backend):
        screen.set_backend(backend)
        barrier.wait()  # Both threads set their backend before either reads
        got = screen._get_backend()
        results[name] = got

    t1 = threading.Thread(target=run_thread, args=("a", backend_a, backend_b))
    t2 = threading.Thread(target=run_thread, args=("b", backend_b, backend_a))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results["a"] is backend_a, "Thread A must see its own backend"
    assert results["b"] is backend_b, "Thread B must see its own backend"


def test_template_subdir_is_thread_isolated():
    """set_template_subdir must not bleed across threads."""
    import core.screen as screen

    results = {}
    barrier = threading.Barrier(2)

    def run_thread(name, subdir):
        screen.set_template_subdir(subdir)
        barrier.wait()
        got = getattr(screen._thread_local, "template_subdir", None)
        results[name] = got

    t1 = threading.Thread(target=run_thread, args=("a", "adb"))
    t2 = threading.Thread(target=run_thread, args=("b", None))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results["a"] == "adb"
    assert results["b"] is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/lap16932/personal/yulangv2 && source venv/bin/activate && pytest tests/test_screen_threading.py -v
```

Expected: `AttributeError: module 'core.screen' has no attribute '_thread_local'` or tests FAIL because globals bleed across threads.

- [ ] **Step 3: Replace globals with `threading.local` in `core/screen.py`**

Replace lines 8–51 of `core/screen.py` with:

```python
from __future__ import annotations

import random
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from core.backend import Backend

# Per-thread backend and template subdir — set by main.py based on --mode.
# threading.local() ensures each worker thread in multi-device execution
# has its own isolated backend; no cross-thread contamination.
_thread_local = threading.local()


def set_backend(backend: Backend) -> None:
    """Set the active capture/click backend (Mac or ADB) for this thread."""
    _thread_local.backend = backend


def set_template_subdir(subdir: str | None) -> None:
    """Set template subdir (e.g. 'adb') for mode-specific templates. None = default."""
    _thread_local.template_subdir = subdir


def set_capture_context(window_id: int | None, game_app: str | None) -> None:
    """Set context for background capture mode (creates MacBackend)."""
    from core.backend import MacBackend

    set_backend(MacBackend(window_id=window_id, game_app=game_app))


def _get_backend() -> Backend:
    """Return active backend for this thread; create default MacBackend if none set."""
    backend = getattr(_thread_local, "backend", None)
    if backend is None:
        from core.backend import MacBackend

        backend = MacBackend(window_id=None, game_app=None)
        _thread_local.backend = backend
    return backend
```

The rest of `core/screen.py` (from line 54 onward) is unchanged. The only other reference to `_template_subdir` is in `set_template_subdir`, `resolve_template_path`, and `get_stone_template_names`. Update those two functions to read from `_thread_local`:

In `resolve_template_path` (around line 135), replace:
```python
    if _template_subdir:
        subdir_path = base / _template_subdir / template_name
```
with:
```python
    _template_subdir = getattr(_thread_local, "template_subdir", None)
    if _template_subdir:
        subdir_path = base / _template_subdir / template_name
```

In `get_stone_template_names` (around line 118), replace:
```python
    if _template_subdir:
        stones_dir = base / _template_subdir / "stones"
    else:
        stones_dir = base / "stones"
    if not stones_dir.is_dir():
        return []
    names = []
    for p in sorted(stones_dir.glob("*.png")):
        rel = p.relative_to(base / _template_subdir if _template_subdir else base)
```
with:
```python
    _template_subdir = getattr(_thread_local, "template_subdir", None)
    if _template_subdir:
        stones_dir = base / _template_subdir / "stones"
    else:
        stones_dir = base / "stones"
    if not stones_dir.is_dir():
        return []
    names = []
    for p in sorted(stones_dir.glob("*.png")):
        rel = p.relative_to(base / _template_subdir if _template_subdir else base)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/lap16932/personal/yulangv2 && source venv/bin/activate && pytest tests/test_screen_threading.py -v
```

Expected output:
```
PASSED tests/test_screen_threading.py::test_backends_are_thread_isolated
PASSED tests/test_screen_threading.py::test_template_subdir_is_thread_isolated
2 passed
```

- [ ] **Step 5: Commit**

```bash
cd /Users/lap16932/personal/yulangv2 && git add core/screen.py tests/test_screen_threading.py && git commit -m "fix: thread-isolate backend globals using threading.local"
```

---

### Task 2: ADB command-level retry in `core/backend.py`

**Files:**
- Modify: `core/backend.py:105-192`
- Create: `tests/test_adb_retry.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_adb_retry.py`:

```python
"""Test ADB command retry logic in ADBBackend."""
import subprocess
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from core.backend import ADBBackend, _ADB_CMD_RETRIES, _ADB_RETRY_DELAY, _ping_device


class TestPingDevice:
    def test_runs_get_state(self):
        """_ping_device runs 'adb -s <device> get-state'."""
        with patch("core.backend.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _ping_device("emulator-5554")
            mock_run.assert_called_once_with(
                ["adb", "-s", "emulator-5554", "get-state"],
                capture_output=True,
                timeout=3,
            )

    def test_ignores_failure(self):
        """_ping_device does not raise even if adb fails."""
        with patch("core.backend.subprocess.run", side_effect=subprocess.TimeoutExpired("adb", 3)):
            _ping_device("emulator-5554")  # must not raise


class TestCaptureExecOutRetry:
    def _make_valid_png(self) -> bytes:
        """Return a minimal valid PNG bytes that OpenCV can decode."""
        import cv2, numpy as np
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        ok, buf = cv2.imencode(".png", img)
        assert ok
        return buf.tobytes()

    def test_succeeds_on_first_try(self):
        """Returns image immediately if first exec-out succeeds."""
        backend = ADBBackend("emulator-5554")
        valid_png = self._make_valid_png()

        with patch("core.backend.subprocess.run") as mock_run, \
             patch("core.backend._ping_device") as mock_ping:
            mock_run.return_value = MagicMock(returncode=0, stdout=valid_png)
            result = backend._capture_exec_out()

        assert result is not None
        mock_ping.assert_not_called()

    def test_retries_on_empty_output(self):
        """Retries when exec-out returns too-short output, eventually succeeds."""
        backend = ADBBackend("emulator-5554")
        valid_png = self._make_valid_png()

        fail = MagicMock(returncode=0, stdout=b"short")
        success = MagicMock(returncode=0, stdout=valid_png)

        with patch("core.backend.subprocess.run") as mock_run, \
             patch("core.backend._ping_device") as mock_ping, \
             patch("core.backend.time.sleep"):
            mock_run.side_effect = [fail, fail, success]
            result = backend._capture_exec_out()

        assert result is not None
        assert mock_ping.call_count == 2  # pinged before each retry

    def test_returns_none_after_all_retries_exhausted(self):
        """Returns None when all retries fail."""
        backend = ADBBackend("emulator-5554")

        fail = MagicMock(returncode=1, stdout=b"")

        with patch("core.backend.subprocess.run") as mock_run, \
             patch("core.backend._ping_device"), \
             patch("core.backend.time.sleep"):
            mock_run.return_value = fail
            result = backend._capture_exec_out()

        assert result is None
        assert mock_run.call_count == _ADB_CMD_RETRIES


class TestClickRetry:
    def test_succeeds_on_first_try(self):
        """Returns True immediately if first tap succeeds."""
        backend = ADBBackend("emulator-5554")

        with patch("core.backend.subprocess.run") as mock_run, \
             patch("core.backend._ping_device") as mock_ping, \
             patch("core.backend.time.sleep"):
            mock_run.return_value = MagicMock(returncode=0)
            result = backend.click(100, 200)

        assert result is True
        mock_ping.assert_not_called()

    def test_retries_on_nonzero_exit(self):
        """Retries when tap returns non-zero exit, eventually succeeds."""
        backend = ADBBackend("emulator-5554")

        fail = MagicMock(returncode=1)
        success = MagicMock(returncode=0)

        with patch("core.backend.subprocess.run") as mock_run, \
             patch("core.backend._ping_device") as mock_ping, \
             patch("core.backend.time.sleep"):
            mock_run.side_effect = [fail, success]
            result = backend.click(100, 200)

        assert result is True
        assert mock_ping.call_count == 1

    def test_returns_false_after_all_retries_exhausted(self):
        """Returns False when all tap retries fail."""
        backend = ADBBackend("emulator-5554")

        fail = MagicMock(returncode=1)

        with patch("core.backend.subprocess.run") as mock_run, \
             patch("core.backend._ping_device"), \
             patch("core.backend.time.sleep"):
            mock_run.return_value = fail
            result = backend.click(100, 200)

        assert result is False
        assert mock_run.call_count == _ADB_CMD_RETRIES
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/lap16932/personal/yulangv2 && source venv/bin/activate && pytest tests/test_adb_retry.py -v
```

Expected: `ImportError: cannot import name '_ADB_CMD_RETRIES'` — the constants and `_ping_device` don't exist yet.

- [ ] **Step 3: Add constants, `_ping_device`, and retry loops to `core/backend.py`**

After the existing imports and before the `pyautogui.PAUSE` line (around line 19), add:

```python
# ADB command retry configuration
_ADB_CMD_RETRIES = 3
_ADB_RETRY_DELAY = 0.5  # seconds between retries


def _ping_device(device: str) -> None:
    """Run adb get-state to nudge a stalled connection. Result is ignored."""
    try:
        subprocess.run(
            ["adb", "-s", device, "get-state"],
            capture_output=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
```

Replace `_capture_exec_out` (lines 132–148) with:

```python
    def _capture_exec_out(self) -> np.ndarray | None:
        """Capture via adb exec-out (fast). Retries on transient failures."""
        for attempt in range(_ADB_CMD_RETRIES):
            try:
                result = subprocess.run(
                    ["adb", "-s", self._device, "exec-out", "screencap", "-p"],
                    capture_output=True,
                    timeout=15,
                )
                if result.returncode == 0:
                    raw = result.stdout.replace(b"\r\n", b"\n").replace(b"\r", b"")
                    if len(raw) >= 100:
                        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                        if img is not None:
                            return img
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            if attempt < _ADB_CMD_RETRIES - 1:
                _ping_device(self._device)
                time.sleep(_ADB_RETRY_DELAY)
        return None
```

Replace `click` (lines 181–192) with:

```python
    def click(self, x: int, y: int, click_delay: float = 0.05) -> bool:
        """Tap at (x, y) via adb. Retries on transient failures."""
        for attempt in range(_ADB_CMD_RETRIES):
            try:
                result = subprocess.run(
                    ["adb", "-s", self._device, "shell", "input", "tap", str(x), str(y)],
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    if click_delay > 0:
                        time.sleep(click_delay)
                    return True
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            if attempt < _ADB_CMD_RETRIES - 1:
                _ping_device(self._device)
                time.sleep(_ADB_RETRY_DELAY)
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/lap16932/personal/yulangv2 && source venv/bin/activate && pytest tests/test_adb_retry.py -v
```

Expected output:
```
PASSED tests/test_adb_retry.py::TestPingDevice::test_runs_get_state
PASSED tests/test_adb_retry.py::TestPingDevice::test_ignores_failure
PASSED tests/test_adb_retry.py::TestCaptureExecOutRetry::test_succeeds_on_first_try
PASSED tests/test_adb_retry.py::TestCaptureExecOutRetry::test_retries_on_empty_output
PASSED tests/test_adb_retry.py::TestCaptureExecOutRetry::test_returns_none_after_all_retries_exhausted
PASSED tests/test_adb_retry.py::TestClickRetry::test_succeeds_on_first_try
PASSED tests/test_adb_retry.py::TestClickRetry::test_retries_on_nonzero_exit
PASSED tests/test_adb_retry.py::TestClickRetry::test_returns_false_after_all_retries_exhausted
8 passed
```

- [ ] **Step 5: Run the full test suite to confirm no regressions**

```bash
cd /Users/lap16932/personal/yulangv2 && source venv/bin/activate && pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
cd /Users/lap16932/personal/yulangv2 && git add core/backend.py tests/test_adb_retry.py && git commit -m "feat: add ADB command-level retry with device ping on transient failures"
```
