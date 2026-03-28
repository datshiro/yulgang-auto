"""Tests for gui.adb_check."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from gui.adb_check import adb_available


def test_adb_available_success():
    mock_run = MagicMock()
    mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="Android Debug Bridge")
    with patch("gui.adb_check.subprocess.run", mock_run):
        ok, msg = adb_available()
    assert ok is True
    assert msg == ""


def test_adb_available_file_not_found():
    with patch("gui.adb_check.subprocess.run", side_effect=FileNotFoundError()):
        ok, msg = adb_available()
    assert ok is False
    assert "PATH" in msg
