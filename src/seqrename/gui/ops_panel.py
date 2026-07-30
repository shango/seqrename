"""The operations form - everything that turns into a RenameOps."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..ops import Case, ExtCase, OutputMode, RenameOps, VersionOp
from .common import Card, field_label, labelled

CASES = [("Keep", Case.KEEP), ("lowercase", Case.LOWER), ("UPPERCASE", Case.UPPER), ("Title Case", Case.TITLE)]
VERSIONS = [("Keep", VersionOp.KEEP), ("Bump +1", VersionOp.BUMP), ("Set to", VersionOp.SET), ("Strip", VersionOp.STRIP)]
EXT_CASES = [("Keep", ExtCase.KEEP), ("lower", ExtCase.LOWER), ("UPPER", ExtCase.UPPER)]


def _combo(items: list[tuple[str, object]]) -> QComboBox:
    """Stores the enum's *value*; Qt does not preserve Python enum identity."""
    box = QComboBox()
    for label, value in items:
        box.addItem(label, value.value)
    return box


def _spin(lo: int, hi: int, value: int, suffix: str = "") -> QSpinBox:
    s = QSpinBox()
    s.setRange(lo, hi)
    s.setValue(value)
    s.setAlignment(Qt.AlignRight)
    if suffix:
        s.setSuffix(suffix)
    return s


