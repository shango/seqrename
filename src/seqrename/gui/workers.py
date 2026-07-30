"""Background work: one generic worker thread for scan / validate / apply / undo."""

from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import QThread, Signal

ProgressFn = Callable[[int, int, str], None]


class Worker(QThread):
    """Runs ``fn(progress)`` off the UI thread."""

    progress = Signal(int, int, str)
    result_ready = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[ProgressFn], Any], parent=None):
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:  # noqa: D102
        try:
            result = self._fn(self.progress.emit)
        except Exception as exc:  # noqa: BLE001 - surfaced in the UI
            traceback.print_exc()
            self.failed.emit(f"{type(exc).__name__}: {exc}")
            return
        self.result_ready.emit(result)
