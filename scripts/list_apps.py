#!/usr/bin/env python3
"""
List running macOS apps with their display name and bundle ID.

Run this with the game open to find the exact --game-app value.

Usage:
    python scripts/list_apps.py
    python scripts/list_apps.py --filter yulang
"""

from __future__ import annotations

import argparse
import sys

try:
    from AppKit import NSWorkspace
    HAS_PYOBJC = True
except ImportError:
    HAS_PYOBJC = False


def list_apps(filter_substring: str | None = None) -> None:
    """Print running GUI apps (name, bundle ID)."""
    if not HAS_PYOBJC:
        print("Requires pyobjc: pip install pyobjc-framework-Cocoa")
        sys.exit(1)

    workspace = NSWorkspace.sharedWorkspace()
    apps = workspace.runningApplications()

    # Sort by display name
    rows: list[tuple[str, str]] = []
    for app in apps:
        if not app.isHidden() and app.activationPolicy() != -2:  # -2 = background
            name = (app.localizedName() or "").strip()
            bid = (app.bundleIdentifier() or "").strip()
            if name or bid:
                if filter_substring is None or (
                    filter_substring.lower() in name.lower()
                    or filter_substring.lower() in bid.lower()
                ):
                    rows.append((name, bid))

    rows.sort(key=lambda x: x[0].lower())

    print("Running apps (use display name or bundle ID with --game-app):\n")
    print(f"{'Display name':<40} {'Bundle ID'}")
    print("-" * 80)
    for name, bid in rows:
        print(f"{name:<40} {bid}")
    print("\nExample: python main.py --action quick_sell --game-app \"Display name\"")


def main() -> int:
    parser = argparse.ArgumentParser(description="List running apps for --game-app")
    parser.add_argument(
        "--filter",
        type=str,
        help="Only show apps whose name or bundle ID contains this (case-insensitive)",
    )
    args = parser.parse_args()
    list_apps(args.filter)
    return 0


if __name__ == "__main__":
    sys.exit(main())
