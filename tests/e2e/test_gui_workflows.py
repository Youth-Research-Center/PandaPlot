"""Golden paths through the real window, dialogs, commands and background import."""

from collections.abc import Callable
from pathlib import Path

import pytest
import shiboken6
from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox, QInputDialog, QLineEdit
from pytestqt.qtbot import QtBot

from pandaplot.commands.project.dataset.create_empty_dataset_command import CreateEmptyDatasetCommand
from pandaplot.gui.components.sidebar.project.project_view_panel import ProjectViewPanel
from pandaplot.gui.components.tabs.note.note_tab import NoteTab
from pandaplot.gui.components.tabs.sketch.sketch_tab import SketchTab
from pandaplot.gui.components.tabs.sketch.tools.tool_manager import ToolMode
from pandaplot.gui.components.tabs.tab_container import TabContainer
from pandaplot.gui.dialogs.chart.add_series_dialog import AddSeriesDialog
from pandaplot.gui.dialogs.chart.chart_wizard import ChartWizard
from pandaplot.gui.dialogs.examples_dialog import ExamplesDialog
from pandaplot.gui.dialogs.import_wizard_dialog import ImportWizardDialog
from pandaplot.gui.dialogs.sketch.export_sketch_dialog import ExportSketchDialog
from pandaplot.gui.main_window import PandaMainWindow
from pandaplot.models.project.items import Chart, Dataset, Sketch
from pandaplot.models.project.items.sketch import RectangleElement
from pandaplot.services.data_managers.project_manager import ProjectManager
from pandaplot.utils.examples import ExampleProject, discover_example_projects


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
    click_menu(qtbot, app_window, "Edit", app_window.main_menu.undo_action.text())
    qtbot.waitUntil(lambda: project.find_item(dataset.id) is None)
    assert app_window.main_menu.redo_action.isEnabled()
    click_menu(qtbot, app_window, "Edit", app_window.main_menu.redo_action.text())
    qtbot.waitUntil(lambda: project.find_item(dataset.id) is not None)
    restored = project.find_item(dataset.id)
    assert restored.data.to_dict("list") == {"x": [0, 1, 2], "y": [1, 3, 5]}
    assert not app_window.main_menu.redo_action.isEnabled()


