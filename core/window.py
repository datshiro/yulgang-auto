"""
macOS window/focus management.

Brings the game to front for automation, then restores the previous app.
macOS does not support sending clicks to background windows—the target must be in front.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from typing import Any

try:
    from AppKit import NSApplicationActivateIgnoringOtherApps, NSWorkspace
    HAS_PYOBJC = True
except ImportError:
    HAS_PYOBJC = False


# Default app bundle ID; user can override via --game-app
DEFAULT_GAME_APP = "com.rxjhvn.iOS"


def _get_frontmost_app() -> Any | None:
    """Return the currently frontmost application, or None if pyobjc unavailable."""
    if not HAS_PYOBJC:
        return None
    return NSWorkspace.sharedWorkspace().frontmostApplication()


def _activate_via_open(bundle_id: str) -> bool:
    """Fallback: use 'open -b' to activate app by bundle ID (no pyobjc needed)."""
    try:
        subprocess.run(
            ["open", "-b", bundle_id],
            check=True,
            capture_output=True,
            timeout=5,
        )
        time.sleep(0.5)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return False


def activate_app(bundle_id_or_name: str) -> bool:
    """
    Activate (bring to front) an app by bundle ID or display name.

    Args:
        bundle_id_or_name: e.g. "com.rxjhvn.iOS" or "Yulgang"

    Returns:
        True if activated, False otherwise.
    """
    if HAS_PYOBJC:
        workspace = NSWorkspace.sharedWorkspace()
        apps = workspace.runningApplications()
        for app in apps:
            name = app.localizedName() or ""
            bid = app.bundleIdentifier() or ""
            if (
                bundle_id_or_name == name
                or bundle_id_or_name == bid
                or bundle_id_or_name in name
                or bundle_id_or_name in bid
            ):
                if app.isActive():
                    return True
                ok = app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                if ok:
                    time.sleep(0.3)
                return ok

    # Fallback: 'open -b' works without pyobjc (bundle ID only)
    if bundle_id_or_name.startswith("com.") or "." in bundle_id_or_name:
        if _activate_via_open(bundle_id_or_name):
            return True

    if not HAS_PYOBJC:
        print("[WARN] pyobjc not available; install: pip install pyobjc-framework-Cocoa")
        print("[WARN] Or run with venv: source venv/bin/activate && python main.py ...")
    return False


def run_with_game_focus(
    game_app: str,
    action_fn: Callable[..., Any],
    *args: Any,
    restore: bool = True,
    **kwargs: Any,
) -> Any:
    """
    Run an action with the game in front, then restore the previous app.

    macOS requires the target window to be in front to receive clicks.
    This minimizes disruption by restoring your previous app when done.

    Args:
        game_app: App name or bundle ID (e.g. "Yulang").
        action_fn: Callable to run (e.g. run_quick_sell).
        *args, **kwargs: Passed to action_fn.
        restore: If True, restore the previous app when done.

    Returns:
        Whatever action_fn returns.
    """
    previous = _get_frontmost_app()
    previous_pid = previous.processIdentifier() if previous else None

    if not activate_app(game_app):
        print(f"[WARN] Could not activate '{game_app}'; is the game running?")
        print("[WARN] Proceeding anyway—clicks may hit the wrong window")

    try:
        return action_fn(*args, **kwargs)
    finally:
        if restore and previous_pid and HAS_PYOBJC:
            workspace = NSWorkspace.sharedWorkspace()
            for app in workspace.runningApplications():
                if app.processIdentifier() == previous_pid:
                    app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                    break


def run_transient_focus(
    game_app: str,
    fn: Callable[[], Any],
) -> Any:
    """
    Activate game, run fn, restore previous app. For use when we only need
    focus for a single action (e.g. click).
    """
    previous = _get_frontmost_app()
    previous_pid = previous.processIdentifier() if previous else None
    activate_app(game_app)
    try:
        return fn()
    finally:
        if previous_pid and HAS_PYOBJC:
            workspace = NSWorkspace.sharedWorkspace()
            for app in workspace.runningApplications():
                if app.processIdentifier() == previous_pid:
                    app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                    break
