"""Check whether ``adb`` is available on PATH."""

from __future__ import annotations

import subprocess


def adb_available(timeout: float = 5.0) -> tuple[bool, str]:
    """Return (True, \"\") if ``adb version`` succeeds; else (False, error message)."""
    try:
        r = subprocess.run(
            ["adb", "version"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if r.returncode == 0:
            return True, ""
        return False, (r.stderr or r.stdout or "adb returned non-zero").strip()
    except FileNotFoundError:
        return False, "adb not found on PATH. Install Android Platform Tools."
    except subprocess.TimeoutExpired:
        return False, "adb version timed out."
    except OSError as e:
        return False, str(e)
