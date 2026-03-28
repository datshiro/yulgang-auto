"""
Screen capture and template matching for game automation.

Supports macOS (PyAutoGUI + screencapture) and ADB (BlueStacks/emulator).
Uses backend abstraction for capture and click.
"""

from __future__ import annotations

import random
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from core.backend import Backend

# Per-thread backend and template subdir — set by main.py based on --mode.
# threading.local() ensures each worker thread in multi-device execution
# has its own isolated backend; no cross-thread contamination.
_thread_local = threading.local()


def set_backend(backend: Backend) -> None:
    """Set the active capture/click backend (Mac or ADB) for this thread."""
    _thread_local.backend = backend


def set_template_subdir(subdir: str | None) -> None:
    """Set template subdir (e.g. 'adb') for mode-specific templates. None = default."""
    _thread_local.template_subdir = subdir


def set_capture_context(window_id: int | None, game_app: str | None) -> None:
    """Set context for background capture mode (creates MacBackend)."""
    from core.backend import MacBackend

    set_backend(MacBackend(window_id=window_id, game_app=game_app))


def _get_backend() -> Backend:
    """Return active backend for this thread; create default MacBackend if none set."""
    backend = getattr(_thread_local, "backend", None)
    if backend is None:
        from core.backend import MacBackend

        backend = MacBackend(window_id=None, game_app=None)
        _thread_local.backend = backend
    return backend


def _get_screenshot_bgr() -> tuple[np.ndarray, bool]:
    """
    Get screenshot as BGR. Returns (image, used_window_capture).
    When used_window_capture is True, coords are in window space.
    """
    backend = _get_backend()
    img, used_window_capture = backend.capture()
    if img is None:
        raise RuntimeError("Backend capture failed")
    return (img, used_window_capture)


def _get_project_root() -> Path:
    """Return project root (parent of core/)."""
    return Path(__file__).resolve().parent.parent


# Scale factors for multi-scale matching (handles slight resolution differences)
_MULTISCALE_FACTORS = (0.90, 0.95, 1.0, 1.05, 1.10)


