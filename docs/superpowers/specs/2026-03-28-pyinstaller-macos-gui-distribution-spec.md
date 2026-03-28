# PyInstaller macOS GUI distribution specification

## Purpose

Define the **recommended app-like distribution** for the ADB-only desktop GUI: a **windowed macOS `.app` bundle** built with **PyInstaller**, launched **without a Terminal window**, with **ADB templates bundled** so users do not need a repository checkout.

**Related documents:** GUI behavior, features, and CLI parity are specified in [2026-03-28-macos-adb-gui-app-design.md](./2026-03-28-macos-adb-gui-app-design.md). User-facing build steps are summarized in [BUILD_GUI.md](../../BUILD_GUI.md).

## Selected approach

| Criterion | PyInstaller `.app` |
|-----------|-------------------|
| Terminal on launch | **None** (`console=False` in spec) |
| Double-click / Dock | **Yes** (`BUNDLE` → `YulangADB.app`) |
| Bundles Python + deps | **Yes** (single artifact for end users) |
| Template assets in bundle | **Yes** (`datas`: `templates/adb` → `templates/adb`) |
| `adb` binary | **Not bundled** (host must install Android Platform Tools; same as design doc BYO ADB) |

**Alternatives considered (not chosen for primary distribution):** running `python -m gui` from Terminal (blocks shell); `nohup … &` (still requires a Python environment); py2app (valid but duplicate tooling with no project spec today).

## Artifact

| Item | Value |
|------|--------|
| Output path | `dist/YulangADB.app` (after build from repo root) |
| Human-visible name | **YulangADB** |
| Bundle identifier | `local.yulang.adb` |
| Entry script | `gui/__main__.py` (equivalent to `python -m gui`) |
| Windowed vs console | **Windowed** — no attached console process for stdout/stderr |

## Functional requirements

1. **Launch:** User opens `YulangADB.app` from Finder, Dock, or `open dist/YulangADB.app`; the tkinter main window appears without spawning an interactive Terminal session.
2. **Template resolution:** OpenCV/template matching loads **ADB** templates from paths under the PyInstaller extract dir (`sys._MEIPASS`), consistent with `core/screen.py` `_get_project_root()` when `sys.frozen` is true.
3. **Runtime parity:** In-app runs use the same automation core, flows, and multi-device behavior as `python main.py --mode adb --config …` for equivalent inputs (per GUI design doc).
4. **External dependency:** `adb` must be available on the user’s **`PATH`** (or documented workaround); missing `adb` surfaces as an **actionable UI message**, not an unhandled crash where feasible.
5. **Rebuild reproducibility:** Build instructions name **Python version with working `tkinter`**, **same virtualenv** as development dependencies (`requirements.txt`), and **PyInstaller** as an explicit dev dependency for the freeze step.

## Technical specification (`yulang_gui.spec`)

### Analysis

- **Script:** `gui/__main__.py` (single entry; imports `gui.mainwindow`).
- **pathex:** Repository root so imports resolve (`core`, `flows`, `programs`, etc.).
- **datas:** `(templates/adb, templates/adb)` — preserve directory layout expected by template resolution.
- **hiddenimports:** At minimum `PIL._tkinter_finder` (Pillow + tkinter). **Extend** when PyInstaller omits dynamic imports (e.g. OpenCV, `cv2`; add to `hiddenimports` if build or runtime import errors occur).

### EXE

- **name:** `YulangADB`
- **console:** `False` (mandatory for app-like UX).
- **exclude_binaries:** `True` with `COLLECT` + `BUNDLE` (standard one-folder-style macOS app layout).

### BUNDLE

- **name:** `YulangADB.app`
- **icon:** Optional future enhancement (`None` in v1).
- **codesign_identity / entitlements:** Optional; unsigned builds may require **System Settings → Privacy & Security → Open Anyway** on first launch.

### Version control

- The spec file **`yulang_gui.spec`** is the source of truth for packaging layout; changes to bundled data or hidden imports belong in that file and should be reflected here when behavior changes.

## Build environment

- **OS:** macOS (target platform for `.app`).
- **Python:** Interpreter used for the project venv must support `import tkinter` (see [BUILD_GUI.md](../../BUILD_GUI.md) for Homebrew `python-tk@…` vs python.org builds).
- **Dependencies:** `pip install -r requirements.txt` in venv; `pip install pyinstaller` for the build step only (or document in requirements optional `[dev]` if introduced later).

## Build procedure

From repository root:

```bash
source venv/bin/activate
pip install pyinstaller
pyinstaller yulang_gui.spec
```

**Outputs:** `dist/YulangADB.app`, build cache under `build/` (may be gitignored).

**Clean rebuild:** Remove `build/` and `dist/` before `pyinstaller` when diagnosing stale bundles.

## Verification checklist (acceptance)

- [ ] `YulangADB.app` launches with **no Terminal window**.
- [ ] Main window appears; ADB refresh / run paths execute without **“template not found”** errors for bundled `templates/adb` assets.
- [ ] With `adb` on PATH and devices connected, a representative action completes as it does from CLI with the same config export.
- [ ] With `adb` absent or broken, the app shows a **clear** error path (banner, dialog, or log) rather than a silent failure where the design specifies messaging.

## Non-goals (this spec)

- **Apple notarization** and **App Store** distribution as mandatory deliverables.
- **Bundling `adb`** inside the app.
- **Code signing** automation in CI (document only unless added later).
- **Universal2 / multi-arch** policy beyond PyInstaller defaults (revisit if Apple Silicon vs Intel artifacts are required).

## Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Gatekeeper blocks unsigned app | Document “Open Anyway”; optional ad-hoc `codesign` for local use |
| PyInstaller misses a native or lazy import | Add to `hiddenimports`; re-run build; check PyInstaller warnings |
| Broken tkinter in freeze Python | Use same interpreter that passes `python -c "import tkinter"` before freezing |
| Large `.app` size | Expected for embedded Python + OpenCV; acceptable for v1 |

## Maintenance

- When adding **new runtime data** (e.g. extra template roots), update **`datas`** in `yulang_gui.spec` and verify `_get_project_root()` / template resolution still match.
- When adding dependencies with **hidden imports**, extend **`hiddenimports`** and re-verify a cold launch of the `.app`.
- Keep **bundle_identifier** stable if macOS preferences or shortcuts rely on it; change only with intentional migration notes.

## Success criteria

End users who do not use the repository can **double-click `YulangADB.app`**, run ADB automation with **bundled templates**, and **never need to leave a Terminal session attached** to the GUI process for normal operation.
