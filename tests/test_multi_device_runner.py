"""Tests for core.multi_device_runner.run_multi_device_adb."""
from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest

from core.multi_device_runner import run_multi_device_adb


def test_empty_devices_returns_1():
    logs: list[str] = []

    def log(line: str) -> None:
        logs.append(line)

    rc = run_multi_device_adb(
        devices=[],
        action="quick_sell",
        threshold=0.75,
        stone_tags=None,
        loop=False,
        loop_interval=1.0,
        log=log,
        cancel_event=None,
    )
    assert rc == 1
    assert any("No devices" in x or "no devices" in x.lower() for x in logs)


def test_cancel_event_stops_loop():
    logs: list[str] = []
    cancel = threading.Event()

    def fake_run_for_device(device_config, action, threshold, stone_tags):
        return (device_config.get("serial", "?"), True, "")

    with patch("core.multi_device_runner._run_for_device", side_effect=fake_run_for_device):

        def run_in_thread():
            return run_multi_device_adb(
                devices=[{"serial": "emulator-5554"}],
                action="quick_sell",
                threshold=0.75,
                stone_tags=None,
                loop=True,
                loop_interval=10.0,
                log=lambda s: logs.append(s),
                cancel_event=cancel,
            )

        t = threading.Thread(target=run_in_thread)
        t.start()
        time.sleep(0.3)
        cancel.set()
        t.join(timeout=5.0)
        assert not t.is_alive(), "worker should exit after cancel"
