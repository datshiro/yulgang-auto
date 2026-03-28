"""python -m gui — launch ADB desktop UI."""

from __future__ import annotations

import sys


def _main() -> None:
    try:
        from gui.mainwindow import main as run_gui
    except ModuleNotFoundError as e:
        # Homebrew python@3.x ships without _tkinter unless python-tk@3.x is installed.
        if getattr(e, "name", None) == "_tkinter" or "_tkinter" in str(e):
            print(
                "This Python build has no Tk/Tcl bindings (missing module '_tkinter').\n\n"
                "On macOS with Homebrew Python 3.13, install:\n"
                "  brew install python-tk@3.13\n\n"
                "Use the same major.minor as `python3 --version` (e.g. python-tk@3.12 for 3.12).\n"
                "Then verify:  python3 -c \"import tkinter\"\n\n"
                "Alternatively install Python from https://www.python.org/downloads/ (includes tkinter).\n",
                file=sys.stderr,
            )
            raise SystemExit(1) from e
        raise
    run_gui()


if __name__ == "__main__":
    _main()
