"""Test that set_backend / _get_backend are thread-isolated."""
import threading
from unittest.mock import MagicMock

import pytest


def test_backends_are_thread_isolated():
    """Two threads must not share backends set via set_backend()."""
    import core.screen as screen

    results = {}

    backend_a = MagicMock(name="BackendA")
    backend_b = MagicMock(name="BackendB")

    barrier = threading.Barrier(2)

    def run_thread(name, backend):
        screen.set_backend(backend)
        barrier.wait()  # Both threads set their backend before either reads
        got = screen._get_backend()
        results[name] = got

    t1 = threading.Thread(target=run_thread, args=("a", backend_a))
    t2 = threading.Thread(target=run_thread, args=("b", backend_b))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results["a"] is backend_a, "Thread A must see its own backend"
    assert results["b"] is backend_b, "Thread B must see its own backend"


def test_template_subdir_is_thread_isolated():
    """set_template_subdir must not bleed across threads."""
    import core.screen as screen

    results = {}
    barrier = threading.Barrier(2)

    def run_thread(name, subdir):
        screen.set_template_subdir(subdir)
        barrier.wait()
        got = getattr(screen._thread_local, "template_subdir", None)
        results[name] = got

    t1 = threading.Thread(target=run_thread, args=("a", "adb"))
    t2 = threading.Thread(target=run_thread, args=("b", None))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results["a"] == "adb"
    assert results["b"] is None
