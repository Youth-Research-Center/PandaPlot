"""Isolated, real application services and windows for GUI workflows."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox
from pytestqt.qtbot import QtBot

from pandaplot.app import build_app_context
from pandaplot.gui.main_window import PandaMainWindow
from pandaplot.services.autosave import AutoSaveManager
from pandaplot.services.theme import ThemeManager


@pytest.fixture
def app_window(qtbot: QtBot, qapp: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[PandaMainWindow]:
    # Config, recent projects, and session files must never touch the user's home.
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    original_palette = qapp.palette()
    original_font = qapp.font()
    original_stylesheet = qapp.styleSheet()
    context = build_app_context()
    theme = context.get_manager(ThemeManager)
    theme.set_qt_app(qapp)
    theme.apply_current()
    window = PandaMainWindow(context)
    context.ui_controller.set_parent_widget(window)

    def prepare_close(widget: PandaMainWindow) -> None:
        context.app_state.mark_saved()
        widget._is_closing = True

    qtbot.addWidget(window, before_close_func=prepare_close)
    qtbot.waitUntil(window.isVisible)
    messages = []
    window.test_dialog_errors = []
    window.test_messages = messages
    notice_timer = QTimer()

    def acknowledge_notice() -> None:
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            if dialog.icon() == QMessageBox.Icon.Information:
                messages.append((dialog.windowTitle(), dialog.text()))
                qtbot.mouseClick(dialog.button(QMessageBox.StandardButton.Ok), Qt.MouseButton.LeftButton)
            else:
                window.test_dialog_errors.append((dialog.windowTitle(), dialog.text()))
                dialog.reject()

    notice_timer.timeout.connect(acknowledge_notice)
    notice_timer.start(10)
    yield window
    try:
        notice_timer.stop()
        context.get_manager(AutoSaveManager).stop()
        context.task_scheduler.cancel_all()
        assert context.task_scheduler.threadpool.waitForDone(5000)
        qapp.processEvents()
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QDialog):
                widget.reject()
        # Teardown must not open a save/discard dialog for deliberate test edits.
        context.app_state.mark_saved()
        window._is_closing = True
        window.close()
    finally:
        qapp.setStyleSheet(original_stylesheet)
        qapp.setPalette(original_palette)
        qapp.setFont(original_font)
        assert not window.test_dialog_errors
