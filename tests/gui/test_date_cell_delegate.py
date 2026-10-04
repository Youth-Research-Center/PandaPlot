"""Date editors commit through the real model, events and undo executor."""

from unittest.mock import Mock

import pandas as pd
import pytest
from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import QCalendarWidget, QLineEdit, QTableView

from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.gui.components.tabs.dataset.dataset_table_view import DatasetTableView
from pandaplot.gui.components.tabs.dataset.date_cell_delegate import DateCellEditor
from pandaplot.gui.components.tabs.dataset.pandas_table_model import PandasTableModel
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events import EventBus
from pandaplot.models.project import Project
from pandaplot.models.project.items import Dataset
from pandaplot.models.state import AppState


@pytest.fixture
def table(qtbot):
    data = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-09-01 12:34:56.123456789", None]),
            "number": [1.5, 2.5],
            "text": ["a", "b"],
        }
    )
    dataset = Dataset(id="dates", name="Dates", data=data)
    bus = EventBus()
    state = AppState(bus)
    project = Project(name="Dates")
    project.add_item(dataset)
    state.load_project(project)
    context = Mock()
    context.event_bus = bus
    context.app_state = state
    context.get_app_state.return_value = state
    context.command_executor = CommandExecutor(on_project_modified=state.mark_modified)
    context.get_ui_controller.return_value = Mock(spec=UIController)
    model = PandasTableModel(context, dataset)
    view = DatasetTableView(context, model)
    qtbot.addWidget(view)
    view.resize(600, 250)
    view.show()
    yield view, model, dataset, context.command_executor
    model.unsubscribe_all()


def edit_cell(qtbot, view, model, row=0, column=0):
    index = model.index(row, column)
    view.setCurrentIndex(index)
    view.edit(index)
    qtbot.waitUntil(lambda: view.findChild(DateCellEditor) is not None)
    return view.findChild(DateCellEditor)


def test_typed_date_preserves_dtype_and_undo_redo(table, qtbot):
    view, model, dataset, executor = table
    old = dataset.data.iloc[0, 0]
    dtype = dataset.data.dtypes.iloc[0]
    editor = edit_cell(qtbot, view, model)
    editor.text.selectAll()
    qtbot.keyClicks(editor.text, "2026-10-02 09:45:00")
    qtbot.keyClick(editor.text, Qt.Key.Key_Return)
    assert dataset.data.iloc[0, 0] == pd.Timestamp("2026-10-02 09:45:00")
    assert dataset.data.dtypes.iloc[0] == dtype
    executor.undo()
    assert dataset.data.iloc[0, 0] == old
    executor.redo()
    assert dataset.data.iloc[0, 0] == pd.Timestamp("2026-10-02 09:45:00")


def test_calendar_selection_preserves_time_and_precision(table, qtbot):
    view, model, dataset, _ = table
    editor = edit_cell(qtbot, view, model)
    qtbot.mouseClick(editor.button, Qt.MouseButton.LeftButton)
    popup = editor.calendar_dialog
    calendar = popup.findChild(QCalendarWidget)
    assert calendar.isVisible()
    grid = calendar.findChild(QTableView, "qt_calendar_calendarview")
    cells = [grid.model().index(row, col) for row in range(1, grid.model().rowCount()) for col in range(1, grid.model().columnCount())]
    target = next(index for index in cells if index.data() == 2)
    qtbot.mouseClick(grid.viewport(), Qt.MouseButton.LeftButton, pos=grid.visualRect(target).center())
    assert not popup.isVisible()
    assert dataset.data.iloc[0, 0] == pd.Timestamp("2026-09-02 12:34:56.123456789")


def test_blank_clears_and_nat_round_trips(table):
    _, model, dataset, executor = table
    old = dataset.data.iloc[0, 0]
    dtype = dataset.data.dtypes.iloc[0]
    assert model.setData(model.index(0, 0), "")
    assert pd.isna(dataset.data.iloc[0, 0])
    assert dataset.data.dtypes.iloc[0] == dtype
    executor.undo()
    assert dataset.data.iloc[0, 0] == old
    executor.redo()
    assert pd.isna(dataset.data.iloc[0, 0])
    assert model.setData(model.index(1, 0), "2026-10-01")
    assert dataset.data.iloc[1, 0] == pd.Timestamp("2026-10-01")


def test_invalid_input_leaves_data_and_history_unchanged(table, qtbot):
    view, model, dataset, executor = table
    old = dataset.data.iloc[0, 0]
    editor = edit_cell(qtbot, view, model)
    editor.text.selectAll()
    qtbot.keyClicks(editor.text, "not a date")
    qtbot.keyClick(editor.text, Qt.Key.Key_Return)
    assert dataset.data.iloc[0, 0] == old
    assert not executor.can_undo()
    assert editor.isVisible()
    assert not model.setData(model.index(0, 0), "2026-09-01T00:00:00Z")


