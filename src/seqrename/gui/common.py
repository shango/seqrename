"""Small shared widgets: cards, section headers, badges, labelled rows."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from . import icons, theme


class Card(QFrame):
    """Titled container used for each block of operations."""

    def __init__(self, title: str, icon_name: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(13, 10, 13, 12)
        outer.setSpacing(8)

        head = QHBoxLayout()
        head.setSpacing(8)
        if icon_name:
            glyph = QLabel()
            glyph.setPixmap(icons.pixmap(icon_name, theme.TEXT_FAINT, 15))
            head.addWidget(glyph)
        label = QLabel(title.upper())
        label.setObjectName("CardTitle")
        f = label.font()
        f.setPointSize(8)
        f.setBold(True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 0.8)
        label.setFont(f)
        head.addWidget(label)
        head.addStretch(1)
        self.header_extra = head
        outer.addLayout(head)

        self.body = QVBoxLayout()
        self.body.setSpacing(7)
        outer.addLayout(self.body)

    def add(self, widget: QWidget) -> QWidget:
        self.body.addWidget(widget)
        return widget

    def add_row(self, *widgets: QWidget, spacing: int = 8) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(spacing)
        for w in widgets:
            row.addWidget(w)
        self.body.addLayout(row)
        return row


class Panel(QFrame):
    """Full-height column with a small caption at the top."""

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Panel")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(1, 1, 1, 1)
        self.layout_.setSpacing(0)

        bar = QWidget()
        bar.setFixedHeight(38)
        self.header = QHBoxLayout(bar)
        self.header.setContentsMargins(14, 0, 10, 0)
        self.header.setSpacing(8)
        caption = QLabel(title.upper())
        caption.setObjectName("PanelTitle")
        f = caption.font()
        f.setPointSize(8)
        f.setBold(True)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 1.0)
        caption.setFont(f)
        self.header.addWidget(caption)
        self.header.addStretch(1)
        self.layout_.addWidget(bar)
        self.layout_.addWidget(hline())

    def add(self, widget: QWidget, stretch: int = 0) -> QWidget:
        self.layout_.addWidget(widget, stretch)
        return widget


def hline() -> QFrame:
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {theme.STROKE};")
    return line


def field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("Hint")
    f = label.font()
    f.setPointSize(8)
    label.setFont(f)
    return label


def labelled(text: str, widget: QWidget) -> QWidget:
    box = QWidget()
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    layout.addWidget(field_label(text))
    layout.addWidget(widget)
    return box


class Badge(QLabel):
    """Small rounded status chip."""

    def __init__(self, text: str = "", tone: str = theme.TEXT_DIM, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        f = self.font()
        f.setPointSize(8)
        f.setBold(True)
        self.setFont(f)
        self.set_tone(tone)

    def set_tone(self, tone: str) -> None:
        self.setStyleSheet(
            f"color: {tone};"
            f"background: rgba({_rgb(tone)}, 0.14);"
            "border-radius: 5px; padding: 2px 7px;"
        )


class EmptyState(QWidget):
    """Centred icon + message shown when a panel has nothing to display."""

    def __init__(self, icon_name: str, title: str, subtitle: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(8)

        glyph = QLabel()
        glyph.setPixmap(icons.pixmap(icon_name, theme.STROKE_STRONG, 40))
        glyph.setAlignment(Qt.AlignCenter)
        layout.addWidget(glyph)

        self.title = QLabel(title)
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet(f"color: {theme.TEXT_DIM};")
        layout.addWidget(self.title)

        self.subtitle = QLabel(subtitle)
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setWordWrap(True)
        self.subtitle.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 11px;")
        layout.addWidget(self.subtitle)

    def set_text(self, title: str, subtitle: str = "") -> None:
        self.title.setText(title)
        self.subtitle.setText(subtitle)


def _rgb(hex_str: str) -> str:
    c = theme.color(hex_str)
    return f"{c.red()}, {c.green()}, {c.blue()}"
