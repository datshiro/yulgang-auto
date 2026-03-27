#!/usr/bin/env python3
"""
Capture raw screenshot from BlueStacks/Android via ADB.

Use this to extract the exact image the automation sees—avoids host scaling
and resolution issues when creating templates.

Usage:
    python scripts/adb_screenshot.py
    python scripts/adb_screenshot.py --output my_screen.png
    python scripts/adb_screenshot.py --device emulator-5554 --output templates/adb/reference.png
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def get_first_adb_device() -> str | None:
    """Return the first connected ADB device ID, or None."""
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                return parts[0]
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _capture_exec_out(device: str, output_path: Path) -> bool:
    """Capture via adb exec-out screencap -p (default, fast)."""
    result = subprocess.run(
        ["adb", "-s", device, "exec-out", "screencap", "-p"],
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        err = result.stderr.decode(errors="replace").strip()
        print(f"[ERROR] adb exec-out screencap failed (code={result.returncode})")
        if err:
            print(f"  stderr: {err}")
        return False
    raw = result.stdout.replace(b"\r\n", b"\n").replace(b"\r", b"")
    if len(raw) < 100:
        print(f"[ERROR] Screencap output too small ({len(raw)} bytes)")
        return False
    if not raw.startswith(b"\x89PNG"):
        print("[ERROR] Output is not a valid PNG")
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(raw)
    return True


def _capture_pull(device: str, output_path: Path) -> bool:
    """Capture via adb shell screencap + pull (slower but more reliable on some emulators)."""
    remote = "/sdcard/screencap_yulang.png"
    r1 = subprocess.run(
        ["adb", "-s", device, "shell", "screencap", "-p", remote],
        capture_output=True,
        timeout=15,
    )
    if r1.returncode != 0:
        err = r1.stderr.decode(errors="replace").strip()
        print(f"[ERROR] adb shell screencap failed (code={r1.returncode})")
        if err:
            print(f"  stderr: {err}")
        return False
    output_path.parent.mkdir(parents=True, exist_ok=True)
    r2 = subprocess.run(
        ["adb", "-s", device, "pull", remote, str(output_path)],
        capture_output=True,
        timeout=10,
    )
    subprocess.run(
        ["adb", "-s", device, "shell", "rm", "-f", remote],
        capture_output=True,
        timeout=5,
    )
    if r2.returncode != 0:
        print(f"[ERROR] adb pull failed (code={r2.returncode})")
        return False
    return True


def capture_adb_screenshot(device: str, output_path: Path, method: str = "exec-out") -> bool:
    """Capture raw screenshot from device and save to output_path."""
    try:
        if method == "pull":
            ok = _capture_pull(device, output_path)
        else:
            ok = _capture_exec_out(device, output_path)
        if ok:
            print(f"[OK] Saved raw screenshot to {output_path}")
        return ok
    except FileNotFoundError:
        print("[ERROR] adb not found. Install: brew install android-platform-tools")
        return False
    except subprocess.TimeoutExpired:
        print("[ERROR] adb timed out. Try: --method pull")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Capture raw screenshot from BlueStacks/Android via ADB",
    )
    parser.add_argument(
        "--device",
        type=str,
        default=None,
        help="ADB device ID (e.g. emulator-5554). Auto-detect if omitted.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output path. Default: screenshots/adb_YYYYMMDD_HHMMSS.png",
    )
    parser.add_argument(
        "--method",
        choices=["exec-out", "pull"],
        default="exec-out",
        help="Capture method. Use 'pull' if exec-out fails (BlueStacks).",
    )
    args = parser.parse_args()

    device = args.device or get_first_adb_device()
    if not device:
        print("[ERROR] No ADB device found. Run 'adb devices' and ensure BlueStacks ADB is enabled.")
        return 1

    if args.output:
        output_path = Path(args.output)
    else:
        root = Path(__file__).resolve().parent.parent
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = root / "screenshots" / f"adb_{ts}.png"

    success = capture_adb_screenshot(device, output_path, method=args.method)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
