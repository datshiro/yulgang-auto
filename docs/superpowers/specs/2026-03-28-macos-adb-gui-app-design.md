# macOS ADB GUI App Design

## Purpose

Ship a **macOS `.app`** that runs the existing Yulang automation against **ADB devices only**, with a **graphical UI** instead of Terminal. **Developers keep using the repo and `python main.py`** for Mac-native mode, scripts, and tests; the **bundled app** is the primary interface for **multi-device, ADB-only** runs using the same flows and templates as today.

## Goals

- **ADB-only in the app:** No Mac backend toggle in the UI; Mac mode remains CLI-only (`--mode mac` in the repository).
- **Action parity (ADB):** Expose every automation action that applies to ADB today: `open_inventory`, `quick_sell`, `complete_quest`, `do_quest`, `teleport_to_huyen_bot`, `open_menu_chuyen_doi`, `run_chuyen_doi_program`, plus **`list_devices`** as a diagnostic action (refresh / show connected devices).
- **Multi-device on the frontend:** **Devices and run settings are visible and editable in the UI**, not hidden behind a file-only workflow. The user can **refresh** connected targets from ADB, **select which serials to include** in the run (e.g. checkboxes or multi-select), **add or remove** device rows (manual serial entry when needed), and edit **threshold**, **loop**, **loop_interval**, and **stones** directly on screen. **Optional persistence:** **Import** JSON/YAML populates the same fields (schema identical to `--config` today: `{ "devices": [ { "serial": "..." }, ... ], ... }` or a top-level list, plus optional `loop`, `loop_interval`, `threshold`). **Export** writes the current on-screen state to a file so it stays compatible with `python main.py --config`.
- **BYO ADB:** Users install **Android Platform Tools**; `adb` must be on **`PATH`** (or documented equivalent the app resolves). If `adb` is missing or not runnable, the app shows a **short, actionable** message (install Platform Tools, ensure BlueStacks ADB enabled, `adb kill-server && adb start-server`, etc.).
- **Options in UI:** Match CLI capabilities relevant to ADB multi/single run: **threshold**, **stones** (comma-separated tags for chuyển đổi actions), **loop** and **loop_interval** (with the same practical note as CLI: loop is intended mainly for `quick_sell`, `do_quest`, `run_chuyen_doi_program`). **Game app / background-capture / no-restore-focus** are **out of scope** in the app (Mac-only concerns).
- **Bundled assets:** The frozen `.app` includes **`templates/adb/`** (and any shared template roots the code expects) so end users do not need a checkout.
- **Observable runs:** A **scrollable log** shows progress and errors (equivalent to stdout/stderr from today’s `[MULTI]` / flow prints). **Stop** cancels the current run cooperatively where feasible (see Error handling).

## Non-goals (v1)

- Mac window capture, Accessibility, or **`--mode mac`** in the GUI.
- **Bundling `adb`** inside the app (deferred; BYO only for v1).
- **Notarization / App Store** as a hard requirement for v1 (document manual “Open Anyway” / ad-hoc signing if needed); revisit if friction is high.
- Replacing **pytest** or CLI for CI; the app is a **distribution shell** around the same Python core.

## Recommended approach

**Python-native UI + freeze with PyInstaller or py2app** (v1):

- **Single stack:** The GUI calls **shared Python APIs** (refactored from `main.py` where needed) so behavior stays aligned with `python main.py --mode adb --config ...`.
- **Trade-off accepted:** Packaging and code signing for frozen Python are **more work** than a thin Swift shell; mitigation is clear build docs and later optional migration to a native host (see Risks).

## Architecture

### High-level

```
┌─────────────────────────────────────┐
│  macOS .app (PyInstaller / py2app)   │
│  ┌──────────────┐  ┌──────────────┐ │
│  │ UI thread    │  │ Worker       │ │
│  │ (Qt/Tk…)     │──│ run_multi or │ │
│  │              │  │ equivalent   │ │
│  └──────────────┘  └──────────────┘ │
│         │                  │        │
│         │    log queue     │        │
│         ▼                  ▼        │
│  ┌─────────────────────────────────┐│
│  │ templates/adb (bundled)         ││
│  │ core/, flows/, programs/        ││
│  └─────────────────────────────────┘│
└─────────────────────────────────────┘
           │ subprocess / PATH
           ▼
      adb (host-installed)
```

### UI responsibilities

