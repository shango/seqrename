"""Application entry point."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from . import icons, theme
from .main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    # --selftest builds the window, then exits 0. The packaged build runs this
    # to prove the bundle imports, finds its Qt plugins and loads its assets;
    # a broken bundle shows a blocking error dialog instead of exiting.
    selftest = "--selftest" in argv
    if selftest:
        argv.remove("--selftest")

    QApplication.setApplicationName("SeqRename")
    QApplication.setOrganizationName("SeqRename")

    app = QApplication(argv)
    # Ask Windows for a dark title bar and dark native dialogs.
    hints = QGuiApplication.styleHints()
    if hasattr(hints, "setColorScheme"):
        hints.setColorScheme(Qt.ColorScheme.Dark)
    theme.apply(app)

    start_dir = argv[1] if len(argv) > 1 else None
    window = MainWindow(start_dir)
    window.show()

    if selftest:
        app.processEvents()
        icons.pixmap("folder")  # exercises the SVG renderer
        print("selftest ok")
        return 0
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
