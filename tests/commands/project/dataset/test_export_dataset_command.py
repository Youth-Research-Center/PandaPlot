"""Tests for ExportDatasetCommand's failure-path logging.

Only exercises the warning-logging behavior added when execute()/redo()
early-return on a genuine failure condition; not a full command test suite.
"""

import logging
from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.dataset.export_dataset_command import ExportDatasetCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState


@pytest.fixture
def mock_app_context():
    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    ui_controller = Mock(spec=UIController)

    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = ui_controller
    app_context.get_task_scheduler.return_value = Mock()

    return app_context, app_state, ui_controller


@pytest.fixture
def sample_project():
    project = Mock()
    project.find_item = Mock()
    return project


def test_execute_logs_warning_when_no_project(mock_app_context, caplog):
    app_context, app_state, ui_controller = mock_app_context
    app_state.has_project = False
    command = ExportDatasetCommand(app_context, "ds-1")

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "no project" in caplog.text.lower()


def test_execute_logs_warning_when_current_project_none(mock_app_context, caplog):
    app_context, app_state, ui_controller = mock_app_context
    app_state.has_project = True
    app_state.current_project = None
    command = ExportDatasetCommand(app_context, "ds-1")

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "current_project is None" in caplog.text


def test_execute_logs_warning_when_dataset_not_found(mock_app_context, sample_project, caplog):
    app_context, app_state, ui_controller = mock_app_context
    app_state.has_project = True
    app_state.current_project = sample_project
    sample_project.find_item.return_value = None
    command = ExportDatasetCommand(app_context, "missing-ds")

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "missing-ds" in caplog.text


def test_execute_logs_warning_when_item_not_a_dataset(mock_app_context, sample_project, caplog):
    app_context, app_state, ui_controller = mock_app_context
    app_state.has_project = True
    app_state.current_project = sample_project
    sample_project.find_item.return_value = object()
    command = ExportDatasetCommand(app_context, "ds-1")

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "ds-1" in caplog.text and "not a Dataset" in caplog.text


def test_execute_logs_warning_when_dataset_empty(mock_app_context, sample_project, caplog):
    app_context, app_state, ui_controller = mock_app_context
    app_state.has_project = True
    app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame())
    sample_project.find_item.return_value = dataset
    command = ExportDatasetCommand(app_context, "ds-1")

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "ds-1" in caplog.text and "no data" in caplog.text.lower()


def test_redo_logs_warning_when_nothing_to_redo(mock_app_context, caplog):
    app_context, app_state, ui_controller = mock_app_context
    command = ExportDatasetCommand(app_context, "ds-1")

    with caplog.at_level(logging.WARNING):
        assert command.redo() is CommandResult.FAILURE
    assert "cannot redo" in caplog.text.lower()


def test_occupies_undo_slot_returns_false(mock_app_context):
    """ExportDatasetCommand's undo() is a documented no-op, so it must never
    occupy an undo slot -- its only call site (DatasetTab.export_data) relies
    on this to keep it off the undo stack when routed through
    CommandExecutor.execute_command()."""
    app_context, _app_state, _ui_controller = mock_app_context
    command = ExportDatasetCommand(app_context, "ds-1")

    assert command.occupies_undo_slot() is False


def test_cleanup_releases_the_project_and_dataset_references(mock_app_context, sample_project):
    app_context, app_state, ui_controller = mock_app_context
    command = ExportDatasetCommand(app_context, "ds-1")
    command.project = sample_project
    command.dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1]}))

    command.cleanup()

    assert command.project is None
    assert command.dataset is None