@pytest.mark.parametrize("value", ["2026-11-01 01:30:00", "2026-03-08 02:30:00", "bad date"])
def test_timezone_rejects_ambiguous_nonexistent_and_invalid(table, value):
    _, model, dataset, executor = table
    dataset.data["date"] = pd.Series(pd.to_datetime(["2026-09-01 12:34:56", None])).dt.tz_localize("America/New_York")
    old = dataset.data.iloc[0, 0]
    assert not model.setData(model.index(0, 0), value)
    assert dataset.data.iloc[0, 0] == old
    assert not executor.can_undo()


def test_timezone_local_entry_and_explicit_offset_preserve_dtype(table):
    _, model, dataset, executor = table
    dataset.data["date"] = pd.Series(pd.to_datetime(["2026-09-01 12:34:56", None])).dt.tz_localize("America/New_York")
    dtype = dataset.data.dtypes.iloc[0]
    assert model.setData(model.index(0, 0), "2026-12-01 12:34:56")
    assert dataset.data.iloc[0, 0] == pd.Timestamp("2026-12-01 12:34:56", tz="America/New_York")
    assert model.setData(model.index(0, 0), "2026-12-01T18:34:56+01:00")
    assert dataset.data.iloc[0, 0].hour == 12
    assert dataset.data.dtypes.iloc[0] == dtype
    executor.undo()
    assert dataset.data.dtypes.iloc[0] == dtype


@pytest.mark.parametrize("column", [1, 2])
def test_non_date_editor_uses_qt_default(table, qtbot, column):
    view, model, _, _ = table
    index = model.index(0, column)
    view.edit(index)
    qtbot.waitUntil(lambda: any(widget.isVisible() for widget in view.findChildren(QLineEdit)))
    assert view.findChild(DateCellEditor) is None


def test_calendar_click_with_unparseable_text_uses_date_only(table, qtbot):
    view, model, dataset, _ = table
    editor = edit_cell(qtbot, view, model)
    editor.text.setText("not a date")
    qtbot.mouseClick(editor.button, Qt.MouseButton.LeftButton)
    popup = editor.calendar_dialog
    calendar = popup.findChild(QCalendarWidget)
    calendar.setSelectedDate(QDate(2026, 10, 1))
    grid = calendar.findChild(QTableView, "qt_calendar_calendarview")
    target = next(
        grid.model().index(row, col)
        for row in range(grid.model().rowCount())
        for col in range(grid.model().columnCount())
        if grid.model().index(row, col).data() == 1
    )
    qtbot.mouseClick(grid.viewport(), Qt.MouseButton.LeftButton, pos=grid.visualRect(target).center())
    assert dataset.data.iloc[0, 0] == pd.Timestamp("2026-10-01")


def test_calendar_selection_on_timezone_column_null_cell(table, qtbot):
    view, model, dataset, _ = table
    dataset.data["date"] = pd.Series(pd.to_datetime([None, None])).dt.tz_localize("America/New_York")
    editor = edit_cell(qtbot, view, model, row=1)
    qtbot.mouseClick(editor.button, Qt.MouseButton.LeftButton)
    popup = editor.calendar_dialog
    calendar = popup.findChild(QCalendarWidget)
    calendar.setSelectedDate(QDate(2026, 10, 1))
    grid = calendar.findChild(QTableView, "qt_calendar_calendarview")
    target = next(
        grid.model().index(row, col)
        for row in range(grid.model().rowCount())
        for col in range(grid.model().columnCount())
        if grid.model().index(row, col).data() == 1
    )
    qtbot.mouseClick(grid.viewport(), Qt.MouseButton.LeftButton, pos=grid.visualRect(target).center())
    assert dataset.data.iloc[1, 0] == pd.Timestamp("2026-10-01", tz="America/New_York")


def test_calendar_out_of_range_date_is_rejected_without_history(table, qtbot):
    view, model, dataset, executor = table
    original = dataset.data.iloc[0, 0]
    editor = edit_cell(qtbot, view, model)
    editor.text.setText("9999-01-01")
    qtbot.mouseClick(editor.button, Qt.MouseButton.LeftButton)
    popup = editor.calendar_dialog
    calendar = popup.findChild(QCalendarWidget)
    calendar.setSelectedDate(QDate(9999, 1, 1))
    editor.select_date(calendar.selectedDate(), popup)
    assert dataset.data.iloc[0, 0] == original
    assert not executor.can_undo()
    assert editor.isVisible()


def test_calendar_on_null_cell_sets_midnight_and_undo_restores_nat(table, qtbot):
    view, model, dataset, executor = table
    editor = edit_cell(qtbot, view, model, row=1)
    assert editor.text.text() == ""
    qtbot.mouseClick(editor.button, Qt.MouseButton.LeftButton)
    popup = editor.calendar_dialog
    calendar = popup.findChild(QCalendarWidget)
    calendar.setSelectedDate(QDate(2026, 10, 1))
    grid = calendar.findChild(QTableView, "qt_calendar_calendarview")
    qtbot.mouseClick(grid.viewport(), Qt.MouseButton.LeftButton, pos=grid.visualRect(grid.currentIndex()).center())
    assert dataset.data.iloc[1, 0] == pd.Timestamp("2026-10-01")
    executor.undo()
    assert pd.isna(dataset.data.iloc[1, 0])


