"""
Click helpers with retries and configurable thresholds.

Wraps screen.click_if_found with optional retries. Uses polling instead of
fixed delays: retry until the button appears, then click immediately.
"""

from __future__ import annotations

import time

from core.screen import click_if_found, locate_template

# Short poll interval for "wait for button to appear" (clicks as soon as found)
# 0.05s balances latency vs capture load; lower values stress ADB/CPU with little gain
DEFAULT_POLL_INTERVAL = 0.05
# Max wait for normal UI transitions
DEFAULT_MAX_WAIT_NORMAL = 3.0


def click_template(
    template_name: str,
    threshold: float = 0.75,
    click_delay: float = 0.05,
) -> bool:
    """
    Click a template by name (resolved under templates/).

    Args:
        template_name: Template filename, e.g. "inventory_button.png".
        threshold: Match confidence threshold.
        click_delay: Mouse move duration before click.

    Returns:
        True if clicked, False otherwise.
    """
    return click_if_found(
        template_path=template_name,
        threshold=threshold,
        click_delay=click_delay,
    )


def click_template_with_retry(
    template_name: str,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    threshold: float = 0.75,
) -> bool:
    """
    Click a template with retries. Polls until button appears, then clicks immediately.

    Args:
        template_name: Template filename.
        max_retries: Number of attempts.
        retry_delay: Seconds between retries (use small value e.g. 0.2 for fast polling).
        threshold: Match confidence threshold.

    Returns:
        True if clicked on any attempt, False otherwise.
    """
    for attempt in range(max_retries):
        if click_template(template_name, threshold=threshold):
            return True
        if attempt < max_retries - 1:
            time.sleep(retry_delay)
    return False


def click_template_wait_for(
    template_name: str,
    max_wait: float = DEFAULT_MAX_WAIT_NORMAL,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    threshold: float = 0.75,
) -> bool:
    """
    Poll until the button appears, then click immediately. No fixed delay.

    Use instead of time.sleep + click when the next UI element may appear
    sooner than a fixed wait.

    Args:
        template_name: Template filename.
        max_wait: Max seconds to wait before giving up.
        poll_interval: Seconds between each attempt.
        threshold: Match confidence threshold.

    Returns:
        True if clicked, False if not found within max_wait.
    """
    max_retries = max(1, int(max_wait / poll_interval))
    return click_template_with_retry(
        template_name=template_name,
        max_retries=max_retries,
        retry_delay=poll_interval,
        threshold=threshold,
    )


def wait_for_template_visible(
    template_name: str,
    max_wait: float = DEFAULT_MAX_WAIT_NORMAL,
    poll_interval: float = DEFAULT_POLL_INTERVAL,
    threshold: float = 0.75,
) -> bool:
    """
    Poll until the template is visible on screen (no click).

    Use to verify that the correct UI element is shown before proceeding.

    Args:
        template_name: Template filename.
        max_wait: Max seconds to wait before giving up.
        poll_interval: Seconds between each attempt.
        threshold: Match confidence threshold.

    Returns:
        True if template found within max_wait, False otherwise.
    """
    max_retries = max(1, int(max_wait / poll_interval))
    for _ in range(max_retries):
        if locate_template(template_name, threshold=threshold) is not None:
            return True
        time.sleep(poll_interval)
    return False
