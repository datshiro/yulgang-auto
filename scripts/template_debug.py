#!/usr/bin/env python3
"""
Debug template matching: capture screen, test templates, report confidence.

Helps diagnose why templates have low match accuracy. Run with ADB device
connected and game visible.

Usage:
    python scripts/template_debug.py inventory_button.png
    python scripts/template_debug.py quick_sell_button.png --device emulator-5554
    python scripts/template_debug.py close_button.png -o debug_output.png
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np


def get_first_adb_device() -> str | None:
    """Return the first connected ADB device ID."""
    try:
        result = subprocess.run(
            ["adb", "devices"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.strip().splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                return parts[0]
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def capture_adb_screen(device: str, method: str = "exec-out") -> np.ndarray | None:
    """Capture raw screenshot from ADB device."""
    try:
        if method == "pull":
            import tempfile
            remote = "/sdcard/screencap_yulang.png"
            r1 = subprocess.run(
                ["adb", "-s", device, "shell", "screencap", "-p", remote],
                capture_output=True,
                timeout=15,
            )
            if r1.returncode != 0:
                print(f"[ERROR] adb shell screencap failed: {r1.stderr.decode(errors='replace')}")
                return None
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                tmp = f.name
            r2 = subprocess.run(
                ["adb", "-s", device, "pull", remote, tmp],
                capture_output=True,
                timeout=10,
            )
            subprocess.run(["adb", "-s", device, "shell", "rm", "-f", remote], capture_output=True)
            if r2.returncode != 0:
                print("[ERROR] adb pull failed")
                return None
            img = cv2.imread(tmp)
            Path(tmp).unlink(missing_ok=True)
            return img

        result = subprocess.run(
            ["adb", "-s", device, "exec-out", "screencap", "-p"],
            capture_output=True,
            timeout=15,
        )
        if result.returncode != 0:
            print(f"[ERROR] adb exec-out failed (code={result.returncode})")
            if result.stderr:
                print("  stderr:", result.stderr.decode(errors="replace")[:200])
            return None
        raw = result.stdout.replace(b"\r\n", b"\n").replace(b"\r", b"")
        if len(raw) < 100:
            print(f"[ERROR] Screencap output too small ({len(raw)} bytes)")
            return None
        nparr = np.frombuffer(raw, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            print("[ERROR] Failed to decode PNG. Try: --method pull")
            return None
        return img
    except FileNotFoundError:
        print("[ERROR] adb not found. Install: brew install android-platform-tools")
        return None
    except subprocess.TimeoutExpired:
        print("[ERROR] adb timed out. Try: --method pull")
        return None


def resolve_template(template_name: str, subdir: str | None = "adb") -> Path:
    """Resolve template path, checking adb subdir first."""
    root = Path(__file__).resolve().parent.parent
    base = root / "templates"
    if subdir:
        p = base / subdir / template_name
        if not p.suffix:
            p = p.with_suffix(".png")
        if p.exists():
            return p
    p = base / template_name
    if not p.suffix:
        p = p.with_suffix(".png")
    return p


def match_at_scale(screen: np.ndarray, template: np.ndarray, scale: float) -> tuple[float, tuple[int, int, int, int]]:
    """Match template at given scale. Returns (confidence, (x, y, w, h))."""
    if scale <= 0 or abs(scale - 1.0) < 0.001:
        scaled = template
    else:
        scaled = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    h, w = scaled.shape[:2]
    if h > screen.shape[0] or w > screen.shape[1]:
        return (0.0, (0, 0, 0, 0))
    result = cv2.matchTemplate(screen, scaled, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    x, y = max_loc
    return (float(max_val), (x, y, w, h))


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug template matching on ADB screen")
    parser.add_argument("template", help="Template name (e.g. inventory_button.png)")
    parser.add_argument("--device", default=None, help="ADB device ID")
    parser.add_argument("-o", "--output", default=None, help="Save debug image with match highlighted")
    parser.add_argument("--threshold", type=float, default=0.75, help="Match threshold")
    parser.add_argument("--no-adb-subdir", action="store_true", help="Skip templates/adb subdir")
    parser.add_argument(
        "--method",
        choices=["exec-out", "pull"],
        default="exec-out",
        help="Capture method. Use 'pull' if exec-out fails (BlueStacks).",
    )
    args = parser.parse_args()

    device = args.device or get_first_adb_device()
    if not device:
        print("[ERROR] No ADB device. Run 'adb devices' and enable BlueStacks ADB.")
        return 1

    print("\n[INFO] Capturing screen from", device, "...")
    screen = capture_adb_screen(device, method=args.method)
    if screen is None:
        print("[ERROR] Failed to capture screen")
        return 1
    print(f"[INFO] Screen size: {screen.shape[1]}x{screen.shape[0]}")

    subdir = None if args.no_adb_subdir else "adb"
    path = resolve_template(args.template, subdir)
    if not path.exists():
        print(f"[ERROR] Template not found: {path}")
        return 1

    template = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if template is None:
        print(f"[ERROR] Could not load template: {path}")
        return 1
    print(f"[INFO] Template: {path.name} ({template.shape[1]}x{template.shape[0]})")

    scales = (0.85, 0.90, 0.95, 1.0, 1.05, 1.10, 1.15)
    best_val = 0.0
    best_scale = 0.0
    best_rect = (0, 0, 0, 0)

    print("\n--- Confidence by scale ---")
    for scale in scales:
        val, rect = match_at_scale(screen, template, scale)
        x, y, w, h = rect
        status = "OK" if val >= args.threshold else "LOW"
        print(f"  scale={scale:.2f}: {val:.3f} {status}  (center: {x + w//2}, {y + h//2})")
        if val > best_val:
            best_val = val
            best_scale = scale
            best_rect = rect

    print("\n--- Best match ---")
    print(f"  confidence: {best_val:.3f}")
    print(f"  best scale: {best_scale:.2f}")
    x, y, w, h = best_rect
    print(f"  center: ({x + w//2}, {y + h//2})")
    print(f"  passes threshold ({args.threshold}): {'yes' if best_val >= args.threshold else 'no'}")

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        debug = screen.copy()
        cv2.rectangle(debug, (x, y), (x + w, y + h), (0, 255, 0), 2)
        cv2.putText(
            debug,
            f"{best_val:.2f} @ {best_scale:.2f}x",
            (x, y - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2,
        )
        cv2.imwrite(str(out_path), debug)
        print("\n[OK] Saved debug image to", out_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
