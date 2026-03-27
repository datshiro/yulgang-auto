# ADB/BlueStacks Quest Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up and verify ADB-based quest automation for Yulang on BlueStacks (macOS).

**Architecture:** Install system-level ADB, configure Python environment, connect to BlueStacks, and verify end-to-end communication via image recognition.

**Tech Stack:** ADB (Android Debug Bridge), Python 3.x, OpenCV, NumPy, PyAutoGUI.

---

### Task 1: System ADB Installation

**Files:**
- System: `/usr/local/bin/adb` (or similar via Homebrew)

- [ ] **Step 1: Install android-platform-tools via Homebrew**

Run: `brew install --cask android-platform-tools`
Expected: Installation completes successfully.

- [ ] **Step 2: Verify ADB installation**

Run: `adb version`
Expected: Returns a valid version string (e.g., "Android Debug Bridge version 1.0.41").

---

### Task 2: Python Environment Setup

**Files:**
- Modify: `requirements.txt` (verify content)
- Environment: `venv/`

- [ ] **Step 1: Activate virtual environment and install dependencies**

Run:
```bash
source venv/bin/activate
pip install -r requirements.txt
```
Expected: All dependencies (opencv-python, numpy, etc.) are installed.

- [ ] **Step 2: Verify OpenCV installation**

Run: `python -c "import cv2; print(cv2.__version__)"`
Expected: Prints a version number (e.g., "4.11.0").

---

### Task 3: BlueStacks ADB Connection

**Files:**
- Manual Config: BlueStacks Settings

- [ ] **Step 1: Connect to BlueStacks via ADB**

Run: `adb connect localhost:5555`
Expected: Returns "connected to localhost:5555" or "already connected".

- [ ] **Step 2: List connected devices**

Run: `adb devices`
Expected: Lists `localhost:5555 device`.

---

### Task 4: Project Integration Verification

**Files:**
- Run: `scripts/adb_screenshot.py`
- Run: `main.py`

- [ ] **Step 1: Capture test screenshot from ADB**

Run: `python scripts/adb_screenshot.py`
Expected: `debug_adb.png` is created in the project root and shows the game screen.

- [ ] **Step 2: Verify device detection in main script**

Run: `python main.py --mode adb --action list_devices`
Expected: Prints `localhost:5555  (device)`.

---

### Task 5: Quest Automation Dry Run

**Files:**
- Run: `main.py`

- [ ] **Step 1: Run quest action in ADB mode**

Run: `python main.py --mode adb --action do_quest`
Expected: Script logs that it is searching for quest templates and attempts a click (or logs "not found" if UI differs).

- [ ] **Step 2: Commit setup changes**

Run:
```bash
git add docs/superpowers/specs/2026-03-27-adb-quest-setup-design.md docs/superpowers/plans/2026-03-27-adb-quest-setup-plan.md
git commit -m "chore: setup and verify ADB/BlueStacks quest automation"
```
