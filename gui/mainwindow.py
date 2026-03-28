"""tkinter main window: ADB devices, run options, import/export, worker + log."""

from __future__ import annotations

import contextlib
import io
import queue
import threading
import tkinter as tk
from collections.abc import Callable
from tkinter import filedialog, messagebox, ttk, scrolledtext

from core.backend import get_adb_devices
from core.config_io import dump_device_config, load_device_config
from core.multi_device_runner import run_multi_device_adb

from gui.adb_check import adb_available

ACTIONS = [
    "open_inventory",
    "quick_sell",
    "complete_quest",
    "do_quest",
    "teleport_to_huyen_bot",
    "open_menu_chuyen_doi",
    "run_chuyen_doi_program",
]


def _parse_stone_tags(stones_arg: str) -> list[str] | None:
    if not stones_arg or not stones_arg.strip():
        return None
    return [s.strip() for s in stones_arg.split(",") if s.strip()]


class _LineQueueLogStream(io.TextIOBase):
    """Send each printed line to the GUI log (used with redirect_stdout/stderr)."""

    encoding = "utf-8"

    def __init__(self, emit_line: Callable[[str], None]) -> None:
        super().__init__()
        self._emit = emit_line
        self._buffer = ""

    def write(self, s: str) -> int:  # type: ignore[override]
        if not s:
            return 0
        self._buffer += str(s)
        while True:
            idx = self._buffer.find("\n")
            if idx < 0:
                break
            line = self._buffer[:idx].rstrip("\r")
            self._buffer = self._buffer[idx + 1 :]
            if line:
                self._emit(line)
        return len(s)

    def flush(self) -> None:
        if self._buffer.strip():
            self._emit(self._buffer.rstrip("\r\n"))
        self._buffer = ""
        super().flush()


class _DeviceRow:
    __slots__ = ("frame", "include", "serial", "status_label", "remove_btn")

    def __init__(
        self,
        parent: ttk.Frame,
        on_remove: object,
        *,
        serial: str = "",
        status: str = "",
        checked: bool = True,
    ) -> None:
        self.frame = ttk.Frame(parent)
        self.include = tk.BooleanVar(value=checked)
        ttk.Checkbutton(self.frame, variable=self.include).pack(side=tk.LEFT, padx=(0, 4))
        self.serial = tk.StringVar(value=serial)
        ttk.Entry(self.frame, textvariable=self.serial, width=28).pack(side=tk.LEFT, padx=(0, 4))
        self.status_label = ttk.Label(self.frame, text=status or "—", width=14)
        self.status_label.pack(side=tk.LEFT, padx=(0, 4))
        self.remove_btn = ttk.Button(self.frame, text="×", width=2, command=lambda: on_remove(self))
        self.remove_btn.pack(side=tk.LEFT)

    def pack(self, **kw: object) -> None:
        self.frame.pack(fill=tk.X, pady=2, **kw)

    def destroy(self) -> None:
        self.frame.destroy()


class YulangAdbApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Yulang ADB")
        self.geometry("720x640")
        self.minsize(560, 480)

        self._device_rows: list[_DeviceRow] = []
        self._log_queue: queue.Queue[tuple[str, str | int | None]] = queue.Queue()
        self._worker: threading.Thread | None = None
        self._cancel = threading.Event()

        self._build_adb_banner()
        self._build_devices_section()
        self._build_options_section()
        self._build_actions_section()
        self._build_log_section()

        self._drain_log_queue()
        self._check_adb_on_start()

    def _build_adb_banner(self) -> None:
        self._adb_banner = ttk.Label(self, text="", foreground="darkred", wraplength=680)
        self._adb_banner.pack(fill=tk.X, padx=8, pady=(8, 0))

    def _build_devices_section(self) -> None:
        lf = ttk.LabelFrame(self, text="Devices")
        lf.pack(fill=tk.BOTH, expand=False, padx=8, pady=8)
        self._device_list_host = ttk.Frame(lf)
        self._device_list_host.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        btns = ttk.Frame(lf)
        btns.pack(fill=tk.X, padx=4, pady=4)
        ttk.Button(btns, text="Refresh from ADB", command=self._refresh_devices).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Add row", command=self._add_device_row).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Import config…", command=self._import_config).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Export config…", command=self._export_config).pack(side=tk.LEFT, padx=2)

    def _build_options_section(self) -> None:
        lf = ttk.LabelFrame(self, text="Run options")
        lf.pack(fill=tk.X, padx=8, pady=4)
        row = ttk.Frame(lf)
        row.pack(fill=tk.X, padx=4, pady=4)
        ttk.Label(row, text="Threshold").pack(side=tk.LEFT)
        self._threshold = tk.DoubleVar(value=0.75)
        ttk.Spinbox(row, from_=0.1, to=1.0, increment=0.05, textvariable=self._threshold, width=6).pack(
            side=tk.LEFT, padx=(4, 16)
        )
        ttk.Label(row, text="Stones (comma-separated)").pack(side=tk.LEFT)
        self._stones = tk.StringVar(value="")
        ttk.Entry(row, textvariable=self._stones, width=28).pack(side=tk.LEFT, padx=4)
        row2 = ttk.Frame(lf)
        row2.pack(fill=tk.X, padx=4, pady=4)
        self._loop = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2, text="Loop", variable=self._loop).pack(side=tk.LEFT)
        ttk.Label(row2, text="Interval (s)").pack(side=tk.LEFT, padx=(12, 0))
        self._loop_interval = tk.DoubleVar(value=10.0)
        ttk.Spinbox(row2, from_=1.0, to=3600.0, increment=1.0, textvariable=self._loop_interval, width=8).pack(
            side=tk.LEFT, padx=4
        )
        self._verbose_log = tk.BooleanVar(value=True)
        ttk.Checkbutton(row2, text="Verbose log", variable=self._verbose_log).pack(side=tk.LEFT, padx=(24, 0))

    def _build_actions_section(self) -> None:
        lf = ttk.Frame(self)
        lf.pack(fill=tk.X, padx=8, pady=4)
        ttk.Label(lf, text="Action").pack(side=tk.LEFT)
        self._action = tk.StringVar(value=ACTIONS[1])
        ttk.Combobox(lf, textvariable=self._action, values=ACTIONS, state="readonly", width=28).pack(
            side=tk.LEFT, padx=4
        )
        self._run_btn = ttk.Button(lf, text="Run", command=self._on_run)
        self._run_btn.pack(side=tk.LEFT, padx=8)
        self._stop_btn = ttk.Button(lf, text="Stop", command=self._on_stop, state=tk.DISABLED)
        self._stop_btn.pack(side=tk.LEFT, padx=2)

    def _build_log_section(self) -> None:
        lf = ttk.LabelFrame(self, text="Log")
        lf.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self._log = scrolledtext.ScrolledText(lf, height=14, state=tk.DISABLED, wrap=tk.WORD)
        self._log.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

    def _check_adb_on_start(self) -> None:
        ok, err = adb_available()
        if not ok:
            self._adb_banner.config(text=err)

    def _append_log(self, line: str) -> None:
        self._log.config(state=tk.NORMAL)
        self._log.insert(tk.END, line + "\n")
        self._log.see(tk.END)
        self._log.config(state=tk.DISABLED)

    def _drain_log_queue(self) -> None:
        try:
            while True:
                kind, payload = self._log_queue.get_nowait()
                if kind == "log":
                    assert isinstance(payload, str)
                    self._append_log(payload)
                elif kind == "done":
                    self._run_btn.config(state=tk.NORMAL)
                    self._stop_btn.config(state=tk.DISABLED)
                    self._worker = None
                    self._cancel = threading.Event()
                    if payload is not None:
                        self._append_log(f"[GUI] Finished (exit code {payload})")
        except queue.Empty:
            pass
        self.after(120, self._drain_log_queue)

    def _remove_row(self, row: _DeviceRow) -> None:
        if row not in self._device_rows:
            return
        self._device_rows.remove(row)
        row.destroy()

    def _add_device_row(self, serial: str = "", status: str = "", checked: bool = True) -> _DeviceRow:
        row = _DeviceRow(
            self._device_list_host,
            self._remove_row,
            serial=serial,
            status=status,
            checked=checked,
        )
        row.pack()
        self._device_rows.append(row)
        return row

    def _clear_device_rows(self) -> None:
        for row in list(self._device_rows):
            row.destroy()
        self._device_rows.clear()

    def _refresh_devices(self) -> None:
        ok, err = adb_available()
        if not ok:
            self._adb_banner.config(text=err)
            messagebox.showerror("ADB", err)
            return
        self._adb_banner.config(text="")

        found = get_adb_devices()
        by_serial = {s: st for s, st in found}

        for row in self._device_rows:
            s = row.serial.get().strip()
            if s in by_serial:
                row.status_label.config(text=by_serial[s])

        existing = {r.serial.get().strip() for r in self._device_rows if r.serial.get().strip()}
        for serial, status in found:
            if serial not in existing:
                self._add_device_row(serial=serial, status=status, checked=True)
                existing.add(serial)

        if not found:
            self._append_log("No ADB devices in 'device' state. Is BlueStacks running with ADB enabled?")
            self._append_log("Try: adb kill-server && adb start-server && adb devices")

    def _import_config(self) -> None:
        path = filedialog.askopenfilename(
            title="Import device config",
            filetypes=[("JSON", "*.json"), ("YAML", "*.yaml *.yml"), ("All", "*.*")],
        )
        if not path:
            return
        try:
            devices, options = load_device_config(path)
        except Exception as e:
            messagebox.showerror("Import", str(e))
            return
        self._clear_device_rows()
        for d in devices:
            ser = (d.get("serial") or "").strip()
            if ser:
                self._add_device_row(serial=ser, status="", checked=True)
        if "threshold" in options:
            self._threshold.set(float(options["threshold"]))
        if "loop_interval" in options:
            self._loop_interval.set(float(options["loop_interval"]))
        if "loop" in options:
            self._loop.set(bool(options["loop"]))
        if isinstance(options.get("stones"), str):
            self._stones.set(options["stones"])
        self._append_log(f"[GUI] Imported {path}")

    def _export_config(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export device config",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("YAML", "*.yaml")],
        )
        if not path:
            return
        devices_payload: list[dict] = []
        for row in self._device_rows:
            if not row.include.get():
                continue
            s = row.serial.get().strip()
            if s:
                devices_payload.append({"serial": s})
        data: dict = {
            "devices": devices_payload,
            "threshold": self._threshold.get(),
            "loop": self._loop.get(),
            "loop_interval": self._loop_interval.get(),
        }
        st = self._stones.get().strip()
        if st:
            data["stones"] = st
        try:
            dump_device_config(path, data)
        except Exception as e:
            messagebox.showerror("Export", str(e))
            return
        self._append_log(f"[GUI] Exported {path}")

    def _selected_devices(self) -> list[dict]:
        out: list[dict] = []
        for row in self._device_rows:
            if not row.include.get():
                continue
            s = row.serial.get().strip()
            if s:
                out.append({"serial": s})
        return out

    def _on_run(self) -> None:
        ok, err = adb_available()
        if not ok:
            messagebox.showerror("ADB", err)
            return
        devices = self._selected_devices()
        if not devices:
            messagebox.showwarning("Run", "Select at least one device (checked row with non-empty serial).")
            return
        action = self._action.get()
        if action not in ACTIONS:
            messagebox.showerror("Run", "Invalid action.")
            return

        self._run_btn.config(state=tk.DISABLED)
        self._stop_btn.config(state=tk.NORMAL)
        self._cancel.clear()

        threshold = float(self._threshold.get())
        loop = bool(self._loop.get())
        loop_interval = float(self._loop_interval.get())
        stone_tags = _parse_stone_tags(self._stones.get())
        verbose = bool(self._verbose_log.get())

        def work() -> None:
            def log_fn(line: str) -> None:
                self._log_queue.put(("log", line))

            try:
                stream = _LineQueueLogStream(log_fn)
                ctx = (
                    contextlib.redirect_stdout(stream),
                    contextlib.redirect_stderr(stream),
                )
                if verbose:
                    with ctx[0], ctx[1]:
                        rc = run_multi_device_adb(
                            devices=devices,
                            action=action,
                            threshold=threshold,
                            stone_tags=stone_tags,
                            loop=loop,
                            loop_interval=loop_interval,
                            log=log_fn,
                            cancel_event=self._cancel,
                            verbose=True,
                        )
                    stream.flush()
                else:
                    rc = run_multi_device_adb(
                        devices=devices,
                        action=action,
                        threshold=threshold,
                        stone_tags=stone_tags,
                        loop=loop,
                        loop_interval=loop_interval,
                        log=log_fn,
                        cancel_event=self._cancel,
                        verbose=False,
                    )
                self._log_queue.put(("done", rc))
            except Exception as e:
                self._log_queue.put(("log", f"[ERROR] {e}"))
                self._log_queue.put(("done", 1))

        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()

    def _on_stop(self) -> None:
        self._cancel.set()


def main() -> None:
    app = YulangAdbApp()
    app.mainloop()


if __name__ == "__main__":
    main()
