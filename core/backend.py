"""
Backend abstraction for screen capture and input.

Supports macOS (PyAutoGUI + screencapture) and ADB (BlueStacks/emulator).
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np
import pyautogui

# PyAutoGUI adds 0.1s PAUSE after every action by default. Reduce for faster automation.
pyautogui.PAUSE = 0.02

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


class Backend(Protocol):
    """Protocol for capture and click backends."""

    @property
    def uses_window_capture(self) -> bool:
        """True if capture returns window-space coords (need conversion for click)."""
        ...

    def get_window_id(self) -> int | None:
        """Window ID for coordinate conversion (Mac only). Returns None for ADB."""
        ...

    @property
    def uses_direct_coords(self) -> bool:
        """True if screenshot coords map directly to click coords (ADB)."""
        ...

    def capture(self) -> tuple[np.ndarray | None, bool]:
        """Capture screen as BGR. Returns (image, used_window_capture)."""
        ...

    def click(self, x: int, y: int, click_delay: float = 0.05) -> bool:
        """Perform click/tap at (x, y). Coords are already in target space."""
        ...


class MacBackend:
    """
    macOS backend: PyAutoGUI + screencapture.

    Uses window capture when window_id is set; otherwise full-screen.
    Clicks require game in front for window capture (transient focus).
    """

    def __init__(
        self,
        window_id: int | None = None,
        game_app: str | None = None,
    ) -> None:
        self._window_id = window_id
        self._game_app = game_app

    @property
    def uses_window_capture(self) -> bool:
        return self._window_id is not None

    def get_window_id(self) -> int | None:
        return self._window_id

    @property
    def uses_direct_coords(self) -> bool:
        return False

    def capture(self) -> tuple[np.ndarray | None, bool]:
        if self._window_id is not None:
            from core.window_capture import capture_window

            img = capture_window(self._window_id)
            if img is not None:
                return (img, True)
            # Fallback to full screen if window capture fails
        screenshot = pyautogui.screenshot()
        screen_rgb = np.array(screenshot)
        img = cv2.cvtColor(screen_rgb, cv2.COLOR_RGB2BGR)
        return (img, False)

    def click(self, x: int, y: int, click_delay: float = 0.05) -> bool:
        def _do_click() -> bool:
            time.sleep(0.15)
            pyautogui.moveTo(x, y, duration=click_delay)
            pyautogui.click()
            return True

        if self._game_app:
            from core.window import run_transient_focus

            run_transient_focus(self._game_app, _do_click)
        else:
            pyautogui.moveTo(x, y, duration=click_delay)
            pyautogui.click()
        return True


class ADBBackend:
    """
    ADB backend for BlueStacks/Android emulator.

    Screencap and tap use the same device coordinate system; no conversion needed.
    """

    def __init__(self, device: str) -> None:
        self._device = device

    @property
    def uses_window_capture(self) -> bool:
        return False

    def get_window_id(self) -> int | None:
        return None

    @property
    def uses_direct_coords(self) -> bool:
        return True

    def capture(self) -> tuple[np.ndarray | None, bool]:
        img = self._capture_exec_out()
        if img is None:
            img = self._capture_pull()
        return (img, False)

    def _capture_exec_out(self) -> np.ndarray | None:
        """Capture via adb exec-out (fast). Retries on transient failures."""
        last_reason = "unknown"
        for attempt in range(_ADB_CMD_RETRIES):
            try:
                result = subprocess.run(
                    ["adb", "-s", self._device, "exec-out", "screencap", "-p"],
                    capture_output=True,
                    timeout=15,
                )
                if result.returncode == 0:
                    raw = result.stdout
                    if len(raw) >= 100:
                        img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                        if img is not None:
                            return img
                        last_reason = "imdecode returned None (corrupt PNG?)"
                    else:
                        last_reason = f"output too short ({len(raw)} bytes)"
                else:
                    stderr = result.stderr.decode(errors="replace").strip()
                    last_reason = f"returncode={result.returncode}" + (f" ({stderr})" if stderr else "")
            except FileNotFoundError:
                last_reason = "adb not found on PATH"
            except subprocess.TimeoutExpired:
                last_reason = "adb timed out"
            if attempt < _ADB_CMD_RETRIES - 1:
                _ping_device(self._device)
                time.sleep(_ADB_RETRY_DELAY)
        print(f"[ADB] {self._device}: exec-out failed after {_ADB_CMD_RETRIES} attempts — {last_reason}")
        return None

    def _capture_pull(self) -> np.ndarray | None:
        """Capture via adb shell + pull (fallback for BlueStacks)."""
        import tempfile
        try:
            remote = "/sdcard/screencap_yulang.png"
            r1 = subprocess.run(
                ["adb", "-s", self._device, "shell", "screencap", "-p", remote],
                capture_output=True,
                timeout=15,
            )
            if r1.returncode != 0:
                return None
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                tmp = f.name
            r2 = subprocess.run(
                ["adb", "-s", self._device, "pull", remote, tmp],
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["adb", "-s", self._device, "shell", "rm", "-f", remote],
                capture_output=True,
            )
            if r2.returncode != 0:
                return None
            img = cv2.imread(tmp)
            Path(tmp).unlink(missing_ok=True)
            return img
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None

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


def get_adb_devices() -> list[tuple[str, str]]:
    """
    Return list of (device_id, status) from adb devices.

    Status is typically "device" (ready) or "offline".
    Starts adb server first if needed (fixes empty list on BlueStacks).
    """
    try:
        subprocess.run(
            ["adb", "start-server"],
            capture_output=True,
            timeout=5,
        )
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return []
        devices = []
        for line in result.stdout.strip().splitlines()[1:]:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            if len(parts) >= 2:
                devices.append((parts[0], parts[1]))
        return devices
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def get_first_adb_device() -> str | None:
    """
    Return the first connected ADB device ID, or None if none.

    Parses `adb devices` output. Skips "List of devices" header and "device" lines.
    """
    for device_id, status in get_adb_devices():
        if status == "device":
            return device_id
    return None
