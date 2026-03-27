"""
Flow: mở túi (open bag/inventory).

Clicks the inventory button to open the bag UI.
"""

from __future__ import annotations

from core.actions import click_template_with_retry


def run_open_inventory(threshold: float = 0.75) -> bool:
    """
    Open the inventory/bag UI.

    Args:
        threshold: Template match confidence.

    Returns:
        True if inventory button was clicked, False otherwise.
    """
    return click_template_with_retry(
        template_name="inventory_button.png",
        max_retries=5,
        retry_delay=0.1,
        threshold=threshold,
    )
