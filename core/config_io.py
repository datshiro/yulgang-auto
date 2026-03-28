"""Load and save multi-device JSON/YAML config (same schema as main --config)."""

from __future__ import annotations

import json
from pathlib import Path

try:
    import yaml

    _YAML = True
except ImportError:
    _YAML = False


def load_device_config(config_path: str) -> tuple[list[dict], dict]:
    """Load device config from JSON or YAML. Returns (devices, global_options)."""
    path = Path(config_path)
    content = path.read_text(encoding="utf-8")

    if path.suffix.lower() in (".yaml", ".yml"):
        if not _YAML:
            raise ImportError("PyYAML not installed. Install with: pip install pyyaml")
        data = yaml.safe_load(content)
    else:
        data = json.loads(content)

    if isinstance(data, dict):
        devices = data.get("devices", [])
        options = {k: v for k, v in data.items() if k != "devices"}
    elif isinstance(data, list):
        devices = data
        options = {}
    else:
        raise ValueError("Config must contain 'devices' list or be a list of devices")
    return devices, options


def dump_device_config(config_path: str, data: dict) -> None:
    """Write config dict to JSON (default) or YAML if path ends with .yaml/.yml and PyYAML is available."""
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.suffix.lower() in (".yaml", ".yml"):
        if not _YAML:
            raise ImportError("PyYAML not installed. Install with: pip install pyyaml")
        path.write_text(yaml.safe_dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")
    else:
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
