#!/usr/bin/env python3
from __future__ import annotations
import subprocess
import sys
import argparse
from pathlib import Path
from datetime import datetime

def get_devices() -> list[str]:
    """Returns a list of serial numbers for devices in 'device' state."""
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            return []
        
        devices: list[str] = []
        for line in result.stdout.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

def select_device(devices: list[str]) -> str | None:
    """Interactively prompts user to select a device from the list."""
    if not devices:
        print("[ERROR] No devices found.")
        return None
    
    if len(devices) == 1:
        print(f"[INFO] Using only connected device: {devices[0]}")
        return devices[0]
    
    print("\nConnected ADB Devices:")
    for i, serial in enumerate(devices, 1):
        print(f"  {i}. {serial}")
    
    while True:
        try:
            choice = input(f"\nSelect device [1-{len(devices)}, q to quit]: ").strip().lower()
            if choice == 'q':
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(devices):
                return devices[idx]
            print(f"[ERROR] Please enter a number between 1 and {len(devices)}.")
        except ValueError:
            print("[ERROR] Invalid input. Enter a number or 'q'.")

def capture_screenshot(serial: str, output_path: Path) -> bool:
    """Captures screen via exec-out with fallback to pull."""
    print(f"[INFO] Capturing screen from {serial}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Method 1: exec-out (fast)
    try:
        result = subprocess.run(
            ["adb", "-s", serial, "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=15
        )
        if result.returncode == 0 and len(result.stdout) > 1000:
            # Fix line endings if necessary (some older adb versions)
            raw = result.stdout.replace(b"\r\n", b"\n").replace(b"\r", b"")
            output_path.write_bytes(raw)
            return True
    except Exception as e:
        print(f"[WARN] exec-out failed: {e}. Trying fallback...")

    # Method 2: Fallback (shell + pull)
    remote_path = "/sdcard/tmp_screencap.png"
    try:
        subprocess.run(["adb", "-s", serial, "shell", "screencap", "-p", remote_path], check=True)
        subprocess.run(["adb", "-s", serial, "pull", remote_path, str(output_path)], check=True)
        subprocess.run(["adb", "-s", serial, "shell", "rm", remote_path], check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] Capture failed: {e}")
        return False

def main() -> int:
    parser = argparse.ArgumentParser(description="Interactively capture ADB screenshot")
    parser.add_argument("-o", "--output", help="Output path for the screenshot")
    args = parser.parse_args()

    devices = get_devices()
    serial = select_device(devices)
    if not serial:
        return 1
    
    if args.output:
        output_path = Path(args.output)
    else:
        root = Path(__file__).resolve().parent.parent
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = root / "screenshots" / f"adb_select_{ts}.png"

    if capture_screenshot(serial, output_path):
        print(f"[OK] Screenshot saved to: {output_path}")
        return 0
    else:
        print("[ERROR] Failed to save screenshot.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
