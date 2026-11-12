"""Isolated, real application services and windows for GUI workflows."""

import gc
from collections.abc import Iterator

import pytest
import shiboken6
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QWidget
from pytestqt.qtbot import QtBot

from pandaplot.app import build_app_context
from pandaplot.gui.main_window import PandaMainWindow
from pandaplot.services.autosave import AutoSaveManager
from pandaplot.services.theme import ThemeManager
from pandaplot.utils.garbage_collection import paused_garbage_collection


def flush_deferred_deletes() -> None:
    """Run pending ``deleteLater()`` calls; ``processEvents()`` leaves ``DeferredDelete`` events queued."""
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def discard_widget(widget: QWidget) -> None:
    """Delete a top-level widget and everything Python still holds for it, before the next test starts."""
    if shiboken6.isValid(widget):
        widget.deleteLater()
    for _ in range(3):
        flush_deferred_deletes()
        gc.collect()
    flush_deferred_deletes()


def top_level_widget_addresses() -> set[int]:
    """Identify the live top-level widgets by C++ address, without keeping their Python wrappers alive."""
    return {shiboken6.getCppPointer(widget)[0] for widget in QApplication.topLevelWidgets()}


def assert_no_stray_top_level_widgets(existing: set[int]) -> None:
    """Fail if the test left a top-level widget (window, dialog, popup menu) alive that did not exist before it.

    A stale widget is re-polished by every later ``QApplication.setStyleSheet`` and, if it was half-destroyed, can crash
    the worker (issue #648). Parent widgets and menus to the widget that owns them so Qt deletes them with it. Widgets
    that other test files on the same xdist worker left behind are not this test's concern.
    """
    strays = [
        f"{type(widget).__name__} ({widget.windowTitle() or widget.objectName() or 'untitled'})"
        for widget in QApplication.topLevelWidgets()
        if shiboken6.getCppPointer(widget)[0] not in existing
    ]
    assert not strays, f"Top-level widgets survived the test: {strays}"


@pytest.fixture
def app_window(qtbot: QtBot, qapp: QApplication) -> Iterator[PandaMainWindow]:
    # Config, recent projects, and session files stay out of the user's home through
    # the autouse isolated_home fixture in tests/conftest.py.
    top_level_before = top_level_widget_addresses()
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
    dialog_errors: list[tuple[str, str, str]] = []
    window.test_dialog_errors = dialog_errors
    window.test_messages = messages
    notice_timer = QTimer()

    def acknowledge_notice() -> None:
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, QMessageBox):
            if dialog.icon() == QMessageBox.Icon.Information:
                messages.append((dialog.windowTitle(), dialog.text()))
                qtbot.mouseClick(dialog.button(QMessageBox.StandardButton.Ok), Qt.MouseButton.LeftButton)
            else:
                dialog_errors.append((dialog.windowTitle(), dialog.text(), dialog.informativeText()))
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
        # Destroy the window now, so the next test's stylesheet change never re-polishes a closed window that is
        # still waiting for its deferred delete (issue #648).
        discard_widget(window)
        with paused_garbage_collection():
            qapp.setStyleSheet(original_stylesheet)
            qapp.setPalette(original_palette)
            qapp.setFont(original_font)
        assert not dialog_errors
    assert_no_stray_top_level_widgets(top_level_before)
