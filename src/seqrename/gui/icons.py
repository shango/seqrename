"""Inline SVG icon set, recoloured at render time."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from . import theme

_STROKE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
    'stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{body}</svg>'
)

_BODY = {
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "refresh": '<path d="M20 11a8 8 0 1 0-.7 4.4"/><path d="M20 4v7h-7"/>',
    "undo": '<path d="M4 11h11a5 5 0 0 1 0 10h-6"/><path d="M8 7l-4 4 4 4"/>',
    "check": '<path d="M4 12.5 9.5 18 20 6.5"/>',
    "play": '<path d="M7 4.5 19 12 7 19.5z"/>',
    "warning": '<path d="M12 4 2.5 20h19z"/><path d="M12 10v4.5"/><path d="M12 17.6v.1"/>',
    "layers": '<path d="M12 3 3 8l9 5 9-5z"/><path d="M3 13.5 12 18l9-4.5"/>',
    "film": '<rect x="3" y="4.5" width="18" height="15" rx="2"/><path d="M8 4.5v15M16 4.5v15M3 12h18"/>',
    "arrow": '<path d="M4 12h15"/><path d="M13.5 6.5 20 12l-6.5 5.5"/>',
    "clock": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "gap": '<path d="M4 12h4"/><path d="M16 12h4"/><path d="M12 8v8"/>',
    "close": '<path d="M6 6l12 12M18 6 6 18"/>',
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5"/><path d="M12 8v.1"/>',
}


@lru_cache(maxsize=256)
def pixmap(name: str, color: str = theme.TEXT_DIM, size: int = 18) -> QPixmap:
    svg = _STROKE.format(c=color, body=_BODY[name])
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pm = QPixmap(size * 2, size * 2)
    pm.fill(Qt.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()
    pm.setDevicePixelRatio(2.0)
    return pm


@lru_cache(maxsize=256)
def icon(name: str, color: str = theme.TEXT_DIM, size: int = 18) -> QIcon:
    return QIcon(pixmap(name, color, size))


def app_icon() -> QIcon:
    """Procedural app mark: accent rounded square with a film-strip glyph."""
    result = QIcon()
    for size in (32, 64, 256):
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(theme.color(theme.ACCENT))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, size, size, size * 0.22, size * 0.22)
        glyph = QSvgRenderer(QByteArray(_STROKE.format(c="#ffffff", body=_BODY["film"]).encode()))
        pad = size * 0.22
        glyph.render(p, QRectF(pad, pad, size - 2 * pad, size - 2 * pad))
        p.end()
        result.addPixmap(pm)
    return result
