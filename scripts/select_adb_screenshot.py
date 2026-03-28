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

if __name__ == "__main__":
    devs = ["dev1", "dev2"]
    selected = select_device(devs)
    print(f"Selected: {selected}")
