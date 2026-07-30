"""SeqRename main window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..fsops import human_size
from ..ops import OutputMode
from ..plan import Plan, Status, last_undoable, undo
from ..scanner import Sequence, scan
from . import icons, theme
from .common import Badge, EmptyState, Panel, hline
from .dialogs import ConfirmDialog
from .ops_panel import OpsPanel
from .preview_table import PreviewTable
from .sequence_list import SequenceList
from .thumbs import ThumbStrip
from .workers import Worker


class MainWindow(QMainWindow):
    def __init__(self, start_dir: str | None = None):
        super().__init__()
        self.setWindowTitle("SeqRename")
        self.setWindowIcon(icons.app_icon())
        self.resize(1440, 900)
        self.setMinimumSize(1080, 680)
        self.setAcceptDrops(True)

        self.settings = QSettings("SeqRename", "SeqRename")
        self.root: Path | None = None
        self.plan: Plan | None = None
        self._workers: set[Worker] = set()
        self._entries: list = []
        self._undo_journal = None
        self._scan_summary = "Ready"
        self._preview_gen = 0
        self._scan_gen = 0
        self._busy = False

        self._build_ui()
        self._build_shortcuts()

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(140)
        self._debounce.timeout.connect(self._rebuild_preview)

        self._restore_state(skip_last_dir=bool(start_dir))
        if start_dir:
            self.set_root(Path(start_dir))

    # -- construction ----------------------------------------------------

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("Root")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._header())

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(12, 12, 12, 10)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(8)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self._sequence_panel())
        self.splitter.addWidget(self._ops_panel())
        self.splitter.addWidget(self._preview_panel())
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 0)
        self.splitter.setStretchFactor(2, 1)
        self.splitter.setSizes([330, 360, 700])
        body_layout.addWidget(self.splitter)

        outer.addWidget(body, 1)
        outer.addWidget(self._footer())
        self.setCentralWidget(root)

    def _header(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Header")
        bar.setFixedHeight(60)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 14, 0)
        layout.setSpacing(10)

        mark = QLabel()
        mark.setPixmap(icons.app_icon().pixmap(22, 22))
        layout.addWidget(mark)

        name = QLabel("SeqRename")
        name.setObjectName("AppName")
        layout.addWidget(name)

        version = Badge(f"v{__version__}", theme.TEXT_FAINT)
        layout.addWidget(version)
        layout.addSpacing(12)

        self.path_field = QLineEdit()
        self.path_field.setObjectName("PathField")
        self.path_field.setPlaceholderText("Drop a folder here, or browse…")
        self.path_field.setClearButtonEnabled(True)
        self.path_field.returnPressed.connect(
            lambda: self.set_root(Path(self.path_field.text().strip()))
        )
        layout.addWidget(self.path_field, 1)

        browse = QPushButton("  Browse")
        browse.setIcon(icons.icon("folder", theme.TEXT_DIM, 16))
        browse.clicked.connect(self.browse)
        layout.addWidget(browse)

        self.rescan_button = QPushButton()
        self.rescan_button.setIcon(icons.icon("refresh", theme.TEXT_DIM, 16))
        self.rescan_button.setToolTip("Rescan folder (F5)")
        self.rescan_button.setFixedWidth(38)
        self.rescan_button.clicked.connect(self.rescan)
        layout.addWidget(self.rescan_button)

        layout.addSpacing(6)
        self.recursive = QCheckBox("Subfolders")
        self.recursive.setToolTip("Scan subdirectories")
        self.recursive.toggled.connect(self.rescan)
        layout.addWidget(self.recursive)

        self.include_single = QCheckBox("Single files")
        self.include_single.setToolTip("Treat lone files as one-frame sequences")
        self.include_single.toggled.connect(self.rescan)
        layout.addWidget(self.include_single)
        return bar

    def _sequence_panel(self) -> QWidget:
        panel = Panel("Sequences")
        self.seq_count = Badge("0", theme.TEXT_FAINT)
        panel.header.insertWidget(1, self.seq_count)

        select_all = QPushButton("Select all")
        select_all.setObjectName("Ghost")
        select_all.clicked.connect(lambda: self.sequence_list.select_all_sequences())
        panel.header.addWidget(select_all)

        panel.setMinimumWidth(270)
        self.sequence_list = SequenceList()
        self.sequence_list.selection_changed.connect(self._on_sequence_selection)

        self.seq_stack = QStackedWidget()
        self.seq_stack.addWidget(self.sequence_list)
        self.seq_empty = EmptyState(
            "layers", "No sequences yet",
            "Choose a folder to scan for image sequences.",
        )
        self.seq_stack.addWidget(self.seq_empty)
        self.seq_stack.setCurrentWidget(self.seq_empty)
        panel.add(self.seq_stack, 1)

        panel.add(hline())
        self.thumbs = ThumbStrip()
        panel.add(self.thumbs)
        return panel

    def _ops_panel(self) -> QWidget:
        panel = Panel("Operations")
        reset = QPushButton("Reset")
        reset.setObjectName("Ghost")
        reset.clicked.connect(self._reset_ops)
        panel.header.addWidget(reset)

        panel.setMinimumWidth(340)
        self.ops = OpsPanel()
        self.ops.changed.connect(self._schedule_preview)
        panel.add(self.ops, 1)
        return panel

    def _preview_panel(self) -> QWidget:
        panel = Panel("Preview")
        self.summary_ok = Badge("0 renames", theme.OK)
        self.summary_issue = Badge("0 conflicts", theme.TEXT_FAINT)
        panel.header.insertWidget(1, self.summary_ok)
        panel.header.insertWidget(2, self.summary_issue)

        self.only_changes = QCheckBox("Only changes")
        self.only_changes.setChecked(True)
        self.only_changes.toggled.connect(lambda: self._show_preview(self._entries))
        panel.header.addWidget(self.only_changes)

        panel.setMinimumWidth(380)
        self.table = PreviewTable()
        self.preview_stack = QStackedWidget()
        self.preview_stack.addWidget(self.table)
        self.preview_empty = EmptyState(
            "film", "Nothing to preview",
            "Select a sequence and set an operation - every change is previewed before anything is written.",
        )
        self.preview_stack.addWidget(self.preview_empty)
        self.preview_stack.setCurrentWidget(self.preview_empty)
        panel.add(self.preview_stack, 1)
        return panel

    def _footer(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("Footer")
        bar.setFixedHeight(58)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 0, 14, 0)
        layout.setSpacing(12)

        self.status = QLabel("Ready")
        self.status.setObjectName("Dim")
        layout.addWidget(self.status)

        self.progress = QProgressBar()
        self.progress.setFixedWidth(180)
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)
        layout.addStretch(1)

        self.undo_button = QPushButton("  Undo last")
        self.undo_button.setIcon(icons.icon("undo", theme.TEXT_DIM, 16))
        self.undo_button.setEnabled(False)
        self.undo_button.clicked.connect(self.undo_last)
        layout.addWidget(self.undo_button)

        self.apply_button = QPushButton("  Apply")
        self.apply_button.setObjectName("Primary")
        self.apply_button.setIcon(icons.icon("check", "#ffffff", 16))
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply)
        layout.addWidget(self.apply_button)
        return bar

    def _build_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+O"), self, self.browse)
        QShortcut(QKeySequence("F5"), self, self.rescan)
        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo_last)
        QShortcut(QKeySequence("Ctrl+Return"), self, self.apply)

    # -- folder ----------------------------------------------------------

    def browse(self) -> None:
        start = str(self.root) if self.root else ""
        chosen = QFileDialog.getExistingDirectory(self, "Choose a folder to scan", start)
        if chosen:
            self.set_root(Path(chosen))

    def set_root(self, path: Path) -> None:
        if not path.is_dir():
            self.set_status(f"Not a folder: {path}", theme.DANGER)
            return
        self.root = path
        self.path_field.setText(str(path))
        self.settings.setValue("last_dir", str(path))
        self.rescan()

    def rescan(self) -> None:
        if self.root is None or self._busy:
            return
        recursive = self.recursive.isChecked()
        singles = self.include_single.isChecked()
        root = self.root
        self._scan_gen += 1
        generation = self._scan_gen
        self.set_status(f"Scanning {root}…")
        self._run(
            lambda _p: scan(root, recursive=recursive, include_single=singles),
            lambda sequences: self._on_scanned(sequences, generation),
        )

    def _on_scanned(self, sequences: list[Sequence], generation: int = 0) -> None:
        if generation and generation != self._scan_gen:
            return  # a newer scan is already running
        self.sequence_list.set_sequences(sequences)
        self.seq_count.setText(str(len(sequences)))
        self.seq_stack.setCurrentWidget(self.sequence_list if sequences else self.seq_empty)
        total = sum(s.count for s in sequences)
        size = sum(s.total_size for s in sequences)
        if sequences:
            self._scan_summary = f"{len(sequences)} sequences · {total} files · {human_size(size)}"
            self.set_status(self._scan_summary)
        else:
            self._scan_summary = "No sequences found."
            self.set_status("No sequences found in this folder.", theme.WARN)
            self.seq_empty.set_text(
                "No sequences found",
                "Try enabling Subfolders or Single files in the header.",
            )
        self._refresh_undo()
        self._schedule_preview()

    # -- preview ---------------------------------------------------------

    def _on_sequence_selection(self, sequences: list[Sequence]) -> None:
        self.thumbs.show_sequence(sequences[0] if sequences else None)
        self._schedule_preview()

    def _reset_ops(self) -> None:
        self.ops.reset()

    def _schedule_preview(self) -> None:
        self._debounce.start()

    def _target_sequences(self) -> list[Sequence]:
        chosen = self.sequence_list.selected_sequences()
        return chosen or self.sequence_list.all_sequences()

    def _rebuild_preview(self) -> None:
        sequences = self._target_sequences()
        ops = self.ops.ops()
        if not sequences or ops.is_noop():
            self.plan = None
            self._show_preview([], noop=True)
            return

        self._preview_gen += 1
        generation = self._preview_gen
        plan = Plan(sequences, ops)

        def build(_progress):
            plan.preview()
            return plan

        def done(result: Plan) -> None:
            if generation != self._preview_gen:
                return  # a newer preview is already on its way
            self.plan = result
            self.ops.set_invalid(bool(result.error))
            if result.error:
                self.set_status(result.error, theme.DANGER)
                self._show_preview([])
                return
            self._show_preview(result.preview())

        self._run(build, done)

    def _show_preview(self, entries, noop: bool = False) -> None:
        self._entries = entries
        counts = {}
        for e in entries:
            counts[e.status] = counts.get(e.status, 0) + 1
        renames = counts.get(Status.OK, 0)
        conflicts = counts.get(Status.COLLISION, 0) + counts.get(Status.DUPLICATE, 0)

        self.summary_ok.setText(f"{renames} rename{'s' if renames != 1 else ''}")
        self.summary_ok.set_tone(theme.OK if renames else theme.TEXT_FAINT)
        self.summary_issue.setText(f"{conflicts} conflict{'s' if conflicts != 1 else ''}")
        self.summary_issue.set_tone(theme.DANGER if conflicts else theme.TEXT_FAINT)

        shown = self._refresh_table()
        if noop or not shown:
            self.preview_empty.set_text(
                "Nothing to preview" if noop else "No changes",
                "Pick a sequence and set an operation - nothing is written until you press Apply."
                if noop else
                "These operations leave every file name unchanged.",
            )
        self.preview_stack.setCurrentWidget(self.table if shown else self.preview_empty)
        self.apply_button.setEnabled(bool(renames) and not self._busy)

        if self._busy:
            return
        if renames or conflicts:
            verb = {OutputMode.RENAME: "rename", OutputMode.MOVE: "move", OutputMode.COPY: "copy"}[
                self.ops.ops().mode
            ]
            note = f"{renames} file{'s' if renames != 1 else ''} to {verb}"
            if conflicts:
                note += f" · {conflicts} blocked by conflicts"
            self.set_status(note, theme.DANGER if conflicts else theme.TEXT_DIM)
        else:
            self.set_status(self._scan_summary)

    def _refresh_table(self) -> int:
        entries = self._entries
        if self.only_changes.isChecked():
            entries = [e for e in entries if e.changed]
        self.table.set_entries(entries)
        return len(entries)

    # -- apply -----------------------------------------------------------

    def apply(self) -> None:
        if self.plan is None or self._busy:
            return
        plan = self.plan
        if not plan.actionable:
            self.set_status("Nothing to apply.", theme.WARN)
            return

        self.set_busy(True, "Checking files…")
        self._run(
            plan.validate,
            lambda problems: self._after_validate(plan, problems),
            on_fail=lambda msg: (self.set_busy(False), self.set_status(msg, theme.DANGER)),
        )

    def _after_validate(self, plan: Plan, problems: list[str]) -> None:
        self.set_busy(False)
        if problems:
            dialog = ConfirmDialog(
                self,
                "Some files need attention",
                "These files may fail during the operation. Continue anyway?",
                details=problems,
                confirm_text="Continue",
                danger=True,
            )
            if dialog.exec() != ConfirmDialog.Accepted:
                self.set_status("Cancelled.", theme.TEXT_DIM)
                return

        ops = plan.ops
        count = len(plan.actionable)
        conflicts = len(plan.blocking)
        verb = {OutputMode.RENAME: "Rename", OutputMode.MOVE: "Move", OutputMode.COPY: "Copy"}[ops.mode]
        message = f"{verb} {count} file{'s' if count != 1 else ''}."
        if ops.mode is not OutputMode.RENAME:
            message += f"\nDestination: {ops.dest}"
        if conflicts:
            message += f"\n{conflicts} file(s) conflict and will be skipped."

        dialog = ConfirmDialog(
            self,
            f"{verb} {count} files?",
            message,
            confirm_text=verb,
            checkbox="Overwrite conflicting files (destructive)" if conflicts else "",
        )
        if dialog.exec() != ConfirmDialog.Accepted:
            self.set_status("Cancelled.", theme.TEXT_DIM)
            return

        force = dialog.checked
        verify = self.ops.verify_checked()
        self.set_busy(True, "Applying…")
        self._run(
            lambda progress: plan.commit(
                progress=progress, force=force, verify=verify, journal_root=self.root
            ),
            self._after_commit,
            on_fail=lambda msg: (self.set_busy(False), self.set_status(msg, theme.DANGER)),
            with_progress=True,
        )

    def _after_commit(self, result) -> None:
        self.set_busy(False)
        if not result.ok:
            suffix = " Everything was rolled back." if result.rolled_back else ""
            self.set_status(f"{result.error}{suffix}", theme.DANGER)
        else:
            self.set_status(f"{result.moved} files {result.mode}d successfully.", theme.OK)
        self.rescan()

    # -- undo ------------------------------------------------------------

    def _refresh_undo(self) -> None:
        journal = last_undoable(self.root) if self.root else None
        self._undo_journal = journal
        self.undo_button.setEnabled(journal is not None and not self._busy)
        self.undo_button.setToolTip(
            f"Undo: {journal.describe()}" if journal else "Nothing to undo in this folder"
        )

    def undo_last(self) -> None:
        journal = self._undo_journal
        if journal is None or self._busy:
            return
        removal = journal.mode == "copy"
        dialog = ConfirmDialog(
            self,
            "Undo last operation?",
            (f"This will delete the {len(journal.entries)} copied files."
             if removal else
             f"This will move {len(journal.entries)} files back to their original names."),
            details=[journal.describe()],
            confirm_text="Delete copies" if removal else "Undo",
            danger=removal,
        )
        if dialog.exec() != ConfirmDialog.Accepted:
            return

        self.set_busy(True, "Undoing…")
        self._run(
            lambda progress: undo(journal, progress=progress),
            self._after_undo,
            on_fail=lambda msg: (self.set_busy(False), self.set_status(msg, theme.DANGER)),
            with_progress=True,
        )

    def _after_undo(self, result) -> None:
        self.set_busy(False)
        if result.ok:
            self.set_status(f"Undone - {result.moved} files restored.", theme.OK)
        else:
            self.set_status(result.error, theme.DANGER)
        self.rescan()

    # -- plumbing --------------------------------------------------------

    def _run(self, fn, on_done, on_fail=None, with_progress: bool = False) -> None:
        worker = Worker(fn, self)
        self._workers.add(worker)
        if with_progress:
            worker.progress.connect(self._on_progress)
        worker.result_ready.connect(on_done)
        worker.failed.connect(on_fail or (lambda msg: self.set_status(msg, theme.DANGER)))
        worker.finished.connect(lambda: self._workers.discard(worker))
        worker.start()

    def _on_progress(self, current: int, total: int, label: str) -> None:
        self.progress.setMaximum(max(total, 1))
        self.progress.setValue(current)
        self.status.setText(f"{label}  ({current}/{total})")

    def set_status(self, text: str, tone: str = theme.TEXT_DIM) -> None:
        self.status.setText(text)
        self.status.setStyleSheet(f"color: {tone};")

    def set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        self.progress.setVisible(busy)
        self.progress.setValue(0)
        self.apply_button.setEnabled(not busy and bool(self.plan and self.plan.actionable))
        self.undo_button.setEnabled(not busy and self._undo_journal is not None)
        self.ops.setEnabled(not busy)
        if message:
            self.set_status(message)

    # -- drag and drop ---------------------------------------------------

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            if path.is_file():
                path = path.parent
            if path.is_dir():
                self.set_root(path)
                break

    # -- window state ----------------------------------------------------

    def _restore_state(self, skip_last_dir: bool = False) -> None:
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        sizes = self.settings.value("splitter")
        if sizes:
            self.splitter.setSizes([int(s) for s in sizes])
        last = self.settings.value("last_dir")
        if not skip_last_dir and last and Path(str(last)).is_dir():
            self.set_root(Path(str(last)))

    def closeEvent(self, event) -> None:  # noqa: N802
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("splitter", self.splitter.sizes())
        for worker in list(self._workers):
            worker.wait(2000)
        super().closeEvent(event)
