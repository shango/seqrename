"""Confirmation and problem-report dialogs."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from . import icons, theme


class ConfirmDialog(QDialog):
    """Modal with a headline, optional detail list and a checkbox."""

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        details: list[str] | None = None,
        confirm_text: str = "Continue",
        danger: bool = False,
        checkbox: str = "",
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        head = QHBoxLayout()
        head.setSpacing(11)
        glyph = QLabel()
        glyph.setPixmap(icons.pixmap("warning" if danger else "info",
                                     theme.WARN if danger else theme.ACCENT, 22))
        glyph.setAlignment(Qt.AlignTop)
        head.addWidget(glyph)

        text = QVBoxLayout()
        text.setSpacing(5)
        heading = QLabel(title)
        f = heading.font()
        f.setPointSize(12)
        f.setBold(True)
        heading.setFont(f)
        text.addWidget(heading)
        body = QLabel(message)
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {theme.TEXT_DIM};")
        text.addWidget(body)
        head.addLayout(text, 1)
        layout.addLayout(head)

        if details:
            box = QTextEdit()
            box.setReadOnly(True)
            box.setFont(theme.mono_font(9))
            box.setPlainText("\n".join(details))
            box.setFixedHeight(min(180, 22 + 16 * len(details)))
            layout.addWidget(box)

        self.checkbox = None
        if checkbox:
            self.checkbox = QCheckBox(checkbox)
            self.checkbox.setStyleSheet(f"color: {theme.DANGER};")
            layout.addWidget(self.checkbox)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        ok = QPushButton(confirm_text)
        ok.setObjectName("Primary")
        ok.setDefault(True)
        if danger:
            ok.setStyleSheet(
                f"background: {theme.DANGER}; border-color: {theme.DANGER}; color: #21070a;"
            )
        ok.clicked.connect(self.accept)
        buttons.addWidget(ok)
        layout.addLayout(buttons)

    @property
    def checked(self) -> bool:
        return bool(self.checkbox and self.checkbox.isChecked())
