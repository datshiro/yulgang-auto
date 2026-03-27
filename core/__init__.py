"""Core module for Mac game automation: screen capture and template matching."""

from core.screen import click_if_found, locate_template
from core.actions import (
    click_template,
    click_template_wait_for,
    click_template_with_retry,
    wait_for_template_visible,
)

__all__ = [
    "click_if_found",
    "locate_template",
    "click_template",
    "click_template_wait_for",
    "click_template_with_retry",
    "wait_for_template_visible",
]
