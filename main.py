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
from typing import Callable
import sys
import time

from core.config_io import load_device_config
from core.multi_device_runner import run_multi_device_adb
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
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Extra logging for multi-device (--config) runs: per-device timing, adb output.",
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


def _run_multi_device(args: argparse.Namespace) -> int:
    """Run action on multiple devices in parallel from config file."""
    try:
        devices, config_options = load_device_config(args.config)
    except Exception as e:
        print(f"[ERROR] Failed to load config: {e}")
        return 1

    if not devices:
        print("[ERROR] No devices in config")
        return 1

    stone_tags = _parse_stone_tags(args.stones)
    if stone_tags is None and isinstance(config_options.get("stones"), str):
        stone_tags = _parse_stone_tags(config_options["stones"])

    loop = args.loop or bool(config_options.get("loop", False))
    loop_interval = (
        float(config_options["loop_interval"]) if "loop_interval" in config_options else args.loop_interval
    )
    threshold = float(config_options["threshold"]) if "threshold" in config_options else args.threshold

    return run_multi_device_adb(
        devices=devices,
        action=args.action,
        threshold=threshold,
        stone_tags=stone_tags,
        loop=loop,
        loop_interval=loop_interval,
        log=print,
        cancel_event=None,
        verbose=args.verbose,
    )


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
