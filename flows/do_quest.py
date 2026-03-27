"""
Flow: làm nhiệm vụ (do quest).

Opens quest UI and starts/accepts a quest.
Uses retries instead of fixed delays: clicks as soon as each button appears.
"""

from __future__ import annotations

from core.actions import click_template_wait_for, click_template_with_retry


def run_do_quest(threshold: float = 0.75) -> bool:
    """
    Do a quest: open quest UI -> select/accept quest.

    Polls for each button and clicks immediately when found.

    Args:
        threshold: Template match confidence.

    Returns:
        True if quest was accepted/started, False otherwise.
    """
    # Step 1: Open quest UI
    if not click_template_with_retry(
        "quest_button.png",
        max_retries=5,
        retry_delay=0.1,
        threshold=threshold,
    ):
        return False

    # Step 2: Wait for accept/start button, click as soon as it appears
    return click_template_wait_for(
        "quest_accept_button.png",
        max_wait=3.0,
        poll_interval=0.1,
        threshold=threshold,
    )
