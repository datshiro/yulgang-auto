"""Tests for core.config_io."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from core.config_io import dump_device_config, load_device_config


def test_load_dump_roundtrip_dict_with_devices():
    data = {
        "threshold": 0.8,
        "loop": True,
        "loop_interval": 5,
        "devices": [{"serial": "emulator-5554"}, {"serial": "emulator-5564"}],
    }
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "cfg.json"
        dump_device_config(str(p), data)
        devices, options = load_device_config(str(p))
        assert len(devices) == 2
        assert devices[0]["serial"] == "emulator-5554"
        assert options.get("threshold") == 0.8
        assert options.get("loop") is True


def test_load_top_level_list():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "list.json"
        p.write_text(json.dumps([{"serial": "a"}], indent=2), encoding="utf-8")
        devices, options = load_device_config(str(p))
        assert devices == [{"serial": "a"}]
        assert options == {}


def test_load_invalid_structure_raises():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "bad.json"
        p.write_text(json.dumps(123), encoding="utf-8")
        with pytest.raises(ValueError, match="devices"):
            load_device_config(str(p))
