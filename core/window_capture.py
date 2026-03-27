"""
Background window capture using macOS Quartz APIs.

Captures a specific application window without bringing it to the foreground.
Uses screencapture -l for reliable capture; Quartz for window ID lookup.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import cv2
import numpy as np

try:
    from AppKit import NSWorkspace
    from Quartz import CoreGraphics as CG

    HAS_QUARTZ = True
except ImportError:
    HAS_QUARTZ = False


def get_game_window_id(bundle_id_or_name: str) -> int | None:
    """
    Find the main window ID of an app by bundle ID or display name.

    Args:
        bundle_id_or_name: e.g. "com.rxjhvn.iOS" or "Yulgang"

    Returns:
        Window ID (kCGWindowNumber) or None if not found.
    """
    if not HAS_QUARTZ:
        return None

    # Get target app's PID
    target_pid = None
    workspace = NSWorkspace.sharedWorkspace()
    for app in workspace.runningApplications():
        name = app.localizedName() or ""
        bid = app.bundleIdentifier() or ""
        if (
            bundle_id_or_name == name
            or bundle_id_or_name == bid
            or bundle_id_or_name in name
            or bundle_id_or_name in bid
        ):
            target_pid = app.processIdentifier()
            break

    if target_pid is None:
        return None

    # Get window list (all on-screen windows)
    window_list = CG.CGWindowListCopyWindowInfo(
        CG.kCGWindowListOptionOnScreenOnly,
        CG.kCGNullWindowID,
    )
    if window_list is None:
        return None

    # Find the app's main window (prefer higher layer = closer to user)
    best_window_id = None
    best_layer = -999999

    for win in window_list:
        owner_pid = win.get(CG.kCGWindowOwnerPID)
        if owner_pid != target_pid:
            continue
        window_id = win.get(CG.kCGWindowNumber)
        layer = win.get(CG.kCGWindowLayer, 0)
        if window_id is not None and layer > best_layer:
            best_window_id = int(window_id)
            best_layer = layer

    return best_window_id


def get_window_bounds(window_id: int) -> tuple[int, int, int, int] | None:
    """
    Get window screen position and size (x, y, width, height).

    Returns top-left origin coords. Uses CGDisplayBounds for consistent
    coordinate system (points) with window bounds.
    """
    if not HAS_QUARTZ:
        return None
    window_list = CG.CGWindowListCopyWindowInfo(
        CG.kCGWindowListOptionOnScreenOnly,
        CG.kCGNullWindowID,
    )
    if not window_list:
        return None
    for win in window_list:
        if win.get(CG.kCGWindowNumber) == window_id:
            bounds = win.get(CG.kCGWindowBounds)
            if bounds:
                # kCGWindowBounds uses top-left origin: X,Y = top-left corner of window
                x = int(bounds.get("X", bounds.get("x", 0)))
                y = int(bounds.get("Y", bounds.get("y", 0)))
                w = int(bounds.get("Width", bounds.get("width", 0)))
                h = int(bounds.get("Height", bounds.get("height", 0)))
                # Y is already top edge (top-left origin); no flip needed
                return (x, y, w, h)
            return None
    return None


def capture_window(window_id: int) -> np.ndarray | None:
    """
    Capture a window by ID without bringing it to the foreground.

    Uses screencapture -l which captures the window in background on macOS.

    Args:
        window_id: From get_game_window_id().

    Returns:
        BGR numpy array (OpenCV format) or None on failure.
    """
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        path = f.name
    try:
        # -x: no sound, -o: no shadow (aligns with window bounds), -l: window by ID
        result = subprocess.run(
            ["screencapture", "-x", "-o", "-l", str(window_id), path],
            capture_output=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        img = cv2.imread(path)
        return img
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    finally:
        Path(path).unlink(missing_ok=True)
