"""Preview table: old -> new with character-level diff highlighting."""

from __future__ import annotations

from difflib import SequenceMatcher
from functools import lru_cache

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRect, Qt
from PySide6.QtGui import QFontMetrics, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QStyle,
    QStyledItemDelegate,
    QTableView,
)

from ..plan import Entry, Status
from . import icons, theme

COL_CURRENT, COL_ARROW, COL_NEW, COL_STATUS = range(4)
HEADERS = ["Current name", "", "New name", "Status"]

STATUS_LOOK = {
    Status.OK: ("Rename", theme.OK),
    Status.UNCHANGED: ("Unchanged", theme.TEXT_FAINT),
    Status.COLLISION: ("Collision", theme.DANGER),
    Status.DUPLICATE: ("Duplicate", theme.DANGER),
}


@lru_cache(maxsize=4096)
def diff_spans(old: str, new: str) -> tuple[tuple[tuple[int, int], ...], tuple[tuple[int, int], ...]]:
    """Character ranges that differ, as (old_spans, new_spans)."""
    matcher = SequenceMatcher(None, old, new, autojunk=False)
    old_spans: list[tuple[int, int]] = []
    new_spans: list[tuple[int, int]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if i2 > i1:
            old_spans.append((i1, i2))
        if j2 > j1:
            new_spans.append((j1, j2))
    return tuple(old_spans), tuple(new_spans)


class PreviewModel(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.entries: list[Entry] = []

    def set_entries(self, entries: list[Entry]) -> None:
        self.beginResetModel()
        self.entries = entries
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self.entries)

    def columnCount(self, parent=QModelIndex()) -> int:  # noqa: N802
        return len(HEADERS)

    def entry(self, row: int) -> Entry:
        return self.entries[row]

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        e = self.entries[index.row()]
        if role == Qt.DisplayRole:
            if index.column() == COL_CURRENT:
                return e.src.name
            if index.column() == COL_NEW:
                return e.dst.name
            if index.column() == COL_STATUS:
                return STATUS_LOOK[e.status][0]
            return ""
        if role == Qt.ToolTipRole:
            tip = f"{e.src}\n→  {e.dst}"
            return f"{tip}\n\n{e.note}" if e.note else tip
        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # noqa: N802
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return HEADERS[section]
        return None


class PreviewDelegate(QStyledItemDelegate):
    """Paints file names with changed spans highlighted, and status pills."""

    def paint(self, painter: QPainter, option, index) -> None:  # noqa: N802
        model: PreviewModel = index.model()
        entry = model.entry(index.row())
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = option.rect
        selected = bool(option.state & QStyle.State_Selected)
        if selected:
            painter.fillRect(rect, theme.color(theme.ACCENT_SOFT))
        elif index.row() % 2:
            painter.fillRect(rect, theme.color(theme.SURFACE_2, 90))
        if entry.status.blocking:
            painter.fillRect(QRect(rect.left(), rect.top(), 2, rect.height()), theme.color(theme.DANGER))

        col = index.column()
        if col == COL_ARROW:
            pm = icons.pixmap("arrow", theme.TEXT_FAINT, 14)
            painter.drawPixmap(
                rect.center().x() - 7, rect.center().y() - 7, pm.width() // 2, pm.height() // 2, pm
            )
        elif col == COL_STATUS:
            self._paint_status(painter, rect, entry)
        else:
            self._paint_name(painter, rect, entry, col)
        painter.restore()

    def _paint_status(self, painter: QPainter, rect: QRect, entry: Entry) -> None:
        label, tone = STATUS_LOOK[entry.status]
        font = theme.ui_font(8, bold=True)
        painter.setFont(font)
        w = QFontMetrics(font).horizontalAdvance(label) + 16
        pill = QRect(rect.left() + 8, rect.center().y() - 9, w, 18)
        painter.setPen(Qt.NoPen)
        painter.setBrush(theme.color(tone, 34))
        painter.drawRoundedRect(pill, 6, 6)
        painter.setPen(theme.color(tone))
        painter.drawText(pill, Qt.AlignCenter, label)

    def _paint_name(self, painter: QPainter, rect: QRect, entry: Entry, col: int) -> None:
        old, new = entry.src.name, entry.dst.name
        text = old if col == COL_CURRENT else new
        font = theme.mono_font(9)
        painter.setFont(font)
        fm = QFontMetrics(font)

        spans: tuple[tuple[int, int], ...] = ()
        if entry.changed:
            spans = diff_spans(old, new)[0 if col == COL_CURRENT else 1]

        x = rect.left() + 10
        available = rect.width() - 18
        if fm.horizontalAdvance(text) > available:
            spans = ()
            text = fm.elidedText(text, Qt.ElideMiddle, available)

        base = theme.TEXT_DIM if col == COL_CURRENT else theme.TEXT
        if entry.status is Status.UNCHANGED:
            base = theme.TEXT_FAINT
        tone = theme.DANGER if entry.status.blocking and col == COL_NEW else theme.ACCENT

        y = rect.top()
        h = rect.height()
        cursor = 0
        for start, end in spans:
            if start > cursor:
                chunk = text[cursor:start]
                painter.setPen(theme.color(base))
                painter.drawText(QRect(x, y, fm.horizontalAdvance(chunk) + 2, h),
                                 Qt.AlignLeft | Qt.AlignVCenter, chunk)
                x += fm.horizontalAdvance(chunk)
            chunk = text[start:end]
            w = fm.horizontalAdvance(chunk)
            painter.setPen(Qt.NoPen)
            painter.setBrush(theme.color(tone, 46))
            painter.drawRoundedRect(QRect(x - 2, y + 5, w + 4, h - 10), 4, 4)
            painter.setPen(theme.color(tone if col == COL_NEW else theme.TEXT_DIM))
            painter.drawText(QRect(x, y, w + 2, h), Qt.AlignLeft | Qt.AlignVCenter, chunk)
            x += w
            cursor = end
        if cursor < len(text):
            chunk = text[cursor:]
            painter.setPen(theme.color(base))
            painter.drawText(QRect(x, y, rect.right() - x, h), Qt.AlignLeft | Qt.AlignVCenter, chunk)


class PreviewTable(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model_ = PreviewModel(self)
        self.setModel(self.model_)
        self.setItemDelegate(PreviewDelegate(self))
        self.setShowGrid(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setFrameShape(QTableView.NoFrame)
        self.setWordWrap(False)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(28)
        header = self.horizontalHeader()
        header.setHighlightSections(False)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header.setSectionResizeMode(COL_CURRENT, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_ARROW, QHeaderView.Fixed)
        header.setSectionResizeMode(COL_NEW, QHeaderView.Stretch)
        header.setSectionResizeMode(COL_STATUS, QHeaderView.Fixed)
        header.resizeSection(COL_ARROW, 34)
        header.resizeSection(COL_STATUS, 110)

    def set_entries(self, entries: list[Entry]) -> None:
        self.model_.set_entries(entries)
        self.scrollToTop()