- **Devices panel:** **Refresh** queries `adb` (same discovery as `get_adb_devices` / `list_devices`) and shows **status** per serial (`device`, `offline`, etc.). User **ticks** which serials participate in the next run (empty selection → validation error before Run). Support **adding a row** with a typed serial and **removing** rows so the list does not depend only on the last refresh (e.g. planning before plugging in a device).
- **Run options panel:** Always-visible fields for **threshold**, **stones**, **loop**, **loop_interval** (same semantics as CLI).
- **Import / Export config:** **Import** fills devices + run options from a JSON/YAML file (same schema as `--config`). **Export** saves the **current** UI state to JSON/YAML for reuse or CLI. Remember **last import/export path** in app prefs if convenient.
- **Pick action** from the enumerated list above (including **`list_devices`** as **Refresh devices** in the devices panel, or keep as a separate button that only updates the list/log).
- **Run** / **Stop**: build the device list from **checked/selected rows** (each with a `serial`); start worker; disable Run while running or show clear state.
- **Log panel:** append lines from the worker; optional “Copy log” / “Clear”.
- **ADB check:** on launch or before Run, verify `adb` is invocable (e.g. `adb version`); show banner or modal if not.

### Worker and core integration

- **Do not block the UI thread** during automation. Run **`_run_multi_device` semantics** (or a new **`run_adb_multi_device(...)`** function extracted from `main.py`) in a **background thread** or **subprocess**.
- **Subprocess option:** spawn `python -m yulang_adb_worker` with serialized args and stream output to the UI. **Pros:** strongest isolation from `set_backend` globals. **Cons:** must bundle interpreter and entrypoint cleanly.
- **In-process option:** call extracted runner in a **daemon thread**; requires **auditing global backend state** (`set_backend`, `set_template_subdir`) so the GUI and worker do not race. The existing multi-device path already uses `ThreadPoolExecutor` per device; **document** that the **GUI must not** trigger concurrent runs from multiple threads without a mutex.

**Recommendation for v1:** Extract a runner that accepts **structured input**: `devices: list[dict]` (each `{"serial": "..."}`) plus **action**, **threshold**, **stone_tags**, **loop**, **loop_interval**, and **`log` callback**. The **CLI** continues to call **`_load_config(path)`** and pass the result into that runner; the **GUI** passes the **current form state** (selected device rows only). **One automation run at a time** from the UI.

### `list_devices` in the GUI

- Primary use: drives the **Refresh** action on the devices panel (update list + statuses). Optionally mirror troubleshooting text to the **log** when no devices are found, matching today’s CLI hints.

## Configuration precedence

- **Source of truth while editing:** The **on-screen** device list and run-option fields. **Import** overwrites those fields from file using the same merge rules as **`_run_multi_device`**: imported **`threshold`**, **`loop_interval`**, and **`loop`** populate the widgets; imported **`devices`** populate the table (user may then change selection or rows).
- **On Run:** Use **exactly** the values shown in the UI for selected devices and options (no hidden file state unless the UI was populated from import and not edited).
- **CLI parity:** Exporting the UI state to JSON and running `python main.py --mode adb --config that.json --action ...` should match a Run from the app with the same selections.

## Data flow

1. User adjusts **devices** (refresh / checkboxes / add-remove rows) and **run options** → UI builds a **request** (`devices` subset, action, threshold, stones, loop flags).
2. Worker runs **`adb start-server`**, then **parallel per-device** execution matching **`_run_for_device`** for each selected serial.
3. Each line that would today go to `print` is routed to the **log callback** (thread-safe queue to UI thread).
4. Exit code / success summary updates UI state (e.g. “All succeeded” vs “N failed”).

## Error handling

- **Missing `adb`:** Block or warn before run; no silent failure.
- **Bad import file / invalid rows:** Surface parser and validation errors in the log or inline; do not crash the app. **Run** with **no device selected** or **empty serial** → clear validation message.
- **Per-device failure:** Same aggregation as CLI; show which serial failed and message.
- **Stop:** Set a **shared cancel flag** inspected between loop iterations or between devices where practical; for long-running **inner** loops (`run_chuyen_doi_program`), document that stop may take effect **after** the current flow step unless flows are later instrumented for cancellation (v1: **best-effort** stop between multi-device batches and between **loop** iterations).

## Testing

- **Unit tests:** Keep covering `core/`, flows, **`_load_config`**, and the **multi-device runner** when given **`devices` + options** (CLI path loads file then calls runner; GUI passes form state).
- **Manual checklist:** Frozen `.app` finds bundled templates; a Run with the same **selected serials and options** as an exported JSON matches `python main.py --mode adb --config <file> ...`; missing `adb` shows the correct error.

## Risks and follow-ups

| Risk | Mitigation |
|------|------------|
| PyInstaller + signing + Gatekeeper | Document build steps; optional later move to Swift shell + bundled Python |
| Global backend state | Single-flight runs; extract runner; optional subprocess worker |
| Thread safety of log UI | Queue + timer or main-thread dispatch per toolkit |

## Success criteria

- User can **see and edit** the device list and run options in the UI, **refresh** from ADB, and **Run** without relying on a config file; **Import/Export** remains optional for sharing presets with CLI or other users.
- For the **same** device list + options, outcomes match `python main.py --mode adb --config <exported-file> --action <action> ...`.
- **Without** Platform Tools installed, the app explains what to install instead of a traceback.
- **Templates** ship inside the `.app` and match **ADB** resolution (`templates/adb/`).
