"""Headless GUI tests: the window builds, previews, applies and undoes."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PySide6 = pytest.importorskip("PySide6")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from seqrename.gui import dialogs, theme  # noqa: E402
from seqrename.gui.main_window import MainWindow  # noqa: E402


@pytest.fixture(scope="session")
def app(tmp_path_factory):
    # Keep the test run out of the user's real settings.
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(
        QSettings.IniFormat, QSettings.UserScope, str(tmp_path_factory.mktemp("settings"))
    )
    instance = QApplication.instance() or QApplication([])
    theme.apply(instance)
    return instance


@pytest.fixture
def seq_dir(tmp_path):
    for n in range(1001, 1006):
        (tmp_path / f"shot_comp_v001.{n:04d}.exr").write_bytes(b"x" * 64)
    return tmp_path


def settle(app, window, cycles: int = 40):
    """Let the debounce timer fire and background workers finish."""
    window._debounce.stop()
    window._rebuild_preview()
    for _ in range(cycles):
        for worker in list(window._workers):
            worker.wait(1000)
        app.processEvents()


def test_window_scans_and_previews(app, seq_dir):
    window = MainWindow(str(seq_dir))
    for _ in range(20):
        app.processEvents()
    assert window.sequence_list.count() == 1

    window.ops.find.setText("v001")
    window.ops.replace.setText("v002")
    settle(app, window)

    assert window.plan is not None
    assert len(window.plan.actionable) == 5
    assert window.apply_button.isEnabled()
    assert window.table.model_.rowCount() == 5
    window.close()


def test_apply_then_undo(app, seq_dir, monkeypatch):
    monkeypatch.setattr(dialogs.ConfirmDialog, "exec", lambda self: QDialog.Accepted)

    window = MainWindow(str(seq_dir))
    for _ in range(20):
        app.processEvents()

    window.ops.repad.setChecked(True)
    window.ops.pad.setValue(6)
    settle(app, window)
    assert len(window.plan.actionable) == 5

    window.apply()
    for _ in range(60):
        for worker in list(window._workers):
            worker.wait(2000)
        app.processEvents()

    assert sorted(p.name for p in seq_dir.glob("*.exr")) == [
        f"shot_comp_v001.{n:06d}.exr" for n in range(1001, 1006)
    ]
    assert window.undo_button.isEnabled()

    window.undo_last()
    for _ in range(60):
        for worker in list(window._workers):
            worker.wait(2000)
        app.processEvents()

    assert sorted(p.name for p in seq_dir.glob("*.exr")) == [
        f"shot_comp_v001.{n:04d}.exr" for n in range(1001, 1006)
    ]
    window.close()
