"""Tests for the DatasetTab empty-state panel shown for datasets with no columns or no rows."""

from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.app import build_app_context
from pandaplot.commands.project.dataset import AddRowsColumnsCommand
from pandaplot.commands.project.dataset.delete_rows_command import DeleteRowsCommand
from pandaplot.gui.components.tabs.dataset.dataset_tab import DatasetTab
from pandaplot.models.events.event_data import DatasetRowsAddedData
from pandaplot.models.events.event_types import DatasetOperationEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project

NO_ROWS = "This dataset has no rows"
NO_COLUMNS = "This dataset has no columns"


@pytest.fixture
def app_context(qapp, monkeypatch):
    context = build_app_context()
    monkeypatch.setattr(context.ui_controller, "show_info_message", Mock())
    monkeypatch.setattr(context.ui_controller, "show_error_message", Mock())
    monkeypatch.setattr(context.ui_controller, "show_warning_message", Mock())
    return context


def _make_tab(app_context, qtbot, data: pd.DataFrame | None) -> DatasetTab:
    project = Project("p")
    dataset = Dataset(name="ds", data=data)
    project.add_item(dataset)
    app_context.get_app_state().load_project(project)
    tab = DatasetTab(app_context, dataset, None)  # ty: ignore[invalid-argument-type]  # top-level tab has no parent
    qtbot.addWidget(tab)
    tab.show()
    return tab


def test_non_empty_dataset_hides_panel(app_context, qtbot):
    tab = _make_tab(app_context, qtbot, pd.DataFrame({"a": [1, 2]}))

    assert not tab.empty_state_panel.isVisible()


def test_zero_row_dataset_shows_rows_heading_and_keeps_table(app_context, qtbot):
    tab = _make_tab(app_context, qtbot, pd.DataFrame({"a": []}))

    assert tab.empty_state_panel.isVisible()
    assert tab.empty_state_panel.heading_label.text() == NO_ROWS
    assert tab.empty_state_panel.description_label.text() == "Add rows and columns, then type or paste values."
    assert tab.table_view.isVisible()


@pytest.mark.parametrize("data", [None, pd.DataFrame()])
def test_dataset_without_columns_shows_columns_heading(app_context, qtbot, data):
    tab = _make_tab(app_context, qtbot, data)

    assert tab.empty_state_panel.isVisible()
    assert tab.empty_state_panel.heading_label.text() == NO_COLUMNS


def test_deleting_all_rows_shows_panel_and_undo_hides_it(app_context, qtbot):
    tab = _make_tab(app_context, qtbot, pd.DataFrame({"a": [1, 2]}))
    executor = app_context.get_command_executor()

    assert executor.execute_command(DeleteRowsCommand(app_context, tab.dataset.id, [0, 1]))
    assert tab.empty_state_panel.isVisible()
    assert tab.empty_state_panel.heading_label.text() == NO_ROWS

    assert executor.undo()
    assert not tab.empty_state_panel.isVisible()


def test_adding_rows_event_hides_panel(app_context, qtbot):
    tab = _make_tab(app_context, qtbot, pd.DataFrame({"a": []}))
    assert tab.empty_state_panel.isVisible()

    tab.dataset.set_data(pd.DataFrame({"a": [1]}))
    app_context.get_app_state().event_bus.emit(
        DatasetOperationEvents.DATASET_ROW_ADDED,
        DatasetRowsAddedData(dataset_id=tab.dataset.id, row_positions=[0]).to_dict(),
    )

    assert not tab.empty_state_panel.isVisible()


def test_other_dataset_event_does_not_refresh_panel(app_context, qtbot):
    tab = _make_tab(app_context, qtbot, pd.DataFrame({"a": []}))
    tab.dataset.set_data(pd.DataFrame({"a": [1]}))

    app_context.get_app_state().event_bus.emit(
        DatasetOperationEvents.DATASET_ROW_ADDED,
        DatasetRowsAddedData(dataset_id="other", row_positions=[0]).to_dict(),
    )

    assert tab.empty_state_panel.isVisible()


def test_action_button_executes_add_rows_columns_command_for_this_dataset(app_context, qtbot, monkeypatch):
    tab = _make_tab(app_context, qtbot, pd.DataFrame({"a": []}))
    execute = Mock(return_value=True)
    monkeypatch.setattr(app_context.get_command_executor(), "execute_command", execute)

    tab.empty_state_panel.action_buttons[0].click()

    execute.assert_called_once()
    command = execute.call_args.args[0]
    assert isinstance(command, AddRowsColumnsCommand)
    assert command.dataset_id == tab.dataset.id