def test_calendar_recalculates_timezone_offset_across_dst(table, qtbot):
    view, model, dataset, executor = table
    dataset.data["date"] = pd.Series(pd.to_datetime(["2026-09-01 12:34:56.123456789", None])).dt.tz_localize("America/New_York")
    dtype = dataset.data.dtypes.iloc[0]
    original = dataset.data.iloc[0, 0]
    editor = edit_cell(qtbot, view, model)
    qtbot.mouseClick(editor.button, Qt.MouseButton.LeftButton)
    popup = editor.calendar_dialog
    calendar = popup.findChild(QCalendarWidget)
    calendar.setSelectedDate(QDate(2026, 12, 1))
    grid = calendar.findChild(QTableView, "qt_calendar_calendarview")
    qtbot.mouseClick(grid.viewport(), Qt.MouseButton.LeftButton, pos=grid.visualRect(grid.currentIndex()).center())
    assert dataset.data.iloc[0, 0] == pd.Timestamp("2026-12-01 12:34:56.123456789", tz="America/New_York")
    assert dataset.data.dtypes.iloc[0] == dtype
    executor.undo()
    assert dataset.data.iloc[0, 0] == original
    executor.redo()
    assert dataset.data.dtypes.iloc[0] == dtype


def test_escape_cancels_without_history(table, qtbot):
    view, model, dataset, executor = table
    original = dataset.data.iloc[0, 0]
    editor = edit_cell(qtbot, view, model)
    editor.text.selectAll()
    qtbot.keyClicks(editor.text, "2026-10-01")
    qtbot.keyClick(editor.text, Qt.Key.Key_Escape)
    assert dataset.data.iloc[0, 0] == original
    assert not executor.can_undo()


def test_unchanged_and_out_of_range_dates_do_not_add_history(table):
    _, model, dataset, executor = table
    assert model.setData(model.index(0, 0), str(dataset.data.iloc[0, 0]))
    assert not executor.can_undo()
    assert not model.setData(model.index(0, 0), "9999-01-01")
    assert not executor.can_undo()


def test_existing_non_date_edits_remain_undoable(table):
    _, model, dataset, executor = table
    assert model.setData(model.index(0, 1), "4.5")
    assert dataset.data.iloc[0, 1] == 4.5
    executor.undo()
    assert dataset.data.iloc[0, 1] == 1.5
    assert model.setData(model.index(0, 2), "updated")
    assert dataset.data.iloc[0, 2] == "updated"


@pytest.mark.parametrize("unit", ["s", "ms", "us", "ns"])
def test_column_datetime_unit_is_preserved(table, unit):
    _, model, dataset, executor = table
    dataset.data["date"] = dataset.data["date"].astype(f"datetime64[{unit}]")
    dtype = dataset.data.dtypes.iloc[0]
    assert model.setData(model.index(0, 0), "2026-10-01 12:30:45")
    assert dataset.data.dtypes.iloc[0] == dtype
    executor.undo()
    assert dataset.data.dtypes.iloc[0] == dtype


def test_calendar_escape_does_not_commit(table, qtbot):
    view, model, dataset, executor = table
    original = dataset.data.iloc[0, 0]
    editor = edit_cell(qtbot, view, model)
    qtbot.mouseClick(editor.button, Qt.MouseButton.LeftButton)
    qtbot.keyClick(editor.calendar_dialog, Qt.Key.Key_Escape)
    assert dataset.data.iloc[0, 0] == original
    assert not executor.can_undo()


def test_failed_command_returns_false(table):
    _, model, _dataset, executor = table
    model.app_context.get_app_state.return_value.close_project()
    assert not model.setData(model.index(0, 0), "2026-10-01")
    assert not executor.can_undo()


def test_tab_commits_typed_date_through_delegate(table, qtbot):
    view, model, dataset, executor = table
    editor = edit_cell(qtbot, view, model)
    editor.text.selectAll()
    qtbot.keyClicks(editor.text, "2026-10-04")
    qtbot.keyClick(editor.text, Qt.Key.Key_Tab)
    assert dataset.data.iloc[0, 0] == pd.Timestamp("2026-10-04")
    assert executor.can_undo()


def test_dynamic_dtype_uses_default_editor_after_column_changes(table, qtbot):
    view, model, dataset, _ = table
    dataset.data["date"] = dataset.data["date"].astype(str)
    view.edit(model.index(0, 0))
    qtbot.waitUntil(lambda: any(widget.isVisible() for widget in view.findChildren(QLineEdit)))
    assert view.findChild(DateCellEditor) is None