def _match_template(
    screen_bgr: np.ndarray,
    template: np.ndarray,
    threshold: float,
    use_multiscale: bool = False,
    return_best_always: bool = False,
) -> tuple[float, int, int] | None:
    """
    Match template against screen. Returns (confidence, center_x, center_y) or None.

    When use_multiscale is True, tries multiple template scales for resolution tolerance.
    When return_best_always is True, returns best match even if below threshold.
    """
    th, tw = template.shape[:2]
    scales = _MULTISCALE_FACTORS if use_multiscale else (1.0,)
    best_val = 0.0
    best_center: tuple[int, int] | None = None

    for scale in scales:
        if scale <= 0:
            continue
        if use_multiscale:
            scaled = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            h, w = scaled.shape[:2]
        else:
            scaled = template
            h, w = th, tw
        if h > screen_bgr.shape[0] or w > screen_bgr.shape[1]:
            continue
        result = cv2.matchTemplate(screen_bgr, scaled, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val > best_val:
            best_val = max_val
            x, y = max_loc
            best_center = (x + w // 2, y + h // 2)

    if best_center is None:
        return None
    if return_best_always or best_val >= threshold:
        return (best_val, best_center[0], best_center[1])
    return None


def get_stone_template_names() -> list[str]:
    """Return sorted list of template names in stones/ subdir (e.g. stones/thiem_1.png)."""
    root = _get_project_root()
    base = root / "templates"
    template_subdir = getattr(_thread_local, "template_subdir", None)
    if template_subdir:
        stones_dir = base / template_subdir / "stones"
    else:
        stones_dir = base / "stones"
    if not stones_dir.is_dir():
        return []
    names = []
    for p in sorted(stones_dir.glob("*.png")):
        rel = p.relative_to(base / template_subdir if template_subdir else base)
        names.append(str(rel))
    return names


def resolve_template_path(template_name: str) -> Path:
    """Resolve template name to full path under templates/ (or templates/subdir/)."""
    root = _get_project_root()
    base = root / "templates"
    template_subdir = getattr(_thread_local, "template_subdir", None)
    if template_subdir:
        subdir_path = base / template_subdir / template_name
        if not subdir_path.suffix:
            subdir_path = subdir_path.with_suffix(".png")
        if subdir_path.exists():
            return subdir_path
    path = base / template_name
    if not path.suffix:
        path = path.with_suffix(".png")
    return path


def locate_template(
    template_path: str | Path,
    threshold: float = 0.75,
) -> tuple[float, tuple[int, int]] | None:
    """
    Find a template on screen using OpenCV matchTemplate.

    For ADB mode, falls back to multi-scale matching if single-scale fails.

    Args:
        template_path: Path to template image (PNG recommended).
        threshold: Minimum match confidence (0.0–1.0).

    Returns:
        (confidence, (center_x, center_y)) if found, else None.
        Coordinates are in screenshot/window pixel space.
    """
    path = Path(template_path)
    if not path.is_absolute():
        path = resolve_template_path(str(path))

    screen_bgr, _ = _get_screenshot_bgr()
    template = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if template is None:
        return None

    backend = _get_backend()
    use_multiscale = backend.uses_direct_coords

    match = _match_template(screen_bgr, template, threshold, use_multiscale=False)
    if match is None and use_multiscale:
        match = _match_template(screen_bgr, template, threshold, use_multiscale=True)
    if match is not None:
        return (match[0], (match[1], match[2]))
    return None


def _window_to_screen_coords(
    center_x: int,
    center_y: int,
    img_w: int,
    img_h: int,
    window_id: int | None,
) -> tuple[int, int]:
    """Convert window image coords to screen coords for click."""
    from core.window_capture import get_window_bounds

    if window_id is None:
        return (center_x, center_y)
    bounds = get_window_bounds(window_id)
    if bounds is None:
        return (center_x, center_y)
    wx, wy, ww, wh = bounds
    if img_w <= 0 or img_h <= 0:
        return (wx + center_x, wy + center_y)
    scale_x = ww / img_w
    scale_y = wh / img_h
    return (
        int(wx + center_x * scale_x),
        int(wy + center_y * scale_y),
    )


def click_if_found(
    template_path: str | Path,
    threshold: float = 0.75,
    click_delay: float = 0.05,
    offset_range: int = 3,
) -> bool:
    """
    Detect a UI element via template matching and click it.

    When using background capture, activates game only for the click.
    Clicks immediately after moving cursor to reduce chance of user moving it away.

    Args:
        template_path: Path to template image.
        threshold: Match confidence threshold.
        click_delay: Mouse move duration before click.
        offset_range: Random pixel offset range (-N to +N) to avoid detection.

    Returns:
        True if clicked, False otherwise.
    """
    path = Path(template_path)
    if not path.is_absolute():
        path = resolve_template_path(str(path))

    screen_bgr, used_window_capture = _get_screenshot_bgr()
    template = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if template is None:
        print(f"[ERROR] Could not load template: {path}")
        return False

    backend = _get_backend()
    use_multiscale = backend.uses_direct_coords
    match = _match_template(screen_bgr, template, threshold, use_multiscale=False)
    if match is None and use_multiscale:
        match = _match_template(screen_bgr, template, threshold, use_multiscale=True)

    if match is not None:
        max_val, center_x, center_y = match

        # Use no random offset for background capture to avoid misclicks
        eff_offset = 0 if used_window_capture else offset_range
        offset_x = random.randint(-eff_offset, eff_offset)
        offset_y = random.randint(-eff_offset, eff_offset)

        if used_window_capture:
            final_x, final_y = _window_to_screen_coords(
                center_x + offset_x,
                center_y + offset_y,
                screen_bgr.shape[1],
                screen_bgr.shape[0],
                backend.get_window_id(),
            )
        elif backend.uses_direct_coords:
            # ADB: screenshot coords = tap coords
            final_x = center_x + offset_x
            final_y = center_y + offset_y
        else:
            # Mac full-screen: scale for Retina
            import pyautogui

            screen_w, screen_h = pyautogui.size()
            screenshot_w, screenshot_h = screen_bgr.shape[1], screen_bgr.shape[0]
            scale_x = screen_w / screenshot_w
            scale_y = screen_h / screenshot_h
            final_x = int((center_x + offset_x) * scale_x)
            final_y = int((center_y + offset_y) * scale_y)

        backend.click(final_x, final_y, click_delay=click_delay)

        print(f"[CLICKED] {path.name} at ({final_x}, {final_y}) | confidence={max_val:.3f}")
        return True

    # Get best confidence for debug output
    best_match = _match_template(
        screen_bgr, template, threshold, use_multiscale=use_multiscale, return_best_always=True
    )
    best_val = best_match[0] if best_match else 0.0
    print(f"[MISS] {path.name} not found | confidence={best_val:.3f}")
    return False


def click_anywhere(click_delay: float = 0.05) -> bool:
    """
    Click at center of screen. Useful to dismiss popups or confirm dialogs.

    Captures screenshot to get dimensions, then clicks center with proper
    coordinate conversion for Mac/ADB/window capture.
    """
    screen_bgr, used_window_capture = _get_screenshot_bgr()
    backend = _get_backend()
    center_x = screen_bgr.shape[1] // 2
    center_y = screen_bgr.shape[0] // 2

    if used_window_capture:
        final_x, final_y = _window_to_screen_coords(
            center_x, center_y,
            screen_bgr.shape[1], screen_bgr.shape[0],
            backend.get_window_id(),
        )
    elif backend.uses_direct_coords:
        final_x, final_y = center_x, center_y
    else:
        import pyautogui
        screen_w, screen_h = pyautogui.size()
        screenshot_w, screenshot_h = screen_bgr.shape[1], screen_bgr.shape[0]
        scale_x = screen_w / screenshot_w
        scale_y = screen_h / screenshot_h
        final_x = int(center_x * scale_x)
        final_y = int(center_y * scale_y)

    backend.click(final_x, final_y, click_delay=click_delay)
    return True
