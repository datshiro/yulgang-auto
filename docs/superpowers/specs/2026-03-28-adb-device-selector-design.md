# ADB Device Screenshot Selector Design

## Purpose
A command-line utility to interactively select a connected ADB device and capture its screen, saving the result to a timestamped file. This improves the workflow for users with multiple emulators or devices connected.

## Architecture

### 1. Device Discovery
- Execute `adb devices` via `subprocess`.
- Parse the output to identify devices in the `device` state.
- Handle cases where no devices are found or the ADB daemon is not running.

### 2. Interactive Selection
- Present a numbered list of detected devices.
- Prompt the user for a selection (e.g., "Select device [1-N]: ").
- Validate user input, re-prompting on invalid entries.
- If only one device is connected, optionally skip selection and proceed (configurable via flag, default is to ask for clarity).

### 3. Screen Capture
- Use `adb -s <serial> exec-out screencap -p` for fast, direct capture.
- Implement a fallback to `adb shell screencap -p /sdcard/...` followed by `adb pull` if direct capture fails (important for some emulators).

### 4. Output Management
- Save screenshots to a `screenshots/` directory.
- Use a timestamped filename format: `adb_select_YYYYMMDD_HHMMSS.png`.
- Provide an optional `--output` argument to override the default path.

## Components

| Component | Responsibility |
|-----------|----------------|
| `get_devices()` | Returns a list of serial numbers for connected devices. |
| `select_device(devices)` | Handles the interactive CLI selection loop. |
| `capture_screenshot(serial, path)` | Executes the capture and saves the file. |
| `main()` | Orchestrates the flow and handles CLI arguments. |

## Success Criteria
- Script correctly lists all `device` state ADB targets.
- User can select a device by number.
- Captured image is a valid PNG and saved to the correct location.
- Graceful failure if no devices are connected.
