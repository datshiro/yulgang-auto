"""
Flow: hoàn thành nhiệm vụ (complete quest).

Clicks the complete/claim button in the quest UI.
"""

from __future__ import annotations

from core.actions import click_template_with_retry


def run_complete_quest(threshold: float = 0.75) -> bool:
    """
    Complete the current quest (claim rewards).

    Assumes quest UI is already open. Clicks the complete/claim button.

    Args:
        threshold: Template match confidence.

    Returns:
        True if complete button was clicked, False otherwise.
    """
    return click_template_with_retry(
        template_name="quest_complete_button.png",
        max_retries=15,
        retry_delay=0.1,
        threshold=threshold,
    )
