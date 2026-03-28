#!/usr/bin/env python3
"""
Game automation for Yulang / Tái Chiến Võ Lâm.

Supports macOS (native) and ADB (BlueStacks/emulator).

Usage:
    python main.py --action open_inventory
    python main.py --action quick_sell --mode mac
    python main.py --action quick_sell --mode adb
    python main.py --action quick_sell --mode adb --adb-device emulator-5554
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable
import sys
import time
import json
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

from core.window import run_with_game_focus
from flows import (
    run_complete_quest,
    run_do_quest,
    run_open_inventory,
    run_open_menu_chuyen_doi,
    run_quick_sell,
    run_teleport_to_huyen_bot,
)
from programs import run_chuyen_doi_program


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Automate Yulang game actions on Mac (mở túi, bán đồ nhanh, nhiệm vụ)",
    )
    parser.add_argument(
        "--mode",
        choices=["mac", "adb"],
        default="mac",
        help="Backend: mac (native) or adb (BlueStacks/emulator)",
    )
    parser.add_argument(
        "--adb-device",
        type=str,
        default=None,
        help="ADB device ID (e.g. emulator-5554). Auto-detect if omitted.",
    )
    parser.add_argument(
        "--action",
        choices=[
            "open_inventory",
            "quick_sell",
            "complete_quest",
            "do_quest",
            "teleport_to_huyen_bot",
            "open_menu_chuyen_doi",
            "run_chuyen_doi_program",
            "list_devices",
        ],
        required=True,
        help="Action to run",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run in a loop (sell -> quest -> sell -> ...)",
    )
    parser.add_argument(
        "--loop-interval",
        type=float,
        default=10.0,
        help="Seconds between loop iterations (default: 10)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.75,
        help="Template match threshold 0.0-1.0 (default: 0.75)",
    )
    parser.add_argument(
        "--game-app",
        type=str,
        default="com.rxjhvn.iOS",
        help="Game app name or bundle ID (default: com.rxjhvn.iOS)",
    )
    parser.add_argument(
        "--no-restore-focus",
        action="store_true",
        help="Do not restore previous app after automation (keep game in front)",
    )
    parser.add_argument(
        "--background-capture",
        action="store_true",
        help="Capture game window in background (no focus switch for screenshots; only activate for clicks)",
    )
    parser.add_argument(
        "--stones",
        type=str,
        default=None,
        help="Comma-separated stone tags for put_in (e.g. noi,2,3,huyet). Each maps to stones/{tag}.png. Used with open_menu_chuyen_doi and run_chuyen_doi_program.",
    )
    parser.add_argument(
        "--config", "-c",
        type=str,
        default=None,
        help="JSON/YAML config file with multiple devices. See devices.example.json for schema.",
    )
    return parser.parse_args()


def run_action(action: str, threshold: float, stone_tags: list[str] | None = None) -> bool:
    """Dispatch to the appropriate flow."""
    if action == "list_devices":
        import subprocess

        from core.backend import get_adb_devices

        devices = get_adb_devices()
        if not devices:
            print("No ADB devices found.")
            print("Troubleshooting:")
            print("  1. Ensure BlueStacks is running and ADB is enabled (Settings -> Advanced)")
            print("  2. Try: adb kill-server && adb start-server && adb devices")
            raw = subprocess.run(
                ["adb", "devices"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if raw.stdout:
                print("  Raw adb devices output:")
                print(raw.stdout)
            return False
        print("ADB devices:")
        for device_id, status in devices:
            print(f"  {device_id}  ({status})")
        return True

    handlers = {
        "open_inventory": run_open_inventory,
        "quick_sell": run_quick_sell,
        "complete_quest": run_complete_quest,
        "do_quest": run_do_quest,
        "teleport_to_huyen_bot": run_teleport_to_huyen_bot,
        "open_menu_chuyen_doi": run_open_menu_chuyen_doi,
        "run_chuyen_doi_program": run_chuyen_doi_program,
    }
    fn = handlers[action]
    if action in ("open_menu_chuyen_doi", "run_chuyen_doi_program"):
        return fn(threshold=threshold, stone_tags=stone_tags)
    return fn(threshold=threshold)


def _setup_adb_backend(adb_device: str | None):
    """Setup ADB backend. Returns run_fn or raises SystemExit."""
    from core.backend import ADBBackend, get_first_adb_device
    from core.screen import set_backend, set_template_subdir

    device = adb_device or get_first_adb_device()
    if not device:
        print("[ERROR] No ADB device found. Run 'adb devices' and ensure BlueStacks ADB is enabled.")
        raise SystemExit(1)
    set_backend(ADBBackend(device))
    set_template_subdir("adb")


def _setup_mac_backend(background_capture: bool, game_app: str):
    """Setup Mac backend (window or full-screen)."""
    from core.backend import MacBackend
    from core.screen import set_backend, set_template_subdir
    from core.window_capture import get_game_window_id

    set_template_subdir(None)

    if background_capture:
        window_id = get_game_window_id(game_app)
        if window_id is None:
            print(f"[WARN] Could not find window for '{game_app}'; falling back to full-screen capture")
        set_backend(MacBackend(window_id=window_id, game_app=game_app if window_id else None))
    else:
        set_backend(MacBackend(window_id=None, game_app=None))


def _load_config(config_path: str) -> tuple[list[dict], dict]:
    """Load device config from JSON or YAML file. Returns (devices, global_options)."""
    with open(config_path, "r") as f:
        content = f.read()
    if config_path.endswith((".yaml", ".yml")):
        if not YAML_AVAILABLE:
            raise ImportError("PyYAML not installed. Install with: pip install pyyaml")
        data = yaml.safe_load(content)
    else:
        data = json.loads(content)
    
    if isinstance(data, dict):
        devices = data.get("devices", [])
        options = {k: v for k, v in data.items() if k != "devices"}
    elif isinstance(data, list):
        devices = data
        options = {}
    else:
        raise ValueError("Config must contain 'devices' list or be a list of devices")
    return devices, options


def _run_for_device(device_config: dict, action: str, threshold: float, stone_tags: list[str] | None) -> tuple[str, bool, str]:
    """Run action for a single device. Returns (device_id, success, error_msg)."""
    from core.backend import ADBBackend
    from core.screen import set_backend, set_template_subdir

    device_id = device_config.get("serial")
    if not device_id:
        return ("<unknown>", False, "Missing 'serial' in device config")

    try:
        set_backend(ADBBackend(device_id))
        set_template_subdir("adb")

        from flows import (
            run_complete_quest,
            run_do_quest,
            run_open_inventory,
            run_open_menu_chuyen_doi,
            run_quick_sell,
            run_teleport_to_huyen_bot,
        )
        from programs import run_chuyen_doi_program

        handlers = {
            "open_inventory": run_open_inventory,
            "quick_sell": run_quick_sell,
            "complete_quest": run_complete_quest,
            "do_quest": run_do_quest,
            "teleport_to_huyen_bot": run_teleport_to_huyen_bot,
            "open_menu_chuyen_doi": run_open_menu_chuyen_doi,
            "run_chuyen_doi_program": run_chuyen_doi_program,
        }
        fn = handlers.get(action)
        if not fn:
            return (device_id, False, f"Unknown action: {action}")

        if action in ("open_menu_chuyen_doi", "run_chuyen_doi_program"):
            success = fn(threshold=threshold, stone_tags=stone_tags)
        else:
            success = fn(threshold=threshold)
        return (device_id, success, "" if success else "Action returned False")
    except Exception as e:
        return (device_id, False, str(e))


def _run_multi_device(args: argparse.Namespace) -> int:
    """Run action on multiple devices in parallel from config file."""
    try:
        devices, config_options = _load_config(args.config)
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}")
        return 1

    if not devices:
        print("[ERROR] No devices in config")
        return 1

    # Ensure ADB daemon is running before spawning parallel workers.
    # Single-device mode handles this inside get_first_adb_device(); multi-device skips that path.
    import subprocess as _sp
    _sp.run(["adb", "start-server"], capture_output=True, timeout=10)

    stone_tags = _parse_stone_tags(args.stones)
    
    loop = args.loop or config_options.get("loop", False)
    loop_interval = args.loop_interval
    if "loop_interval" in config_options:
        loop_interval = float(config_options["loop_interval"])
    threshold = args.threshold
    if "threshold" in config_options:
        threshold = float(config_options["threshold"])

    def run_once() -> int:
        print(f"[MULTI] Running '{args.action}' on {len(devices)} devices...")
        results = []
        with ThreadPoolExecutor(max_workers=len(devices)) as executor:
            futures = {
                executor.submit(_run_for_device, d, args.action, threshold, stone_tags): d
                for d in devices
            }
            for future in as_completed(futures):
                device_id, success, error = future.result()
                results.append((device_id, success, error))
                status = "OK" if success else "FAIL"
                msg = f"  [{status}] {device_id}"
                if error:
                    msg += f" - {error}"
                print(msg)

        failed = [d for d, s, e in results if not s]
        if failed:
            print(f"[MULTI] {len(failed)}/{len(devices)} device(s) failed")
            return 1
        print(f"[MULTI] All {len(devices)} device(s) succeeded")
        return 0

    if loop:
        if args.action not in ("quick_sell", "do_quest", "run_chuyen_doi_program"):
            print("[WARN] --loop works best with quick_sell, do_quest, or run_chuyen_doi_program")
        iteration = 0
        try:
            while True:
                iteration += 1
                print(f"[LOOP #{iteration}]")
                run_once()
                print(f"[LOOP] Next run in {loop_interval}s")
                time.sleep(loop_interval)
        except KeyboardInterrupt:
            print(f"\n[LOOP] Stopped after {iteration} iteration(s).")
            return 0
    else:
        return run_once()


def _parse_stone_tags(stones_arg: str | None) -> list[str] | None:
    """Parse --stones comma-separated string into list of tags."""
    if not stones_arg:
        return None
    return [s.strip() for s in stones_arg.split(",") if s.strip()]


def _create_run_fn(args: argparse.Namespace, do_run: Callable[[], bool]) -> Callable[[], bool]:
    """Create the appropriate run function based on mode and options."""
    if args.mode == "adb":
        _setup_adb_backend(args.adb_device)
        return do_run
    _setup_mac_backend(args.background_capture, args.game_app)
    if args.background_capture:
        return do_run
    return lambda: run_with_game_focus(
        args.game_app,
        do_run,
        restore=not args.no_restore_focus,
    )


def main() -> int:
    """Entry point."""
    args = parse_args()

    if args.config:
        return _run_multi_device(args)

    stone_tags = _parse_stone_tags(args.stones)

    def do_run() -> bool:
        return run_action(args.action, args.threshold, stone_tags=stone_tags)

    if args.action == "list_devices":
        success = do_run()
        return 0 if success else 1

    run_fn = _create_run_fn(args, do_run)

    if args.loop:
        if args.action not in ("quick_sell", "do_quest", "run_chuyen_doi_program"):
            print("[WARN] --loop works best with quick_sell, do_quest, or run_chuyen_doi_program")
        while True:
            run_fn()
            print(f"[LOOP] Next run in {args.loop_interval}s")
            time.sleep(args.loop_interval)
    else:
        success = run_fn()
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
