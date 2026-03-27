"""
Flow: mở menu, chuyển đổi, đặt 4 đá, tái tạo.

Sequence: menu -> chuyển đổi -> wait 4s -> pick 4 stones (each: stone -> put_in) -> tái tạo -> auto close.
When skip_menu=True, starts from put in 4 stones (assumes already in chuyển đổi screen).
"""

from __future__ import annotations

import time

from core.actions import click_template_wait_for, click_template_with_retry
from core.screen import get_stone_template_names


def run_open_menu_chuyen_doi(
    threshold: float = 0.75,
    skip_menu: bool = False,
    stone_tags: list[str] | None = None,
) -> bool:
    """
    Open menu, chuyển đổi, put in 4 stones, then click tái tạo and close.

    When skip_menu=True, skips menu/chuyển đổi and starts from put in 4 stones.

    Args:
        threshold: Template match confidence.
        skip_menu: If True, skip opening menu (resume from stones step).
        stone_tags: Optional list of stone tags (e.g. ["noi", "2", "3", "huyet"]).
            Each tag maps to stones/{tag}.png. If None, uses all templates from stones/.

    Returns:
        True if full flow completed, False otherwise.
    """
    if not skip_menu:
        # Step 1: Open menu
        if not click_template_with_retry(
            "menu_button.png",
            max_retries=5,
            retry_delay=0.05,
            threshold=threshold,
        ):
            return False

        time.sleep(0.05)
        # Step 2: Click chuyển đổi
        if not click_template_wait_for(
            "chuyen_doi_button.png",
            max_wait=3.0,
            poll_interval=0.05,
            threshold=threshold,
        ):
            return False

        time.sleep(3.0)

    # Step 3: Put in 4 stones (pick stone -> put_in popup -> click put_in)
    if stone_tags:
        stone_names = [f"stones/{tag}" for tag in stone_tags]
    else:
        stone_names = get_stone_template_names()
    if not stone_names:
        print("[ERROR] No stone templates in templates/adb/stones/")
        return False

    for i in range(4):
        stone = stone_names[i % len(stone_names)]
        if not click_template_with_retry(
            stone,
            max_retries=5,
            retry_delay=0.05,
            threshold=threshold,
        ):
            print(f"[ERROR] Stone {i + 1}/4: could not find {stone}")
            return False
        if not click_template_wait_for(
            "put_in_button.png",
            max_wait=3.0,
            poll_interval=0.05,
            threshold=threshold,
        ):
            print(f"[ERROR] Stone {i + 1}/4: put_in popup not found")
            return False
        time.sleep(0.05)

    # Step 4: Click tái tạo
    if not click_template_with_retry(
        "tai_tao_button.png",
        max_retries=5,
        retry_delay=0.05,
        threshold=threshold,
    ):
        return False

    time.sleep(4)
    return True
    # # Step 5: Click auto close button to dismiss popup
    # return click_template_with_retry(
    #     "auto_close_button.png",
    #     max_retries=5,
    #     retry_delay=0.05,
    #     threshold=threshold,
    # )
