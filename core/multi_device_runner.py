"""
Run automation on multiple ADB devices in parallel (same semantics as CLI --config).

Used by main.py and the GUI; use log= callback instead of print; optional cancel_event
for cooperative stop between loop iterations.
"""

from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.backend import ADBBackend
from core.screen import set_backend, set_template_subdir
from flows import (
    run_complete_quest,
    run_do_quest,
    run_open_inventory,
    run_open_menu_chuyen_doi,
    run_quick_sell,
    run_teleport_to_huyen_bot,
)
from programs import run_chuyen_doi_program

LogFn = Callable[[str], None]

_ACTION_HANDLERS = {
    "open_inventory": run_open_inventory,
    "quick_sell": run_quick_sell,
    "complete_quest": run_complete_quest,
    "do_quest": run_do_quest,
    "teleport_to_huyen_bot": run_teleport_to_huyen_bot,
    "open_menu_chuyen_doi": run_open_menu_chuyen_doi,
    "run_chuyen_doi_program": run_chuyen_doi_program,
}


def _run_for_device(
    device_config: dict,
    action: str,
    threshold: float,
    stone_tags: list[str] | None,
) -> tuple[str, bool, str]:
    """Run action for a single device. Returns (device_id, success, error_msg)."""
    device_id = device_config.get("serial")
    if not device_id:
        return ("<unknown>", False, "Missing 'serial' in device config")

    try:
        set_backend(ADBBackend(device_id))
        set_template_subdir("adb")

        fn = _ACTION_HANDLERS.get(action)
        if not fn:
            return (device_id, False, f"Unknown action: {action}")

        if action in ("open_menu_chuyen_doi", "run_chuyen_doi_program"):
            success = fn(threshold=threshold, stone_tags=stone_tags)
        else:
            success = fn(threshold=threshold)
        return (device_id, success, "" if success else "Action returned False")
    except Exception as e:
        return (device_id, False, str(e))


def run_multi_device_adb(
    devices: list[dict],
    action: str,
    threshold: float,
    stone_tags: list[str] | None,
    loop: bool,
    loop_interval: float,
    log: LogFn,
    cancel_event: threading.Event | None = None,
) -> int:
    """
    Run ``action`` on each device dict (must include ``serial``).

    Returns 0 on full success, 1 if any device failed or no devices.
    If ``loop`` is True and ``cancel_event`` is set between iterations, returns 0.
    """
    if not devices:
        log("[ERROR] No devices in config")
        return 1

    subprocess.run(["adb", "start-server"], capture_output=True, timeout=10)

    def run_once() -> int:
        log(f"[MULTI] Running '{action}' on {len(devices)} devices...")
        results: list[tuple[str, bool, str]] = []
        with ThreadPoolExecutor(max_workers=len(devices)) as executor:
            futures = {
                executor.submit(_run_for_device, d, action, threshold, stone_tags): d
                for d in devices
            }
            for future in as_completed(futures):
                device_id, success, error = future.result()
                results.append((device_id, success, error))
                status = "OK" if success else "FAIL"
                msg = f"  [{status}] {device_id}"
                if error:
                    msg += f" - {error}"
                log(msg)

        failed = [d for d, s, _e in results if not s]
        if failed:
            log(f"[MULTI] {len(failed)}/{len(devices)} device(s) failed")
            return 1
        log(f"[MULTI] All {len(devices)} device(s) succeeded")
        return 0

    if not loop:
        return run_once()

    if action not in ("quick_sell", "do_quest", "run_chuyen_doi_program"):
        log("[WARN] --loop works best with quick_sell, do_quest, or run_chuyen_doi_program")

    iteration = 0
    try:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                log(f"\n[LOOP] Stopped after {iteration} iteration(s).")
                return 0
            iteration += 1
            log(f"[LOOP #{iteration}]")
            rc = run_once()
            if rc != 0:
                return rc
            log(f"[LOOP] Next run in {loop_interval}s")
            end = time.monotonic() + loop_interval
            while time.monotonic() < end:
                if cancel_event is not None and cancel_event.is_set():
                    log(f"\n[LOOP] Stopped after {iteration} iteration(s).")
                    return 0
                remaining = end - time.monotonic()
                time.sleep(min(0.5, remaining) if remaining > 0 else 0)
    except KeyboardInterrupt:
        log(f"\n[LOOP] Stopped after {iteration} iteration(s).")
        return 0
