# PyInstaller macOS GUI distribution — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use **superpowers:subagent-driven-development** (recommended) or **superpowers:executing-plans** to run tasks in order. Checkboxes (`- [ ]`) track completion.

**Goal:** Deliver and **verify** the **app-like** macOS artifact **`dist/YulangADB.app`**: windowed launch (no Terminal), bundled **`templates/adb`**, stable PyInstaller layout, and docs that match reality.

**Specification:** [2026-03-28-pyinstaller-macos-gui-distribution-spec.md](../specs/2026-03-28-pyinstaller-macos-gui-distribution-spec.md)

**Prerequisite:** GUI and core features from [2026-03-28-macos-adb-gui-app-plan.md](./2026-03-28-macos-adb-gui-app-plan.md) (Tasks 1–7) are implemented or in progress; this plan focuses on **freeze, validate, and harden** the distribution. It **extends** Task 8 of that plan with acceptance work and spec alignment.

---

## File map

| File / artifact | Action | Notes |
|-----------------|--------|--------|
| `yulang_gui.spec` | Verify / adjust | `datas`, `hiddenimports`, `console=False`, `BUNDLE` name |
| `core/screen.py` | Verify | `_get_project_root()` → `sys._MEIPASS` when `sys.frozen` |
| `docs/BUILD_GUI.md` | Verify / tweak | Build commands, output path `dist/YulangADB.app`, Gatekeeper, `_tkinter` |
| `docs/superpowers/specs/2026-03-28-pyinstaller-macos-gui-distribution-spec.md` | Reference | Update only if packaging behavior changes |
| `dist/`, `build/` | Generated | Clean before release builds; typically gitignored |

---

## Task D1: Frozen template root audit

**Objective:** No code path assumes a writable repo checkout for ADB templates when frozen.

- [x] **Step 1:** Confirm `_get_project_root()` in `core/screen.py` returns `Path(sys._MEIPASS)` when `getattr(sys, "frozen", False)` and `_MEIPASS` is set (see spec §Functional requirements).

- [x] **Step 2:** Search for other `Path(__file__).resolve().parent...` usages under `core/`, `flows/`, `programs/`, `gui/` that resolve **data files** (templates, assets). If any bypass `_get_project_root()` or equivalent, refactor or document an exception. *(Only `scripts/*` uses repo-relative paths; not bundled in the GUI entrypoint.)*

- [x] **Step 3:** Confirm `set_template_subdir("adb")` + bundled layout resolves files under `templates/adb/...` inside the bundle (same relative paths as dev tree).

---

## Task D2: `yulang_gui.spec` vs distribution spec

**Objective:** Spec file matches [distribution spec](../specs/2026-03-28-pyinstaller-macos-gui-distribution-spec.md) §Technical specification.

- [x] **Step 1:** Check **entry** is `gui/__main__.py`, **pathex** is repo root, **datas** includes `(templates/adb, templates/adb)`.

- [x] **Step 2:** Confirm **EXE** `console=False`, **BUNDLE** `name='YulangADB.app'`, **bundle_identifier** `local.yulang.adb`.

- [x] **Step 3:** Review **hiddenimports**: keep `PIL._tkinter_finder`; add **`cv2`** (and any other modules PyInstaller omits) after a trial build if import errors occur at runtime.

- [x] **Step 4 (optional):** If OpenCV data files are missing at runtime, add `collect_data_files("cv2")` (or PyInstaller-recommended hook pattern) to `datas` per build log warnings. *(Trial build used `hook-cv2.py`; no extra datas required.)*

---

## Task D3: Clean build and smoke test

**Objective:** Reproducible `dist/YulangADB.app` from a clean tree.

- [x] **Step 1:** From repo root, with `venv` active and `requirements.txt` installed: `pip install pyinstaller`.

