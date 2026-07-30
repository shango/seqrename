"""Render the app mark to packaging/seqrename.ico for the Windows build."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from PySide6.QtGui import QGuiApplication  # noqa: E402

from seqrename.gui import icons  # noqa: E402

OUT = Path(__file__).resolve().parent / "seqrename.ico"


def main() -> int:
    QGuiApplication([])
    pixmap = icons.app_icon().pixmap(256, 256)
    if not pixmap.save(str(OUT), "ICO"):
        print(f"Failed to write {OUT}", file=sys.stderr)
        return 1
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
