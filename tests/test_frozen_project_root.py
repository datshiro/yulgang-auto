"""Frozen (PyInstaller) bundle path resolution for templates."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch


def test_get_project_root_uses_meipass_when_frozen() -> None:
    import core.screen as screen

    fake = "/tmp/pyinstaller_meipass_fixture"
    with patch.object(sys, "frozen", True, create=True):
        with patch.object(sys, "_MEIPASS", fake, create=True):
            root = screen._get_project_root()
    assert root == Path(fake)


def test_get_project_root_falls_back_when_meipass_missing() -> None:
    import core.screen as screen

    with patch.object(sys, "frozen", True, create=True):
        with patch.object(sys, "_MEIPASS", None, create=True):
            root = screen._get_project_root()
    expected = Path(screen.__file__).resolve().parent.parent
    assert root == expected


def test_get_project_root_dev_tree_when_not_frozen() -> None:
    import core.screen as screen

    with patch.object(sys, "frozen", False, create=True):
        root = screen._get_project_root()
    expected = Path(screen.__file__).resolve().parent.parent
    assert root == expected
