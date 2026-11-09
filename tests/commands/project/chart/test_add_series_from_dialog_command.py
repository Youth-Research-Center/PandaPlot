"""Tests for AddSeriesFromDialogCommand, against a real app context and project."""
from unittest.mock import Mock

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QWidget

from pandaplot.app import build_app_context
from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.chart import AddSeriesCommand, AddSeriesFromDialogCommand
from pandaplot.gui.dialogs.chart.add_series_dialog import AddSeriesDialog
from pandaplot.models.events import ChartEvents
from pandaplot.models.project import Project
from pandaplot.models.project.items import Chart, Dataset


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def app_context(monkeypatch):
    context = build_app_context()
    ui = context.get_ui_controller()
    monkeypatch.setattr(ui, "show_info_message", Mock())
    monkeypatch.setattr(ui, "show_error_message", Mock())
    return context


@pytest.fixture
def dataset() -> Dataset:
    return Dataset(id="ds-1", name="Sales", data=pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]}))


@pytest.fixture
def chart() -> Chart:
    return Chart(name="Revenue", chart_type="line")


@pytest.fixture
def project(app_context, dataset, chart) -> Project:
    project = Project(name="P")
    project.add_item(dataset)
    project.add_item(chart)
    app_context.get_app_state().load_project(project)
    return project


@pytest.fixture
def selected(app_context) -> list[dict]:
    received: list[dict] = []
    app_context.event_bus.subscribe(ChartEvents.SERIES_SELECTED, received.append)
    return received


def _open(app_context, chart, qtbot, *, parent=None) -> tuple[AddSeriesFromDialogCommand, AddSeriesDialog]:
    command = AddSeriesFromDialogCommand(app_context, chart.id, parent=parent)
    assert app_context.get_command_executor().execute_command(command)
    dialog = command._dialog
    assert isinstance(dialog, AddSeriesDialog)
    return command, dialog


def _fill(dialog, dataset) -> None:
    for role, column in (("x", "x"), ("y", "y")):
        combo = dialog.card._role_combos[role]
        combo.setCurrentIndex(combo.findData(dataset.column_id(column)))


def test_opener_does_not_occupy_undo_slot_or_mark_modified(app_context, chart):
    command = AddSeriesFromDialogCommand(app_context, chart.id)
    assert command.occupies_undo_slot() is False
    assert command.marks_project_modified() is False


def test_no_datasets_shows_info_and_opens_no_dialog(app_context, chart):
    project = Project(name="Empty")
    project.add_item(chart)
    app_context.get_app_state().load_project(project)
    command = AddSeriesFromDialogCommand(app_context, chart.id)

    assert command.execute() is CommandResult.NOOP

    assert command._dialog is None
    app_context.get_ui_controller().show_info_message.assert_called_once()
    assert not any(isinstance(w, AddSeriesDialog) for w in QApplication.topLevelWidgets())


def test_missing_chart_fails(app_context, project):
    command = AddSeriesFromDialogCommand(app_context, "no-such-chart")

    assert command.execute() is CommandResult.FAILURE

    app_context.get_ui_controller().show_error_message.assert_called_once()
    assert command._dialog is None


def test_no_project_fails(app_context):
    assert AddSeriesFromDialogCommand(app_context, "c").execute() is CommandResult.FAILURE


def test_accept_adds_series_with_one_undo_entry_and_selects_it(app_context, project, chart, dataset, qtbot, selected):
    executor = app_context.get_command_executor()
    before = len(executor.undo_stack)
    command, dialog = _open(app_context, chart, qtbot)
    assert len(executor.undo_stack) == before
    _fill(dialog, dataset)

    dialog.accept()

    assert len(chart.data_series) == 1
    series = chart.data_series[0]
    assert series.dataset_id == dataset.id
    assert series.x_column_id == dataset.column_id("x")
    assert series.y_column_id == dataset.column_id("y")
    assert len(executor.undo_stack) == before + 1
    assert isinstance(executor.undo_stack[-1], AddSeriesCommand)
    assert [(e["chart_id"], e["series_index"], e["kind"]) for e in selected] == [(chart.id, 0, "series")]
    assert command._dialog is None


def test_undo_and_redo(app_context, project, chart, dataset, qtbot):
    executor = app_context.get_command_executor()
    _command, dialog = _open(app_context, chart, qtbot)
    _fill(dialog, dataset)
    dialog.accept()
    series = chart.data_series[0]

    assert executor.undo()
    assert chart.data_series == []
    assert executor.redo()
    assert chart.data_series == [series]


def test_reject_adds_nothing(app_context, project, chart, qtbot, selected):
    executor = app_context.get_command_executor()
    before = len(executor.undo_stack)
    command, dialog = _open(app_context, chart, qtbot)

    dialog.reject()

    assert chart.data_series == []
    assert len(executor.undo_stack) == before
    assert selected == []
    assert command._dialog is None


def test_chart_deleted_before_accept_adds_nothing(app_context, project, chart, dataset, qtbot, selected):
    executor = app_context.get_command_executor()
    before = len(executor.undo_stack)
    _command, dialog = _open(app_context, chart, qtbot)
    _fill(dialog, dataset)
    project.remove_item_by_id(chart.id)

    dialog.accept()

    assert chart.data_series == []
    assert len(executor.undo_stack) == before
    assert selected == []


def test_project_replaced_before_accept_adds_nothing(app_context, project, chart, dataset, qtbot, selected):
    _command, dialog = _open(app_context, chart, qtbot)
    _fill(dialog, dataset)
    app_context.get_app_state().load_project(Project(name="Other"))

    dialog.accept()

    assert chart.data_series == []
    assert selected == []


def test_dialog_parent_is_the_given_parent(app_context, project, chart, qtbot):
    parent = QWidget()

    _command, dialog = _open(app_context, chart, qtbot, parent=parent)

    try:
        assert dialog.parent() is parent
        assert dialog.isModal()
    finally:
        dialog.reject()
        parent.deleteLater()
