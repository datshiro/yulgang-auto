# Design Spec: ADB/BlueStacks Quest Automation Setup

This document outlines the setup and verification of the ADB-based quest automation for the Yulang game on macOS, specifically targeting BlueStacks.

## Goals
- Install and configure `adb` on macOS.
- Connect the project to a running BlueStacks emulator.
- Verify the Python environment and dependencies for ADB-based image recognition.
- Successfully execute a quest action in `--mode adb`.

## 1. System-Level ADB Installation
Since the user is on macOS, we will use Homebrew to install the Android platform tools.
- **Action:** `brew install --cask android-platform-tools`
- **Verification:** `adb version` must return a valid version string.

## 2. Python Environment & BlueStacks Verification
We will use the existing `venv` and ensure all necessary libraries for ADB interaction and image processing are present.
- **Action:** Activate `venv` (`source venv/bin/activate`).
- **Action:** Install/update dependencies: `pip install -r requirements.txt`.
- **BlueStacks Configuration:** The user must ensure "Android Debugging" is enabled in BlueStacks Preferences/Settings.
- **Connection:** `adb connect localhost:5555` (or the specific port shown in BlueStacks settings).

## 3. Project Integration & Visual Test
Verify that the project's internal backend can communicate with the emulator.
- **Tool:** `python scripts/adb_screenshot.py` - Captures the current emulator screen to `debug_adb.png` to verify "vision".
- **Tool:** `python main.py --mode adb --action list_devices` - Confirms the `core.backend` correctly identifies the connected BlueStacks instance.

## 4. Quest Automation "Dry Run"
Verify the end-to-end flow of a quest action using ADB.
- **Command:** `python main.py --mode adb --action do_quest`
- **Success Criteria:** 
    1. The script captures the emulator screen.
    2. The script identifies UI elements using ADB-specific templates (in `templates/adb/`).
    3. The script sends a tap command via ADB to the emulator.

## Dependencies
- `opencv-python`: For template matching on ADB screenshots.
- `numpy`: Required by OpenCV.
- `Pure-Python-ADB` (if used) or standard shell-based `adb` calls.

## Risks & Mitigations
- **Port Mismatch:** BlueStacks often uses dynamic ports for ADB. Mitigation: Use `main.py --action list_devices` to find the correct ID if `localhost:5555` fails.
- **Template Mismatch:** Emulator resolution might differ from native Mac resolution. Mitigation: Ensure templates in `templates/adb/` match the emulator's current DPI/Resolution.
