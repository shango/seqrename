"""Sequence browser: card rows painted by a delegate."""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QListWidgetItem,
    QStyle,
    QStyledItemDelegate,
)

from ..fsops import human_size
from ..scanner import Sequence
from . import theme

SEQ_ROLE = Qt.UserRole + 1
ROW_HEIGHT = 62


class SequenceDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index) -> QSize:  # noqa: N802
        return QSize(200, ROW_HEIGHT)

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: N802
        seq: Sequence = index.data(SEQ_ROLE)
        if seq is None:
            return
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = option.rect.adjusted(6, 3, -6, -3)
        selected = bool(option.state & QStyle.State_Selected)
        hovered = bool(option.state & QStyle.State_MouseOver)

        if selected:
            painter.setBrush(theme.color(theme.ACCENT_SOFT))
            painter.setPen(QPen(theme.color(theme.ACCENT, 90), 1))
        elif hovered:
            painter.setBrush(theme.color(theme.SURFACE_2))
            painter.setPen(Qt.NoPen)
        else:
            painter.setBrush(theme.color(theme.SURFACE_2, 110))
            painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 7, 7)

        if selected:
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme.color(theme.ACCENT))
            painter.drawRoundedRect(QRect(rect.left(), rect.top() + 10, 3, rect.height() - 20), 2, 2)

        text_left = rect.left() + 14
        text_right = rect.right() - 12
        width = text_right - text_left

        name_font = theme.mono_font(9)
        painter.setFont(name_font)
        painter.setPen(theme.color(theme.TEXT if selected or hovered else "#d6dbe6"))
        fm = QFontMetrics(name_font)
        name = fm.elidedText(seq.display_name(), Qt.ElideMiddle, width)
        painter.drawText(QRect(text_left, rect.top() + 11, width, 16), Qt.AlignLeft | Qt.AlignVCenter, name)

        meta_font = theme.ui_font(8)
        painter.setFont(meta_font)
        fm2 = QFontMetrics(meta_font)
        meta = f"{seq.range_str()}   ·   {seq.count} frames   ·   {human_size(seq.total_size)}"
        meta_rect = QRect(text_left, rect.top() + 32, width, 15)

        badges = []
        if seq.missing:
            badges.append((f"{len(seq.missing)} missing", theme.WARN))
        if not seq.padding_consistent:
            badges.append(("mixed padding", theme.DANGER))
        x = text_right
        for label, tone in reversed(badges):
            w = fm2.horizontalAdvance(label) + 12
            x -= w + 6
            chip = QRect(x, rect.top() + 31, w, 16)
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme.color(tone, 36))
            painter.drawRoundedRect(chip, 5, 5)
            painter.setPen(theme.color(tone))
            painter.drawText(chip, Qt.AlignCenter, label)
        meta_rect.setRight(max(text_left, x - 8))

        painter.setPen(theme.color(theme.TEXT_FAINT))
        painter.drawText(
            meta_rect,
            Qt.AlignLeft | Qt.AlignVCenter,
            fm2.elidedText(meta, Qt.ElideRight, meta_rect.width()),
        )
        painter.restore()


class SequenceList(QListWidget):
    selection_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setItemDelegate(SequenceDelegate(self))
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setMouseTracking(True)
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setFrameShape(QListWidget.NoFrame)
        self.itemSelectionChanged.connect(
            lambda: self.selection_changed.emit(self.selected_sequences())
        )

    def set_sequences(self, sequences: list[Sequence]) -> None:
        self.clear()
        for seq in sequences:
            item = QListWidgetItem()
            item.setData(SEQ_ROLE, seq)
            item.setToolTip(f"{seq.directory}\n{seq.display_name()}  [{seq.range_str()}]")
            self.addItem(item)
        if sequences:
            self.setCurrentRow(0)
        else:
            self.selection_changed.emit([])

    def selected_sequences(self) -> list[Sequence]:
        return [i.data(SEQ_ROLE) for i in self.selectedItems()]

    def all_sequences(self) -> list[Sequence]:
        return [self.item(i).data(SEQ_ROLE) for i in range(self.count())]

    def select_all_sequences(self) -> None:
        self.selectAll()
