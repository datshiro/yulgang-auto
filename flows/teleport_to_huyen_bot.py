"""
Flow: teleport to Huyen Bot (Huyền Bột).

Opens inventory, selects the Huyen Bot teleport item, verifies the correct
item is shown, then clicks Use to teleport.
"""

from __future__ import annotations

from core.actions import (
    click_template_wait_for,
    click_template_with_retry,
    wait_for_template_visible,
)


def run_teleport_to_huyen_bot(threshold: float = 0.75) -> bool:
    """
    Teleport to Huyen Bot: inventory -> select item -> verify -> use.

    Args:
        threshold: Template match confidence.

    Returns:
        True if teleport was triggered, False if any step failed.
    """
    # Step 1: Open inventory
    if not click_template_with_retry(
        "inventory_button.png",
        max_retries=5,
        retry_delay=0.05,
        threshold=threshold,
    ):
        return False

    # Step 2: Click the Huyen Bot teleport item
    if not click_template_wait_for(
        "huyen_bot_teleport_item.png",
        max_wait=3.0,
        poll_interval=0.05,
        threshold=threshold,
    ):
        return False

    # Step 3: Verify correct item selected (Hồi Thành Phù Huyền Bột Phái text)
    if not wait_for_template_visible(
        "huyen_bot_teleport_text.png",
        max_wait=2.0,
        poll_interval=0.05,
        threshold=threshold,
    ):
        print("[WARN] Huyen Bot teleport text not found; wrong item may be selected")
        return False

    # Step 4: Click Use button
    if not click_template_wait_for(
        "use_item_button.png",
        max_wait=2.0,
        poll_interval=0.05,
        threshold=threshold,
    ):
        return False

    # Step 5: Close inventory
    click_template_wait_for(
        "close_button.png",
        max_wait=3.0,
        poll_interval=0.1,
        threshold=threshold,
    )
    return True