class OpsPanel(QScrollArea):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(11, 11, 11, 11)
        layout.setSpacing(8)

        layout.addWidget(self._name_card())
        layout.addWidget(self._number_card())
        layout.addWidget(self._format_card())
        layout.addWidget(self._output_card())
        layout.addStretch(1)
        self.setWidget(body)

        self._wire()
        self._sync_enabled()

    # -- cards -----------------------------------------------------------

    def _name_card(self) -> Card:
        card = Card("Name", "layers")
        self.find = QLineEdit()
        self.find.setPlaceholderText("find…")
        self.replace = QLineEdit()
        self.replace.setPlaceholderText("replace with…")
        card.add(labelled("Find", self.find))
        card.add(labelled("Replace", self.replace))
        self.use_regex = QCheckBox("Regular expression")
        self.case = _combo(CASES)
        row = QHBoxLayout()
        row.addWidget(self.use_regex)
        row.addStretch(1)
        row.addWidget(field_label("Case"))
        row.addWidget(self.case)
        card.body.addLayout(row)
        return card

    def _number_card(self) -> Card:
        card = Card("Numbering", "film")
        self.renumber = QCheckBox("Renumber frames")
        card.add(self.renumber)
        self.start = _spin(-99_999, 9_999_999, 1001)
        self.step = _spin(-1000, 1000, 1)
        card.add_row(labelled("Start at", self.start), labelled("Step", self.step))
        self.offset = _spin(-99_999, 99_999, 0)
        self.reverse = QCheckBox("Reverse order")
        card.add_row(labelled("Offset existing frames by", self.offset))
        card.add(self.reverse)
        return card

    def _format_card(self) -> Card:
        card = Card("Version & format", "clock")
        self.version_op = _combo(VERSIONS)
        self.version_value = _spin(0, 9999, 1)
        card.add_row(labelled("Version", self.version_op), labelled("Value", self.version_value))

        self.repad = QCheckBox("Repad frame numbers")
        self.pad = _spin(1, 12, 4, " digits")
        card.add_row(self.repad, self.pad)

        self.ext = QLineEdit()
        self.ext.setPlaceholderText("keep")
        self.ext_case = _combo(EXT_CASES)
        card.add_row(labelled("Extension", self.ext), labelled("Ext case", self.ext_case))
        return card

    def _output_card(self) -> Card:
        card = Card("Output", "folder")
        self.mode_rename = QRadioButton("In place")
        self.mode_move = QRadioButton("Move")
        self.mode_copy = QRadioButton("Copy")
        self.mode_rename.setChecked(True)
        self.mode_group = QButtonGroup(self)
        modes = QHBoxLayout()
        modes.setSpacing(12)
        for i, b in enumerate((self.mode_rename, self.mode_move, self.mode_copy)):
            self.mode_group.addButton(b, i)
            modes.addWidget(b)
        modes.addStretch(1)
        card.body.addLayout(modes)

        self.dest = QLineEdit()
        self.dest.setPlaceholderText("destination folder…")
        browse = QPushButton("…")
        browse.setFixedWidth(34)
        browse.clicked.connect(self._pick_dest)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self.dest, 1)
        row.addWidget(browse)
        card.body.addLayout(row)
        self.dest_row_browse = browse

        self.verify = QCheckBox("Verify copies with a checksum (slower)")
        card.add(self.verify)
        return card

    # -- behaviour -------------------------------------------------------

    def _wire(self) -> None:
        for w in (self.find, self.replace, self.dest, self.ext):
            w.textChanged.connect(self._emit)
        for w in (self.case, self.version_op, self.ext_case):
            w.currentIndexChanged.connect(self._emit)
        for w in (self.start, self.step, self.offset, self.pad, self.version_value):
            w.valueChanged.connect(self._emit)
        for w in (self.use_regex, self.renumber, self.reverse, self.repad, self.verify):
            w.toggled.connect(self._emit)
        self.mode_group.idToggled.connect(lambda *_: self._emit())

    def _emit(self, *_args) -> None:
        self._sync_enabled()
        self.changed.emit()

    def _sync_enabled(self) -> None:
        renumbering = self.renumber.isChecked()
        self.start.setEnabled(renumbering)
        self.step.setEnabled(renumbering)
        self.offset.setEnabled(not renumbering)
        self.version_value.setEnabled(VersionOp(self.version_op.currentData()) is VersionOp.SET)
        self.pad.setEnabled(self.repad.isChecked())
        to_folder = not self.mode_rename.isChecked()
        self.dest.setEnabled(to_folder)
        self.dest_row_browse.setEnabled(to_folder)
        self.verify.setEnabled(self.mode_copy.isChecked())

    def _pick_dest(self) -> None:
        start = self.dest.text() or ""
        chosen = QFileDialog.getExistingDirectory(self, "Choose destination folder", start)
        if chosen:
            self.dest.setText(chosen)

    # -- value -----------------------------------------------------------

    def ops(self) -> RenameOps:
        if self.mode_copy.isChecked():
            mode = OutputMode.COPY
        elif self.mode_move.isChecked():
            mode = OutputMode.MOVE
        else:
            mode = OutputMode.RENAME
        return RenameOps(
            find=self.find.text(),
            replace=self.replace.text(),
            use_regex=self.use_regex.isChecked(),
            case=Case(self.case.currentData()),
            version_op=VersionOp(self.version_op.currentData()),
            version_value=self.version_value.value(),
            renumber=self.renumber.isChecked(),
            start=self.start.value(),
            step=self.step.value(),
            reverse=self.reverse.isChecked(),
            offset=0 if self.renumber.isChecked() else self.offset.value(),
            repad=self.repad.isChecked(),
            pad=self.pad.value(),
            ext_replace=self.ext.text().strip(),
            ext_case=ExtCase(self.ext_case.currentData()),
            mode=mode,
            dest=self.dest.text().strip(),
        )

    def verify_checked(self) -> bool:
        return self.verify.isChecked()

    def reset(self) -> None:
        blockers = [
            self.find, self.replace, self.dest, self.ext, self.case, self.version_op,
            self.ext_case, self.start, self.step, self.offset, self.pad,
            self.version_value, self.use_regex, self.renumber, self.reverse,
            self.repad, self.verify, self.mode_rename,
        ]
        for w in blockers:
            w.blockSignals(True)
        self.find.clear()
        self.replace.clear()
        self.dest.clear()
        self.ext.clear()
        for combo in (self.case, self.version_op, self.ext_case):
            combo.setCurrentIndex(0)
        self.start.setValue(1001)
        self.step.setValue(1)
        self.offset.setValue(0)
        self.pad.setValue(4)
        self.version_value.setValue(1)
        for check in (self.use_regex, self.renumber, self.reverse, self.repad, self.verify):
            check.setChecked(False)
        self.mode_rename.setChecked(True)
        for w in blockers:
            w.blockSignals(False)
        self._emit()

    def set_invalid(self, invalid: bool) -> None:
        """Flag the find field when the regex does not compile."""
        self.find.setProperty("invalid", "true" if invalid else "false")
        self.find.style().unpolish(self.find)
        self.find.style().polish(self.find)
