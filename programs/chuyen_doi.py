"""
Program: chuyển đổi (run open_menu_chuyen_doi flow until it fails).

After a successful run, continues from put in 4 stones (skips menu).
On failure, double taps close button to exit.
"""

from __future__ import annotations

import time

from core.actions import click_template_with_retry
from flows.open_menu_chuyen_doi import run_open_menu_chuyen_doi


def _double_tap_close(threshold: float) -> None:
    """Double tap close button to exit on failure."""
    click_template_with_retry(
        "close_button.png",
        max_retries=3,
        retry_delay=0.05,
        threshold=threshold,
    )
    time.sleep(0.05)
    click_template_with_retry(
        "close_button.png",
        max_retries=2,
        retry_delay=0.05,
        threshold=threshold,
    )

    # click menu again to close menu
    time.sleep(0.05)
    click_template_with_retry(
        "close_menu_button.png",
        max_retries=5,
        retry_delay=0.05,
        threshold=threshold,
    )


def run_chuyen_doi_program(
    threshold: float = 0.75,
    stone_tags: list[str] | None = None,
) -> bool:
    """
    Run open_menu_chuyen_doi flow in a loop until it fails.

    After success, next run skips menu and continues from put in 4 stones.
    On failure, double taps close button before stopping.

    Args:
        threshold: Template match confidence.
        stone_tags: Optional list of stone tags (e.g. ["noi", "2", "3", "huyet"]).
            Each tag maps to stones/{tag}.png. If None, uses all templates from stones/.

    Returns:
        True if at least one iteration succeeded, False if the first run failed.
    """
    run_count = 0
    skip_menu = False
    while True:
        run_count += 1
        print(
            f"[PROGRAM] Run #{run_count}"
            + (" (resume from stones)" if skip_menu else "")
        )
        if not run_open_menu_chuyen_doi(
            threshold=threshold,
            skip_menu=skip_menu,
            stone_tags=stone_tags,
        ):
            print("[PROGRAM] Failed. Double tapping close...")
            _double_tap_close(threshold)
            print(f"[PROGRAM] Stopped after {run_count - 1} successful run(s)")
            return run_count > 1
        skip_menu = True
