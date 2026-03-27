"""
Flow: bán đồ nhanh (quick sell items).

Sequence: open inventory -> quick sell button -> confirm -> close.
Uses retries instead of fixed delays: clicks as soon as each button appears.
"""

from __future__ import annotations

import time

from core.actions import (
    click_template_wait_for,
    click_template_with_retry,
)


def run_quick_sell(threshold: float = 0.75) -> bool:
    """
    Quick sell all items: inventory -> quick sell -> confirm -> close.

    Polls for each button and clicks immediately when found (no fixed delays).

    Args:
        threshold: Template match confidence.

    Returns:
        True if the full flow completed, False if any step failed.
    """
    # Step 1: Open inventory
    if not click_template_with_retry(
        "inventory_button.png",
        max_retries=5,
        retry_delay=0.1,
        threshold=threshold,
    ):
        return False

    time.sleep(0.1)
    # Step 2: Wait for quick sell button, click as soon as it appears
    if not click_template_with_retry(
        "quick_sell_button.png",
        max_retries=5,
        retry_delay=0.1,
        threshold=threshold,
    ):
        return False

    time.sleep(0.1)
    # Step 3: Wait for confirm button (Bán Nhanh), click immediately
    if not click_template_with_retry(
        "quick_sell_confirm_button.png",
        max_retries=5,
        retry_delay=0.1,
        threshold=threshold,
    ):
        return False

    time.sleep(0.1)
    # Step 4: Wait for close button (success banner ~6s), click when it appears
    if not click_template_with_retry(
        "close_button.png",
        max_retries=5,
        retry_delay=0.1,
        threshold=threshold,
    ):
        return False

    time.sleep(0.1)
    # Step 5: Click again to ensure the inventory is closed
    if not click_template_with_retry(
        "close_button.png",
        max_retries=5,
        retry_delay=0.1,
        threshold=threshold,
    ):
        return False

    return True