def test_create_draw_save_and_reopen_a_sketch(app_window: PandaMainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    new_project(qtbot, app_window)
    click_menu(qtbot, app_window, "Data", "New Sketch")
    project = app_window.app_context.app_state.current_project
    assert project is not None
    sketch = next(item for item in project.get_all_items() if isinstance(item, Sketch))
    assert sketch.name == "New Sketch 1"

    panel = app_window.findChild(ProjectViewPanel)
    assert panel is not None
    tree = panel.tree
    row = next(
        tree_item for tree_item in tree.findItems("New Sketch 1", Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive)
        if tree_item.data(0, Qt.ItemDataRole.UserRole).get("id") == sketch.id
    )
    assert row.text(0) == "New Sketch 1"
    tree.scrollToItem(row)
    position = tree.visualItemRect(row).center()
    qtbot.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=position)
    qtbot.mouseDClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=position)
    tabs = app_window.app_context.get_manager(TabContainer)
    qtbot.waitUntil(lambda: tabs.get_tab_widget(sketch.id) is not None)
    tab = tabs.get_tab_widget(sketch.id)
    assert isinstance(tab, SketchTab)

    qtbot.mouseClick(tab.layer_panel.add_button, Qt.MouseButton.LeftButton)
    assert [layer.name for layer in sketch.layers] == ["Layer 1", "Layer 2"]
    assert sketch.active_layer_id == sketch.layers[1].id

    rectangle_button = tab.toolbar.widgetForAction(tab.tool_actions[ToolMode.RECTANGLE])
    qtbot.mouseClick(rectangle_button, Qt.MouseButton.LeftButton)
    tab.property_bar.width_input.setFocus()
    qtbot.keyClick(tab.property_bar.width_input.focusProxy(), Qt.Key.Key_PageUp)
    viewport = tab.canvas.viewport()
    start = tab.canvas.mapFromScene(QPointF(100.0, 100.0))
    end = tab.canvas.mapFromScene(QPointF(300.0, 200.0))
    qtbot.mousePress(viewport, Qt.MouseButton.LeftButton, pos=start)
    qtbot.mouseMove(viewport, pos=(start + end) / 2)
    qtbot.mouseMove(viewport, pos=end)
    qtbot.mouseRelease(viewport, Qt.MouseButton.LeftButton, pos=end)
    [box] = sketch.active_layer.elements
    assert isinstance(box, RectangleElement)
    assert (box.width, box.height) == pytest.approx((200.0, 100.0), abs=1.0 / tab.canvas.zoom)
    # PageUp in the property bar's width field: 2.0 plus ten 0.5 px steps.
    assert box.stroke_width == 7.0
    assert tab.canvas.element_item(box.id) is not None
    assert sketch.layers[0].elements == []
    qtbot.mouseClick(tab.layer_panel.rows[sketch.layers[1].id].lock_button, Qt.MouseButton.LeftButton)
    assert sketch.layers[1].locked

    exported_path = tmp_path / "sketch.png"
    monkeypatch.setattr(
        "pandaplot.gui.controllers.ui_controller.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(exported_path.with_suffix("")), "PNG image (*.png)"),
    )

    def export_half_size_transparent(dialog: ExportSketchDialog) -> None:
        qtbot.mouseClick(dialog.transparent_radio, Qt.MouseButton.LeftButton)
        dialog.scale_input.setValue(0.5)
        qtbot.mouseClick(dialog.export_button, Qt.MouseButton.LeftButton)

    timer, errors = drive_modal(qtbot, ExportSketchDialog, export_half_size_transparent)
    qtbot.mouseClick(tab.toolbar.widgetForAction(tab.export_action), Qt.MouseButton.LeftButton)
    timer.stop()
    assert not errors
    exported = QImage(str(exported_path))
    assert (exported.width(), exported.height()) == (round(sketch.canvas_width / 2), round(sketch.canvas_height / 2))
    assert exported.pixelColor(0, 0).alpha() == 0
    assert tab.status_label.text() == "Exported to sketch.png"

    saved_path = tmp_path / "sketch.pplot"
    monkeypatch.setattr(
        "pandaplot.gui.controllers.ui_controller.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(saved_path), "Project files"),
    )
    click_menu(qtbot, app_window, "File", "Save As...")
    # Wait on the file and the saved state, not the message box title: macOS
    # message boxes have no title (#501).
    qtbot.waitUntil(lambda: saved_path.exists() and not app_window.app_context.app_state.is_modified, timeout=10000)
    click_menu(qtbot, app_window, "File", "Close")
    assert tabs.get_tab_widget(sketch.id) is None
    monkeypatch.setattr(
        "pandaplot.gui.controllers.ui_controller.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (str(saved_path), "Project files"),
    )

    click_menu(qtbot, app_window, "File", "Open")
    qtbot.waitUntil(lambda: app_window.app_context.app_state.has_project, timeout=10000)
    reopened = app_window.app_context.app_state.current_project
    assert reopened is not None
    restored = reopened.find_item(sketch.id)
    assert isinstance(restored, Sketch)
    assert restored.to_dict() == sketch.to_dict()
    assert [(layer.name, layer.locked) for layer in restored.layers] == [("Layer 1", False), ("Layer 2", True)]


