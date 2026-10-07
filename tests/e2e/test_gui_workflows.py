"""Golden paths through the real window, dialogs, commands and background import."""

from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QInputDialog, QLineEdit
from pytestqt.qtbot import QtBot

from pandaplot.gui.components.tabs.tab_container import TabContainer
from pandaplot.gui.dialogs.chart.chart_wizard import ChartWizard
from pandaplot.gui.dialogs.import_wizard_dialog import ImportWizardDialog
from pandaplot.gui.main_window import PandaMainWindow
from pandaplot.models.project.items import Chart, Dataset


def click_menu(qtbot: QtBot, window: PandaMainWindow, menu_name: str, action_name: str) -> None:
    menu = next(action.menu() for action in window.main_menu.actions() if action.text() == menu_name)
    action = next(action for action in menu.actions() if action.text() == action_name)
    assert action.isEnabled()
    menu.popup(window.mapToGlobal(window.rect().center()))
    qtbot.waitUntil(menu.isVisible)
    qtbot.mouseClick(menu, Qt.MouseButton.LeftButton, pos=menu.actionGeometry(action).center())


def drive_modal(qtbot: QtBot, dialog_type: type[QDialog], interact: Callable[[QDialog], None]) -> tuple[QTimer, list[Exception]]:
    """Run inside exec()'s event loop; reject on failure rather than hang pytest."""
    errors = []
    timer = QTimer()
    timer.setInterval(10)
    attempts = 0

    def poll() -> None:
        nonlocal attempts
        attempts += 1
        dialog = QApplication.activeModalWidget()
        if isinstance(dialog, dialog_type):
            timer.stop()
            try:
                interact(dialog)
            except Exception as error:  # noqa: BLE001 - return Qt callback failures to pytest
                errors.append(error)
                dialog.reject()
        elif attempts >= 500:
            timer.stop()
            errors.append(AssertionError(f"{dialog_type.__name__} did not open"))
            if dialog is not None:
                dialog.reject()

    timer.timeout.connect(poll)
    timer.start()
    return timer, errors


def new_project(qtbot: QtBot, window: PandaMainWindow) -> None:
    def enter_name(dialog: QInputDialog) -> None:
        edit = dialog.findChild(QLineEdit)
        edit.selectAll()
        qtbot.keyClicks(edit, "GUI workflow")
        buttons = dialog.findChild(QDialogButtonBox)
        qtbot.mouseClick(buttons.button(QDialogButtonBox.StandardButton.Ok), Qt.MouseButton.LeftButton)

    timer, errors = drive_modal(qtbot, QInputDialog, enter_name)
    click_menu(qtbot, window, "File", "New")
    timer.stop()
    assert not errors
    assert window.app_context.app_state.current_project.name == "GUI workflow"


