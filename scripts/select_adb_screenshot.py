#!/usr/bin/env python3
import subprocess
import sys
import argparse
from pathlib import Path
from datetime import datetime

def get_devices():
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
        
        devices = []
        for line in result.stdout.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])
        return devices
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

if __name__ == "__main__":
    pass