def test_empty_chart_gets_first_series_from_empty_state(
    app_window: PandaMainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    new_project(qtbot, app_window)
    dataset = import_csv(qtbot, app_window, monkeypatch, tmp_path)
    click_menu(qtbot, app_window, "Chart", "Create New")
    qtbot.waitUntil(lambda: any(isinstance(w, ChartWizard) and w.isVisible() for w in QApplication.topLevelWidgets()))
    wizard = next(w for w in QApplication.topLevelWidgets() if isinstance(w, ChartWizard) and w.isVisible())
    qtbot.mouseClick(wizard.type_page.footer.empty_link, Qt.MouseButton.LeftButton)
    project = app_window.app_context.app_state.current_project
    qtbot.waitUntil(lambda: any(isinstance(item, Chart) for item in project.get_all_items()))
    chart = next(item for item in project.get_all_items() if isinstance(item, Chart))
    assert chart.data_series == []
    tabs = app_window.app_context.get_manager(TabContainer)
    qtbot.waitUntil(lambda: tabs.get_tab_widget(chart.id) is not None)
    editor = tabs.get_tab_widget(chart.id).chart_editor
    qtbot.waitUntil(lambda: editor.preview_stack.currentWidget() is editor.empty_state_panel)

    add_series_button = next(button for button in editor.empty_state_panel.action_buttons if button.text() == "Add Series")
    clicked_dialogs: list[AddSeriesDialog] = []

    def complete_dialog() -> None:
        dialog = QApplication.activeModalWidget()
        if not isinstance(dialog, AddSeriesDialog) or dialog in clicked_dialogs:
            return
        try:
            assert dialog.card.dataset_combo.currentData() == dataset.id
            for role, column in (("x", "x"), ("y", "y")):
                combo = dialog.card._role_combos[role]
                index = combo.findData(dataset.column_id(column))
                assert index >= 0
                combo.setCurrentIndex(index)
            assert dialog.add_button.isEnabled()
            clicked_dialogs.append(dialog)
            qtbot.mouseClick(dialog.add_button, Qt.MouseButton.LeftButton)
        except AssertionError:
            dialog.reject()
            raise

    dialog_timer = QTimer()
    dialog_timer.timeout.connect(complete_dialog)
    dialog_timer.start(10)
    try:
        qtbot.mouseClick(add_series_button, Qt.MouseButton.LeftButton)
        qtbot.waitUntil(lambda: len(chart.data_series) == 1, timeout=10000)
    finally:
        dialog_timer.stop()
    assert len(clicked_dialogs) == 1
    assert chart.data_series[0].dataset_id == dataset.id
    assert chart.data_series[0].x_column_id == dataset.column_id("x")
    assert chart.data_series[0].y_column_id == dataset.column_id("y")
    qtbot.waitUntil(lambda: editor.preview_stack.currentWidget() is editor.canvas_scroll)
    qtbot.waitUntil(lambda: len(editor.chart_canvas.axes.lines) > 0)

    assert app_window.main_menu.undo_action.isEnabled()
    app_window.main_menu.undo_action.trigger()
    qtbot.waitUntil(lambda: chart.data_series == [])
    qtbot.waitUntil(lambda: editor.preview_stack.currentWidget() is editor.empty_state_panel)


def test_edit_project_details_from_the_file_menu_with_undo_and_redo(app_window: PandaMainWindow, qtbot: QtBot) -> None:
    from pandaplot.gui.dialogs.project.project_details_dialog import ProjectDetailsDialog

    new_project(qtbot, app_window)
    project = app_window.app_context.app_state.current_project
    original_description = project.description

    def edit(dialog: ProjectDetailsDialog) -> None:
        dialog.name_edit.setText("Renamed project")
        dialog.description_edit.setPlainText("Findings. More text.")
        dialog.example_checkbox.setChecked(True)
        dialog.tag_checkboxes["physics"].setChecked(True)
        qtbot.mouseClick(dialog.ok_button, Qt.MouseButton.LeftButton)

    timer, errors = drive_modal(qtbot, ProjectDetailsDialog, edit)
    click_menu(qtbot, app_window, "File", "Project Details...")
    timer.stop()
    assert not errors

    assert project.name == "Renamed project"
    assert project.description == "Findings. More text."
    assert project.example_info.is_example
    assert project.example_info.tag_ids == ("physics",)
    assert app_window.windowTitle().startswith("Renamed project")

    app_window.main_menu.undo_action.trigger()
    assert project.name == "GUI workflow"
    assert project.description == original_description
    assert not project.example_info.is_example
    assert app_window.windowTitle().startswith("GUI workflow")

    app_window.main_menu.redo_action.trigger()
    assert project.name == "Renamed project"
    assert project.example_info.tag_ids == ("physics",)


def test_example_opens_as_untitled_copy_and_save_never_overwrites_it(
    app_window: PandaMainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from pandaplot.services.session.recent_projects import get_recent_projects
    from pandaplot.utils.examples import discover_example_projects

    example = Path(discover_example_projects()[0].path)
    original_bytes = example.read_bytes()
    state = app_window.app_context.app_state

    app_window.tab_container.command_manager.handle_example_project(str(example))
    qtbot.waitUntil(lambda: state.has_project, timeout=10000)
    project = state.current_project
    assert project.project_file_path is None
    assert project.name
    assert not state.is_modified
    assert str(example) not in [entry["path"] for entry in get_recent_projects(app_window.app_context)]

    executed = app_window.app_context.get_command_executor().execute_command(
        CreateEmptyDatasetCommand(app_window.app_context, dataset_name="Edit after opening")
    )
    assert executed
    assert state.is_modified
    assert state.project_file_path is None
    saved_path = tmp_path / "my_copy.pplot"
    dialog_calls: list[tuple[object, ...]] = []

    def pick_path(*args: object, **kwargs: object) -> tuple[str, str]:
        dialog_calls.append(args)
        return str(saved_path), "Project files"

    monkeypatch.setattr("pandaplot.gui.controllers.ui_controller.QFileDialog.getSaveFileName", pick_path)

    click_menu(qtbot, app_window, "File", "Save")
    qtbot.waitUntil(lambda: any(title == "Project Saved" for title, _ in app_window.test_messages), timeout=10000)

    assert len(dialog_calls) == 1
    assert saved_path.exists()
    assert state.project_file_path == str(saved_path)
    assert example.read_bytes() == original_bytes


def test_closing_an_edited_example_offers_save_as_and_clears_the_recovery_copy(
    app_window: PandaMainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from pandaplot.services.autosave import AutoSaveManager
    from pandaplot.services.autosave.recovery import session_recovery_path
    from pandaplot.utils.examples import discover_example_projects

    example = Path(discover_example_projects()[0].path)
    context = app_window.app_context
    state = context.app_state

    app_window.tab_container.command_manager.handle_example_project(str(example))
    qtbot.waitUntil(lambda: state.has_project, timeout=10000)
    assert context.get_command_executor().execute_command(
        CreateEmptyDatasetCommand(context, dataset_name="Edit after opening")
    )
    assert state.is_modified
    assert state.project_file_path is None

    manager = context.get_manager(AutoSaveManager)
    manager._on_timer()
    qtbot.waitUntil(lambda: not manager._recovery_write_in_flight, timeout=10000)

    assert session_recovery_path().is_file()
    assert state.project_file_path is None
    assert state.is_modified

    saved_path = tmp_path / "closed_with_save_as.pplot"
    prompts: list[tuple[str, str]] = []

    def answer_save_as(title: str, message: str) -> str:
        prompts.append((title, message))
        return "save_as"

    monkeypatch.setattr(context.ui_controller, "show_save_as_discard_cancel", answer_save_as)
    monkeypatch.setattr(
        "pandaplot.gui.controllers.ui_controller.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(saved_path), "Project files"),
    )

    assert app_window.close()

    assert len(prompts) == 1
    assert saved_path.is_file()
    assert state.project_file_path == str(saved_path)
    assert not state.is_modified
    assert not session_recovery_path().exists()
    reopened = context.get_manager(ProjectManager).load_project(str(saved_path))
    assert any(item.name == "Edit after opening" for item in reopened.get_all_items())


def _open_example_start_note(app_window: PandaMainWindow, qtbot: QtBot, stem: str, previous: object) -> tuple[object, str]:
    """Open the bundled example `stem` and its "Start here" note tab; return the loaded project and the note id."""
    from pandaplot.models.project.items import Note
    from pandaplot.utils.examples import discover_example_projects

    example = next(e for e in discover_example_projects() if Path(e.path).stem == stem)
    state = app_window.app_context.app_state
    app_window.tab_container.command_manager.handle_example_project(example.path)
    qtbot.waitUntil(lambda: state.current_project is not None and state.current_project is not previous, timeout=10000)
    project = state.current_project
    note = next(i for i in project.get_all_items() if isinstance(i, Note) and i.name == "Start here")
    app_window.tab_container.open_tab(note.id)
    return project, note.id


def _tab_title(tab_container: TabContainer, item_id: str) -> str:
    widget = tab_container.tabs[item_id]
    pane = tab_container._pane_of(widget)
    return pane.tabText(pane.indexOf(widget))


def test_opening_another_example_closes_the_previous_projects_tabs(app_window: PandaMainWindow, qtbot: QtBot) -> None:
    tab_container = app_window.tab_container

    first, first_note_id = _open_example_start_note(app_window, qtbot, "basic_statistics", previous=None)
    first_widget = tab_container.tabs[first_note_id]

    _second, second_note_id = _open_example_start_note(app_window, qtbot, "Functions", previous=first)

    assert first_note_id not in tab_container.tabs
    assert not shiboken6.isValid(first_widget) or tab_container._pane_of(first_widget) is None
    assert set(tab_container.tabs) == {second_note_id}
    assert tab_container._active_pane.currentWidget() is tab_container.tabs[second_note_id]


def test_reopening_the_same_example_gives_a_note_tab_bound_to_the_live_project(
    app_window: PandaMainWindow, qtbot: QtBot
) -> None:
    from pandaplot.commands.project.item.rename_item_command import RenameItemCommand

    context = app_window.app_context
    state = context.app_state
    tab_container = app_window.tab_container

    first, note_id = _open_example_start_note(app_window, qtbot, "basic_statistics", previous=None)
    old_title = _tab_title(tab_container, note_id)
    stale_widget = tab_container.tabs[note_id]

    _second, same_note_id = _open_example_start_note(app_window, qtbot, "basic_statistics", previous=first)

    assert same_note_id == note_id
    tab = tab_container.tabs[note_id]
    assert tab is not stale_widget
    assert tab.note is state.current_project.find_item(note_id)

    assert context.get_command_executor().execute_command(RenameItemCommand(context, note_id, "Renamed"))

    assert _tab_title(tab_container, note_id) == "Renamed"
    assert not any(
        pane.tabText(i) == old_title for pane in tab_container.panes for i in range(pane.count())
    )


def test_undoing_an_example_load_closes_the_undone_projects_tabs(app_window: PandaMainWindow, qtbot: QtBot) -> None:
    from pandaplot.commands.project.item.rename_item_command import RenameItemCommand

    context = app_window.app_context
    state = context.app_state
    tab_container = app_window.tab_container

    first, note_id = _open_example_start_note(app_window, qtbot, "basic_statistics", previous=None)
    old_title = _tab_title(tab_container, note_id)
    second, _ = _open_example_start_note(app_window, qtbot, "basic_statistics", previous=first)
    assert context.get_command_executor().execute_command(RenameItemCommand(context, note_id, "Renamed"))
    assert _tab_title(tab_container, note_id) == "Renamed"

    click_menu(qtbot, app_window, "Edit", app_window.main_menu.undo_action.text())

    assert state.current_project is second
    assert _tab_title(tab_container, note_id) == old_title

    click_menu(qtbot, app_window, "Edit", app_window.main_menu.undo_action.text())

    assert state.current_project is first
    assert tab_container.tabs == {}


def _example_named(name: str) -> ExampleProject:
    return next(example for example in discover_example_projects() if example.name == name)


def _assert_start_note_open(app_window: PandaMainWindow, qtbot: QtBot, example: ExampleProject) -> None:
    state = app_window.app_context.app_state
    tabs = app_window.tab_container
    note_id = example.start_note_id
    assert note_id is not None

    qtbot.waitUntil(lambda: isinstance(tabs.get_tab_widget(note_id), NoteTab), timeout=10000)

    tab = tabs.get_tab_widget(note_id)
    assert isinstance(tab, NoteTab)
    assert len(tabs.panes) == 1
    assert tabs.panes[0].currentWidget() is tab
    assert state.current_project is not None
    assert tab.note is state.current_project.find_item(note_id)
    assert not state.is_modified


def test_opening_an_example_from_the_welcome_tab_shows_its_start_note(app_window: PandaMainWindow, qtbot: QtBot) -> None:
    example = _example_named("Basic Statistics")

    app_window.tab_container.command_manager.handle_example_project(example.path)

    _assert_start_note_open(app_window, qtbot, example)
    assert example.start_note_id is not None
    tab = app_window.tab_container.get_tab_widget(example.start_note_id)
    assert isinstance(tab, NoteTab)
    assert tab.note.name == "Start here"


def test_opening_an_example_from_the_help_menu_shows_its_start_note(app_window: PandaMainWindow, qtbot: QtBot) -> None:
    example = _example_named("Curve Fitting Examples")

    def pick(dialog: QDialog) -> None:
        assert isinstance(dialog, ExamplesDialog)
        card = next(card for card in dialog.cards if card.example.path == example.path)
        qtbot.mouseClick(card.open_button, Qt.MouseButton.LeftButton)

    timer, errors = drive_modal(qtbot, ExamplesDialog, pick)
    click_menu(qtbot, app_window, "Help", "Open Example Project...")
    timer.stop()

    assert not errors
    _assert_start_note_open(app_window, qtbot, example)


def test_declining_to_replace_a_modified_project_opens_no_example_tab(
    app_window: PandaMainWindow, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    example = _example_named("Basic Statistics")
    context = app_window.app_context
    state = context.app_state
    tabs = app_window.tab_container
    new_project(qtbot, app_window)
    assert context.get_command_executor().execute_command(CreateEmptyDatasetCommand(context, dataset_name="Edit"))
    assert state.is_modified
    before = state.current_project
    tabs_before = set(tabs.tabs)
    prompts: list[str] = []

    def cancel(title: str, message: str) -> str:
        prompts.append(title)
        return "cancel"

    monkeypatch.setattr(context.ui_controller, "show_save_as_discard_cancel", cancel)

    tabs.command_manager.handle_example_project(example.path)

    assert prompts == ["Open Project"]
    assert state.current_project is before
    assert set(tabs.tabs) == tabs_before