def import_csv(qtbot: QtBot, window: PandaMainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Dataset:
    path = tmp_path / "measurements.csv"
    path.write_text("x,y\n0,1\n1,3\n2,5\n", encoding="utf-8")
    # Only the platform file picker is replaced; preview, wizard and worker are real.
    monkeypatch.setattr(
        "pandaplot.gui.dialogs.import_wizard_dialog.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(path), "CSV"),
    )

    def confirm_import(dialog: ImportWizardDialog) -> None:
        qtbot.mouseClick(dialog.browse_button, Qt.MouseButton.LeftButton)
        assert dialog.preview_table.rowCount() == 3
        assert dialog.preview_table.columnCount() == 2
        assert dialog.import_button.isEnabled()
        qtbot.mouseClick(dialog.import_button, Qt.MouseButton.LeftButton)

    timer, errors = drive_modal(qtbot, ImportWizardDialog, confirm_import)
    click_menu(qtbot, window, "Data", "Import Data...")
    timer.stop()
    assert not errors
    project = window.app_context.app_state.current_project
    qtbot.waitUntil(lambda: any(isinstance(item, Dataset) for item in project.get_all_items()), timeout=10000)
    qtbot.waitUntil(lambda: any("Successfully imported" in text for _, text in window.test_messages), timeout=10000)
    dataset = next(item for item in project.get_all_items() if isinstance(item, Dataset))
    assert dataset.data.to_dict("list") == {"x": [0, 1, 2], "y": [1, 3, 5]}
    return dataset


def test_create_import_save_and_reopen_project(app_window: PandaMainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    new_project(qtbot, app_window)
    dataset = import_csv(qtbot, app_window, monkeypatch, tmp_path)
    assert app_window.app_context.app_state.is_modified
    assert app_window.main_menu.undo_action.isEnabled()
    assert dataset.name == "measurements"
    saved_path = tmp_path / "workflow.pplot"
    monkeypatch.setattr(
        "pandaplot.gui.controllers.ui_controller.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(saved_path), "Project files"),
    )

    click_menu(qtbot, app_window, "File", "Save As...")
    qtbot.waitUntil(lambda: any(title == "Project Saved" for title, _ in app_window.test_messages), timeout=10000)
    assert saved_path.exists()
    assert not app_window.app_context.app_state.is_modified
    click_menu(qtbot, app_window, "File", "Close")
    assert not app_window.app_context.app_state.has_project
    monkeypatch.setattr(
        "pandaplot.gui.controllers.ui_controller.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(saved_path), "Project files"),
    )

    click_menu(qtbot, app_window, "File", "Open")
    qtbot.waitUntil(lambda: app_window.app_context.app_state.has_project, timeout=10000)
    loaded = app_window.app_context.app_state.current_project
    assert loaded.name == "GUI workflow"
    restored = loaded.find_item(dataset.id)
    assert isinstance(restored, Dataset)
    assert restored.data.to_dict("list") == {"x": [0, 1, 2], "y": [1, 3, 5]}


def test_create_chart_from_imported_data(app_window: PandaMainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    new_project(qtbot, app_window)
    dataset = import_csv(qtbot, app_window, monkeypatch, tmp_path)
    click_menu(qtbot, app_window, "Chart", "Create New")
    qtbot.waitUntil(lambda: any(isinstance(w, ChartWizard) and w.isVisible() for w in QApplication.topLevelWidgets()))
    wizard = next(w for w in QApplication.topLevelWidgets() if isinstance(w, ChartWizard) and w.isVisible())
    qtbot.mouseClick(wizard.type_page.footer.next_button, Qt.MouseButton.LeftButton)
    card = wizard.data_page.cards[0]
    assert card.dataset_combo.currentData() == dataset.id
    for role, column in (("x", "x"), ("y", "y")):
        combo = card._role_combos[role]
        combo.setFocus()
        qtbot.keyClick(combo, Qt.Key.Key_Home)
        index = combo.findData(dataset.column_id(column))
        assert index >= 0
        for _ in range(index):
            qtbot.keyClick(combo, Qt.Key.Key_Down)
        assert combo.currentData() == dataset.column_id(column)
    assert wizard.data_page.footer.next_button.isEnabled()
    qtbot.mouseClick(wizard.data_page.footer.next_button, Qt.MouseButton.LeftButton)
    wizard.labels_page.title_edit.selectAll()
    qtbot.keyClicks(wizard.labels_page.title_edit, "Measured line")
    qtbot.mouseClick(wizard.labels_page.footer.finish_button, Qt.MouseButton.LeftButton)
    project = app_window.app_context.app_state.current_project
    qtbot.waitUntil(lambda: any(isinstance(item, Chart) for item in project.get_all_items()))
    chart = next(item for item in project.get_all_items() if isinstance(item, Chart))
    assert chart.name == "Measured line"
    assert len(chart.data_series) == 1
    assert chart.data_series[0].dataset_id == dataset.id
    assert chart.data_series[0].x_column_id == dataset.column_id("x")
    assert chart.data_series[0].y_column_id == dataset.column_id("y")
    tabs = app_window.app_context.get_manager(TabContainer)
    qtbot.waitUntil(lambda: tabs.get_tab_widget(chart.id) is not None)
    tab = tabs.get_tab_widget(chart.id)
    canvas = tab.chart_editor.chart_canvas
    qtbot.waitUntil(lambda: len(canvas.axes.lines) > 0)
    line = canvas.axes.lines[0]
    assert list(line.get_xdata()) == [0, 1, 2]
    assert list(line.get_ydata()) == [1, 3, 5]


def test_undo_redo_import_through_edit_menu(app_window: PandaMainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    new_project(qtbot, app_window)
    dataset = import_csv(qtbot, app_window, monkeypatch, tmp_path)
    project = app_window.app_context.app_state.current_project
    click_menu(qtbot, app_window, "Edit", "Undo")
    qtbot.waitUntil(lambda: project.find_item(dataset.id) is None)
    assert app_window.main_menu.redo_action.isEnabled()
    click_menu(qtbot, app_window, "Edit", "Redo")
    qtbot.waitUntil(lambda: project.find_item(dataset.id) is not None)
    restored = project.find_item(dataset.id)
    assert restored.data.to_dict("list") == {"x": [0, 1, 2], "y": [1, 3, 5]}
    assert not app_window.main_menu.redo_action.isEnabled()
