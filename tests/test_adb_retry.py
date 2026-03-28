"""Test ADB command retry logic in ADBBackend."""
import subprocess
from unittest.mock import MagicMock, call, patch

import numpy as np
import pytest

from core.backend import ADBBackend, _ADB_CMD_RETRIES, _ADB_RETRY_DELAY, _ping_device


class TestPingDevice:
    def test_runs_get_state(self):
        """_ping_device runs 'adb -s <device> get-state'."""
        with patch("core.backend.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _ping_device("emulator-5554")
            mock_run.assert_called_once_with(
                ["adb", "-s", "emulator-5554", "get-state"],
                capture_output=True,
                timeout=3,
            )

    def test_ignores_failure(self):
        """_ping_device does not raise even if adb fails."""
        with patch("core.backend.subprocess.run", side_effect=subprocess.TimeoutExpired("adb", 3)):
            _ping_device("emulator-5554")  # must not raise

    def test_ignores_file_not_found(self):
        """_ping_device does not raise when adb is not on PATH."""
        with patch("core.backend.subprocess.run", side_effect=FileNotFoundError):
            _ping_device("emulator-5554")  # must not raise


class TestCaptureExecOutRetry:
    def _make_valid_png(self) -> bytes:
        """Return a minimal valid PNG bytes that OpenCV can decode (>= 100 bytes)."""
        import cv2, numpy as np
        img = np.zeros((20, 20, 3), dtype=np.uint8)
        ok, buf = cv2.imencode(".png", img)
        assert ok
        return buf.tobytes()

    def test_succeeds_on_first_try(self):
        """Returns image immediately if first exec-out succeeds."""
        backend = ADBBackend("emulator-5554")
        valid_png = self._make_valid_png()

        with patch("core.backend.subprocess.run") as mock_run, \
             patch("core.backend._ping_device") as mock_ping:
            mock_run.return_value = MagicMock(returncode=0, stdout=valid_png)
            result = backend._capture_exec_out()

        assert result is not None
        mock_ping.assert_not_called()

    def test_retries_on_empty_output(self):
        """Retries when exec-out returns too-short output, eventually succeeds."""
        backend = ADBBackend("emulator-5554")
        valid_png = self._make_valid_png()

        fail = MagicMock(returncode=0, stdout=b"short")
        success = MagicMock(returncode=0, stdout=valid_png)

        with patch("core.backend.subprocess.run") as mock_run, \
             patch("core.backend._ping_device") as mock_ping, \
             patch("core.backend.time.sleep"):
            mock_run.side_effect = [fail] * (_ADB_CMD_RETRIES - 1) + [success]
            result = backend._capture_exec_out()

        assert result is not None
        assert mock_ping.call_count == _ADB_CMD_RETRIES - 1

    def test_returns_none_after_all_retries_exhausted(self):
        """Returns None when all retries fail."""
        backend = ADBBackend("emulator-5554")

        fail = MagicMock(returncode=1, stdout=b"")

        with patch("core.backend.subprocess.run") as mock_run, \
             patch("core.backend._ping_device"), \
             patch("core.backend.time.sleep"):
            mock_run.return_value = fail
            result = backend._capture_exec_out()

        assert result is None
        assert mock_run.call_count == _ADB_CMD_RETRIES


class TestCaptureFallback:
    def test_falls_through_to_capture_pull_on_exhaustion(self):
        """capture() calls _capture_pull when _capture_exec_out exhausts retries."""
        import numpy as np
        backend = ADBBackend("emulator-5554")
        dummy_img = np.zeros((10, 10, 3), dtype=np.uint8)

        with patch.object(backend, "_capture_exec_out", return_value=None) as mock_exec, \
             patch.object(backend, "_capture_pull", return_value=dummy_img) as mock_pull:
            img, used_window = backend.capture()

        mock_exec.assert_called_once()
        mock_pull.assert_called_once()
        assert img is dummy_img
        assert used_window is False


class TestClickRetry:
    def test_succeeds_on_first_try(self):
        """Returns True immediately if first tap succeeds."""
        backend = ADBBackend("emulator-5554")

        with patch("core.backend.subprocess.run") as mock_run, \
             patch("core.backend._ping_device") as mock_ping, \
             patch("core.backend.time.sleep"):
            mock_run.return_value = MagicMock(returncode=0)
            result = backend.click(100, 200)

        assert result is True
        mock_ping.assert_not_called()

    def test_retries_on_nonzero_exit(self):
        """Retries when tap returns non-zero exit, eventually succeeds."""
        backend = ADBBackend("emulator-5554")

        fail = MagicMock(returncode=1)
        success = MagicMock(returncode=0)

        with patch("core.backend.subprocess.run") as mock_run, \
             patch("core.backend._ping_device") as mock_ping, \
             patch("core.backend.time.sleep"):
            mock_run.side_effect = [fail, success]
            result = backend.click(100, 200)

        assert result is True
        assert mock_ping.call_count == 1

    def test_returns_false_after_all_retries_exhausted(self):
        """Returns False when all tap retries fail."""
        backend = ADBBackend("emulator-5554")

        fail = MagicMock(returncode=1)

        with patch("core.backend.subprocess.run") as mock_run, \
             patch("core.backend._ping_device"), \
             patch("core.backend.time.sleep"):
            mock_run.return_value = fail
            result = backend.click(100, 200)

        assert result is False
        assert mock_run.call_count == _ADB_CMD_RETRIES

    def test_no_sleep_when_click_delay_zero(self):
        """click() does not sleep when click_delay=0."""
        backend = ADBBackend("emulator-5554")

        with patch("core.backend.subprocess.run") as mock_run, \
             patch("core.backend.time.sleep") as mock_sleep:
            mock_run.return_value = MagicMock(returncode=0)
            result = backend.click(100, 200, click_delay=0)

        assert result is True
        mock_sleep.assert_not_called()
