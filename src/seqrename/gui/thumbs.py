"""Thumbnail strip for the selected sequence.

Qt reads png/jpg/tiff/bmp directly; EXR/DPX and friends get a labelled
placeholder tile rather than a heavyweight image dependency.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QRect, QRunnable, QSize, Qt, QThreadPool, Signal
from PySide6.QtGui import QImageReader, QPainter, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ..scanner import Sequence
from . import theme

TILE_W, TILE_H = 104, 62
_QT_READABLE = {bytes(f).decode().lower() for f in QImageReader.supportedImageFormats()}


def readable(path: Path) -> bool:
    return path.suffix.lstrip(".").lower() in _QT_READABLE


class _Signals(QObject):
    done = Signal(str, object)


class _LoadTask(QRunnable):
    def __init__(self, path: Path, signals: _Signals):
        super().__init__()
        self.path = path
        self.signals = signals

    def run(self) -> None:
        reader = QImageReader(str(self.path))
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid() and size.width() > 0:
            scale = max(1, min(size.width() // (TILE_W * 2), size.height() // (TILE_H * 2)))
            reader.setScaledSize(QSize(size.width() // scale, size.height() // scale))
        image = reader.read()
        self.signals.done.emit(str(self.path), image if not image.isNull() else None)


class Tile(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(TILE_W, TILE_H)
        self.caption = ""
        self.placeholder = ""
        self._pix: QPixmap | None = None
        self.setAlignment(Qt.AlignCenter)

    def set_source(self, caption: str, placeholder: str) -> None:
        self.caption = caption
        self.placeholder = placeholder
        self._pix = None
        self.update()

    def set_image(self, image) -> None:
        if image is None:
            self._pix = None
        else:
            self._pix = QPixmap.fromImage(image).scaled(
                TILE_W * 2, TILE_H * 2, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
            self._pix.setDevicePixelRatio(2.0)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        path_rect = QRect(rect)
        p.setPen(Qt.NoPen)
        p.setBrush(theme.color(theme.SURFACE_3))
        p.drawRoundedRect(path_rect, 6, 6)

        if self._pix is not None:
            p.save()
            p.setClipRect(path_rect)
            x = path_rect.center().x() - self._pix.width() / self._pix.devicePixelRatio() / 2
            y = path_rect.center().y() - self._pix.height() / self._pix.devicePixelRatio() / 2
            p.drawPixmap(int(x), int(y), self._pix)
            p.restore()
        elif self.placeholder:
            p.setFont(theme.mono_font(9))
            p.setPen(theme.color(theme.TEXT_FAINT))
            p.drawText(path_rect, Qt.AlignCenter, self.placeholder)

        if self.caption:
            band = QRect(rect.left(), rect.bottom() - 15, rect.width(), 16)
            p.setPen(Qt.NoPen)
            p.setBrush(theme.color("#000000", 150))
            p.drawRoundedRect(band, 6, 6)
            p.fillRect(QRect(band.left(), band.top(), band.width(), 6), theme.color("#000000", 150))
            p.setFont(theme.mono_font(7))
            p.setPen(theme.color("#cfd6e4"))
            p.drawText(band, Qt.AlignCenter, self.caption)
        p.end()


class ThumbStrip(QWidget):
    """First / middle / last frame of the selected sequence."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(3)
        self.signals = _Signals()
        self.signals.done.connect(self._on_loaded)
        self._pending: dict[str, Tile] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 12)
        outer.setSpacing(7)
        self.caption = QLabel("No sequence selected")
        self.caption.setObjectName("Hint")
        outer.addWidget(self.caption)

        row = QHBoxLayout()
        row.setSpacing(7)
        self.tiles = [Tile() for _ in range(3)]
        for t in self.tiles:
            row.addWidget(t)
        row.addStretch(1)
        outer.addLayout(row)

    def show_sequence(self, seq: Sequence | None) -> None:
        self._pending.clear()
        if seq is None or not seq.frames:
            self.caption.setText("No sequence selected")
            for t in self.tiles:
                t.set_source("", "")
                t.set_image(None)
            return

        self.caption.setText(
            f"{seq.count} frames  ·  {seq.range_str()}"
            + (f"  ·  {len(seq.missing)} missing" if seq.missing else "")
        )
        if seq.count == 1:
            picks = [seq.frames[0]]
        elif seq.count == 2:
            picks = [seq.frames[0], seq.frames[1]]
        else:
            picks = [seq.frames[0], seq.frames[seq.count // 2], seq.frames[-1]]

        for i, tile in enumerate(self.tiles):
            tile.setVisible(i < len(picks))
            if i >= len(picks):
                continue
            frame = picks[i]
            tile.set_source(str(frame.number), seq.ext.lstrip(".").upper())
            tile.set_image(None)
            if readable(frame.path):
                self._pending[str(frame.path)] = tile
                self.pool.start(_LoadTask(frame.path, self.signals))

    def _on_loaded(self, path: str, image) -> None:
        tile = self._pending.pop(path, None)
        if tile is not None:
            tile.set_image(image)
