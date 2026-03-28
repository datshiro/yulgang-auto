# macOS ADB GUI App Design

## Purpose

Ship a **macOS `.app`** that runs the existing Yulang automation against **ADB devices only**, with a **graphical UI** instead of Terminal. **Developers keep using the repo and `python main.py`** for Mac-native mode, scripts, and tests; the **bundled app** is the primary interface for **multi-device, ADB-only** runs using the same flows and templates as today.

## Goals

- **ADB-only in the app:** No Mac backend toggle in the UI; Mac mode remains CLI-only (`--mode mac` in the repository).
- **Action parity (ADB):** Expose every automation action that applies to ADB today: `open_inventory`, `quick_sell`, `complete_quest`, `do_quest`, `teleport_to_huyen_bot`, `open_menu_chuyen_doi`, `run_chuyen_doi_program`, plus **`list_devices`** as a diagnostic action (refresh / show connected devices).
- **Multi-device:** User selects a **config file** (JSON or YAML) with the same schema as `--config` today: either `{ "devices": [ { "serial": "..." }, ... ], ... }` or a top-level list of device objects, with optional top-level keys `loop`, `loop_interval`, `threshold` merged like `main.py` does.
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

- **Choose config file** (Open panel; remember last path in UserDefaults or a small prefs file).
- **Pick action** from the enumerated list above.
- **Edit** threshold, stones, loop, loop interval (defaults from config file when keys present; UI overrides or merges per existing `main.py` precedence: CLI-style UI values override file where specified).
- **Run** / **Stop**: start worker; disable Run while running or show clear state.
- **Log panel:** append lines from the worker; optional “Copy log” / “Clear”.
- **ADB check:** on launch or before Run, verify `adb` is invocable (e.g. `adb version`); show banner or modal if not.

### Worker and core integration

- **Do not block the UI thread** during automation. Run **`_run_multi_device` semantics** (or a new **`run_adb_multi_device(...)`** function extracted from `main.py`) in a **background thread** or **subprocess**.
- **Subprocess option:** spawn `python -m yulang_adb_worker` with serialized args and stream output to the UI. **Pros:** strongest isolation from `set_backend` globals. **Cons:** must bundle interpreter and entrypoint cleanly.
- **In-process option:** call extracted runner in a **daemon thread**; requires **auditing global backend state** (`set_backend`, `set_template_subdir`) so the GUI and worker do not race. The existing multi-device path already uses `ThreadPoolExecutor` per device; **document** that the **GUI must not** trigger concurrent runs from multiple threads without a mutex.

**Recommendation for v1:** Prefer **extracting a pure function** (e.g. `run_multi_device_from_config(path, action, threshold, stone_tags, loop, loop_interval, log: Callable[[str], None]) -> int`) used by both **CLI** and **GUI**, with **one automation run at a time** from the UI.

### `list_devices` in the GUI

- Invokes the same discovery path as today (`get_adb_devices` / troubleshooting output) and prints results into the log panel.

## Configuration precedence

Mirror `main.py` **`_run_multi_device`** behavior: **`threshold`** and **`loop_interval`** from the config file override UI defaults when those keys exist in the loaded file; **`loop`** is **on** if either the UI enables it **or** the config file sets `"loop": true`. The UI should show effective values after load (e.g. when opening a file, populate threshold/interval/loop from file) and apply the same merge on Run.

## Data flow

1. User selects config file and options → UI builds a **request** (action + numeric/string options + path).
2. Worker loads config via **`_load_config`**, runs **`adb start-server`**, then **parallel per-device** execution matching **`_run_for_device`**.
3. Each line that would today go to `print` is routed to the **log callback** (thread-safe queue to UI thread).
4. Exit code / success summary updates UI state (e.g. “All succeeded” vs “N failed”).

## Error handling

- **Missing `adb`:** Block or warn before run; no silent failure.
- **Bad config / missing serials:** Surface parser and validation errors in the log; do not crash the app.
- **Per-device failure:** Same aggregation as CLI; show which serial failed and message.
- **Stop:** Set a **shared cancel flag** inspected between loop iterations or between devices where practical; for long-running **inner** loops (`run_chuyen_doi_program`), document that stop may take effect **after** the current flow step unless flows are later instrumented for cancellation (v1: **best-effort** stop between multi-device batches and between **loop** iterations).

## Testing

- **Unit tests:** Keep covering `core/`, flows, and **`_load_config` / multi-device runner** after extraction (no regression vs `main.py` behavior).
- **Manual checklist:** Frozen `.app` finds bundled templates; multi-device config run matches CLI output for a small fixture config; missing `adb` shows the correct error.

## Risks and follow-ups

| Risk | Mitigation |
|------|------------|
| PyInstaller + signing + Gatekeeper | Document build steps; optional later move to Swift shell + bundled Python |
| Global backend state | Single-flight runs; extract runner; optional subprocess worker |
| Thread safety of log UI | Queue + timer or main-thread dispatch per toolkit |

## Success criteria

- User can select a valid **devices JSON/YAML**, pick any **ADB action**, set **stones/threshold/loop**, run **once or loop**, and see **equivalent outcomes** to `python main.py --mode adb --config <file> --action <action> ...` for the same file and options.
- **Without** Platform Tools installed, the app explains what to install instead of a traceback.
- **Templates** ship inside the `.app` and match **ADB** resolution (`templates/adb/`).
