"""Tests for DeleteRowsCommand's failure-path logging.

Only exercises the warning-logging behavior added when execute()/undo()
early-return on a genuine failure condition; not a full command test suite.
"""

import logging
from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.project.dataset.delete_rows_command import DeleteRowsCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state import AppContext, AppState


@pytest.fixture
def mock_app_context():
    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    ui_controller = Mock(spec=UIController)

    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = ui_controller
    app_state.event_bus = Mock()
    app_state.event_bus.emit = Mock()

    return app_context, app_state, ui_controller


@pytest.fixture
def sample_project():
    project = Mock()
    project.find_item = Mock()
    return project


def test_execute_logs_warning_when_no_row_positions(mock_app_context, caplog):
    app_context, app_state, ui_controller = mock_app_context
    command = DeleteRowsCommand(app_context, "ds-1", row_positions=[])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "no row positions" in caplog.text.lower()


def test_execute_logs_warning_when_no_project(mock_app_context, caplog):
    app_context, app_state, ui_controller = mock_app_context
    app_state.has_project = False
    command = DeleteRowsCommand(app_context, "ds-1", row_positions=[0])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "no project" in caplog.text.lower()


def test_execute_logs_warning_when_current_project_none(mock_app_context, caplog):
    app_context, app_state, ui_controller = mock_app_context
    app_state.has_project = True
    app_state.current_project = None
    command = DeleteRowsCommand(app_context, "ds-1", row_positions=[0])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "current_project is None" in caplog.text


def test_execute_logs_warning_when_dataset_not_found(mock_app_context, sample_project, caplog):
    app_context, app_state, ui_controller = mock_app_context
    app_state.has_project = True
    app_state.current_project = sample_project
    sample_project.find_item.return_value = None
    command = DeleteRowsCommand(app_context, "missing-ds", row_positions=[0])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "missing-ds" in caplog.text


def test_execute_logs_warning_when_item_not_a_dataset(mock_app_context, sample_project, caplog):
    app_context, app_state, ui_controller = mock_app_context
    app_state.has_project = True
    app_state.current_project = sample_project
    sample_project.find_item.return_value = object()
    command = DeleteRowsCommand(app_context, "ds-1", row_positions=[0])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "ds-1" in caplog.text and "not a Dataset" in caplog.text


def test_execute_logs_warning_when_dataset_empty(mock_app_context, sample_project, caplog):
    app_context, app_state, ui_controller = mock_app_context
    app_state.has_project = True
    app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame())
    sample_project.find_item.return_value = dataset
    command = DeleteRowsCommand(app_context, "ds-1", row_positions=[0])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "ds-1" in caplog.text and "no data" in caplog.text.lower()


def test_execute_logs_warning_when_row_positions_invalid(mock_app_context, sample_project, caplog):
    app_context, app_state, ui_controller = mock_app_context
    app_state.has_project = True
    app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
    sample_project.find_item.return_value = dataset
    command = DeleteRowsCommand(app_context, "ds-1", row_positions=[5])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "5" in caplog.text


def test_execute_logs_warning_when_duplicate_positions(mock_app_context, sample_project, caplog):
    app_context, app_state, ui_controller = mock_app_context
    app_state.has_project = True
    app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2, 3]}))
    sample_project.find_item.return_value = dataset
    command = DeleteRowsCommand(app_context, "ds-1", row_positions=[0, 0])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "duplicate row positions" in caplog.text.lower()


def test_undo_logs_warning_when_nothing_to_undo(mock_app_context, caplog):
    app_context, app_state, ui_controller = mock_app_context
    command = DeleteRowsCommand(app_context, "ds-1", row_positions=[0])

    with caplog.at_level(logging.WARNING):
        command.undo()
    assert "ds-1" in caplog.text


def test_cleanup_releases_the_undo_snapshots():
    app_context = Mock(spec=AppContext)
    app_context.get_app_state.return_value = Mock(spec=AppState)
    app_context.get_ui_controller.return_value = Mock()

    command = DeleteRowsCommand(app_context, "ds-1", row_positions=[0])
    command.original_data = pd.DataFrame({"a": [1, 2, 3]})
    command.deleted_rows_data = pd.DataFrame({"a": [2]})

    command.cleanup()

    assert command.original_data is None
    assert command.deleted_rows_data is None
