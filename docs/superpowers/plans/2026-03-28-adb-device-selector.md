# ADB Device Screenshot Selector Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a Python script that interactively lets the user select an ADB device and captures its screen.

**Architecture:** A standalone Python script using `subprocess` to call `adb`. It follows a Discover -> Select -> Capture -> Save flow.

**Tech Stack:** Python 3, ADB (Android Debug Bridge).

---

### Task 1: Project Setup & Device Discovery

**Files:**
- Create: `scripts/select_adb_screenshot.py`
- Test: `scripts/test_adb_discovery.py` (temporary test)

- [ ] **Step 1: Write the failing test for device discovery**

```python
import subprocess
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent dir to sys.path to import the script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_get_devices():
    from scripts.select_adb_screenshot import get_devices
    
    mock_stdout = "List of devices attached\nemulator-5554\tdevice\nemulator-5556\toffline\n"
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_stdout, returncode=0)
        devices = get_devices()
        assert devices == ["emulator-5554"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 scripts/test_adb_discovery.py`
Expected: `ModuleNotFoundError: No module named 'scripts.select_adb_screenshot'`

- [ ] **Step 3: Implement `get_devices()` and basic script structure**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 scripts/test_adb_discovery.py`
Expected: `PASS` (or no output if using `assert`)

- [ ] **Step 5: Commit**

```bash
git add scripts/select_adb_screenshot.py
git commit -m "feat: implement adb device discovery"
```

---

### Task 2: Interactive Selection Logic

**Files:**
- Modify: `scripts/select_adb_screenshot.py`

- [ ] **Step 1: Add `select_device()` with validation**

```python
def select_device(devices):
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
```

- [ ] **Step 2: Manual verification of selection**
Add a temporary `main` to test selection:
```python
if __name__ == "__main__":
    devs = ["dev1", "dev2"]
    selected = select_device(devs)
    print(f"Selected: {selected}")
```
Run: `python3 scripts/select_adb_screenshot.py`
Expected: Interactively select dev1 or dev2.

- [ ] **Step 3: Commit**

```bash
git add scripts/select_adb_screenshot.py
git commit -m "feat: add interactive device selection"
```

---

### Task 3: Screen Capture Implementation

**Files:**
- Modify: `scripts/select_adb_screenshot.py`

- [x] **Step 1: Implement `capture_screenshot()` with fallback**

```python
def capture_screenshot(serial, output_path):
    """Captures screen via exec-out with fallback to pull."""
    print(f"[INFO] Capturing screen from {serial}...")
    
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
            output_path.parent.mkdir(parents=True, exist_ok=True)
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
```

- [x] **Step 2: Commit**

```bash
git add scripts/select_adb_screenshot.py
git commit -m "feat: implement screenshot capture logic"
```

---

### Task 4: Main Orchestration & CLI

**Files:**
- Modify: `scripts/select_adb_screenshot.py`

- [ ] **Step 1: Implement `main()` and argument parsing**

```python
def main():
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
```

- [ ] **Step 2: Final cleanup and permission**

Run: `chmod +x scripts/select_adb_screenshot.py`

- [ ] **Step 3: Commit**

```bash
git add scripts/select_adb_screenshot.py
git commit -m "feat: complete interactive screenshot script"
```

---

### Task 5: Final Verification

- [ ] **Step 1: Test with multiple devices (if possible) or mock**
- [ ] **Step 2: Verify file output in `screenshots/`**
- [ ] **Step 3: Remove temporary test file**

Run: `rm scripts/test_adb_discovery.py`
Run: `git commit -m "cleanup: remove temporary tests"`