- [x] **Step 2:** `rm -rf build dist` then `pyinstaller yulang_gui.spec`. Capture PyInstaller **warnings** about missing hidden imports for follow-up. *(Build OK; see `build/yulang_gui/warn-yulang_gui.txt` — e.g. harmless `msvcrt` ctypes warning on macOS.)*

- [ ] **Step 3:** Launch `open dist/YulangADB.app` (or double-click in Finder). **Assert:** no Terminal window attaches to the GUI process.

- [ ] **Step 4:** In the app, run **Refresh devices** (or equivalent) with `adb` on PATH; run a **light action** (e.g. `list_devices` or a short flow) and confirm **no template path errors** in the log.

- [ ] **Step 5:** Temporarily remove or rename `adb` on PATH (or use a clean user account) and confirm **actionable messaging** (per GUI design / `adb_check`) rather than a raw traceback-only failure, where feasible.

---

## Task D4: Documentation pass

**Objective:** [BUILD_GUI.md](../../BUILD_GUI.md) is sufficient for a maintainer to ship a bundle.

- [x] **Step 1:** Ensure build output path is **`dist/YulangADB.app`** everywhere (not a stale folder name).

- [x] **Step 2:** Document **clean rebuild** (`rm -rf build dist`) when debugging “stale” template or code in the bundle.

- [x] **Step 3:** Link to the **distribution spec** for full requirements and acceptance checklist (one line in BUILD_GUI or in plan index is enough).

- [x] **Step 4 (optional):** Add a one-line **ad-hoc codesign** example for local Gatekeeper relief (e.g. `codesign --force --deep --sign - dist/YulangADB.app`), with a note that this is not notarization.

---

## Task D5: Optional dev ergonomics

**Objective:** Lower friction for repeat builds (non-blocking).

- [x] **Step 1 (optional):** Add `pyinstaller` to a **dev** extras file (e.g. `requirements-dev.txt` or `requirements.txt` comment block) if the team wants a single install story — only if it matches repo conventions.

- [x] **Step 2 (optional):** Add a **`scripts/build_gui_app.sh`** that activates venv, cleans, and runs `pyinstaller yulang_gui.spec` with `set -e` — only if maintainers want a one-command build.

---

## Task D6: Acceptance sign-off

**Objective:** All items in distribution spec §Verification checklist are satisfied.

- [ ] `YulangADB.app` launches **without** a Terminal window. *(Manual: `open dist/YulangADB.app`.)*

- [ ] Template matching works for bundled **`templates/adb`** (no missing-file errors on representative runs). *(Manual GUI run; automated: `tests/test_frozen_project_root.py` covers bundle root resolution.)*

- [ ] With **`adb`** available, behavior matches CLI for the **same** exported config + action (spot-check).

- [x] With **`adb`** missing/unusable, user-visible **clear** error path (not silent failure). *(Covered by `tests/test_adb_check.py` + `gui/adb_check.py`; confirm banner/UI wiring manually once.)*

- [x] **Commit** (suggested message): `build: verify PyInstaller YulangADB.app distribution` — include any spec/hiddenimports/doc fixes in the same or follow-up commit.

---

## Spec coverage (self-review)

| Distribution spec section | Task(s) |
|---------------------------|---------|
| §Functional requirements (templates, PATH, parity) | D1, D3, D6 |
| §Technical specification (`yulang_gui.spec`) | D2 |
| §Build procedure | D3, D4 |
| §Risks (hidden imports, Gatekeeper, tkinter) | D2, D3, D4 |
| §Maintenance (datas / hiddenimports) | D2, D4 |

---

## Relationship to macOS ADB GUI app plan

| Item | Plan |
|------|------|
| Task 8 (PyInstaller + BUILD_GUI) | **Foundation** — spec file + frozen root + first-pass docs |
| This document | **Completion** — audit, trial build, acceptance, doc accuracy, optional scripts |

After D6, treat the distribution spec as the **authoritative requirement list** for future packaging changes; update the spec when `yulang_gui.spec` behavior changes.
