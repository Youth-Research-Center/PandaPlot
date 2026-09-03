"""Tests for EditCommand's failure-path logging.

Only exercises the warning-logging behavior added when execute() early-returns
on a genuine failure condition; not a full command test suite.
"""

import logging
from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.dataset.edit_command import EditCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext


@pytest.fixture
def mock_app_context():
    app_context = Mock(spec=AppContext)
    app_context.app_state = Mock()
    app_context.get_ui_controller.return_value = Mock(spec=UIController)
    app_context.event_bus = Mock()
    app_context.event_bus.emit = Mock()
    return app_context


@pytest.fixture
def sample_project():
    project = Mock()
    project.find_item = Mock()
    return project


def test_execute_logs_warning_when_no_project(mock_app_context, caplog):
    mock_app_context.app_state.has_project = False
    command = EditCommand(mock_app_context, "ds-1", (0, 0), old_value=1, new_value=2)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "no project" in caplog.text.lower()


def test_execute_logs_warning_when_current_project_none(mock_app_context, caplog):
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = None
    command = EditCommand(mock_app_context, "ds-1", (0, 0), old_value=1, new_value=2)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "current_project is None" in caplog.text


def test_execute_logs_warning_when_dataset_not_found(mock_app_context, sample_project, caplog):
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    sample_project.find_item.return_value = None
    command = EditCommand(mock_app_context, "missing-ds", (0, 0), old_value=1, new_value=2)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "missing-ds" in caplog.text


def test_execute_logs_warning_when_item_not_a_dataset(mock_app_context, sample_project, caplog):
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    sample_project.find_item.return_value = object()
    command = EditCommand(mock_app_context, "ds-1", (0, 0), old_value=1, new_value=2)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "ds-1" in caplog.text and "not a Dataset" in caplog.text


def test_execute_logs_warning_when_dataset_has_no_structure(mock_app_context, sample_project, caplog):
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1]}))
    dataset.data = None  # simulate a dataset without structure
    sample_project.find_item.return_value = dataset
    command = EditCommand(mock_app_context, "ds-1", (0, 0), old_value=1, new_value=2)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "ds-1" in caplog.text and "no structure" in caplog.text.lower()


def test_undo_returns_failure_when_called_before_execute(mock_app_context, caplog):
    command = EditCommand(mock_app_context, "ds-1", (0, 0), old_value=1, new_value=2)

    with caplog.at_level(logging.WARNING):
        assert command.undo() is CommandResult.FAILURE
    assert "ds-1" in caplog.text


def test_redo_returns_failure_when_called_before_execute(mock_app_context, caplog):
    command = EditCommand(mock_app_context, "ds-1", (0, 0), old_value=1, new_value=2)

    with caplog.at_level(logging.WARNING):
        assert command.redo() is CommandResult.FAILURE
    assert "ds-1" in caplog.text


def test_undo_returns_failure_when_execute_failed_after_assigning_dataset(mock_app_context, sample_project, caplog):
    """execute() assigns self.dataset before attempting the write, so a
    write that fails (e.g. an out-of-range index) would leave self.dataset
    set without anything having actually been applied, unless execute()
    resets it on that failure path (it does). undo() must not treat this
    as a valid prior execution."""
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1]}))
    sample_project.find_item.return_value = dataset
    command = EditCommand(mock_app_context, "ds-1", (5, 5), old_value=1, new_value=2)

    assert command.execute() is CommandResult.FAILURE

    with caplog.at_level(logging.WARNING):
        assert command.undo() is CommandResult.FAILURE
    assert "ds-1" in caplog.text


def test_redo_returns_failure_when_execute_failed_after_assigning_dataset(mock_app_context, sample_project, caplog):
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1]}))
    sample_project.find_item.return_value = dataset
    command = EditCommand(mock_app_context, "ds-1", (5, 5), old_value=1, new_value=2)

    assert command.execute() is CommandResult.FAILURE

    with caplog.at_level(logging.WARNING):
        assert command.redo() is CommandResult.FAILURE
    assert "ds-1" in caplog.text


def test_undo_returns_failure_when_dataset_gains_structure_after_a_no_structure_failure(
    mock_app_context, sample_project, caplog,
):
    """execute() assigns self.dataset before checking dataset.data is None,
    and self.dataset is a live reference to the shared Dataset object. If
    that object is later given a DataFrame by something else entirely,
    undo() must still not treat this command as having executed
    successfully -- self.dataset must have been cleared on that failure
    path too."""
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1]}))
    dataset.data = None  # simulate a dataset without structure
    sample_project.find_item.return_value = dataset
    command = EditCommand(mock_app_context, "ds-1", (0, 0), old_value=1, new_value=2)

    assert command.execute() is CommandResult.FAILURE

    dataset.data = pd.DataFrame({"a": [1]})  # dataset gains structure afterwards

    with caplog.at_level(logging.WARNING):
        assert command.undo() is CommandResult.FAILURE
    assert "ds-1" in caplog.text


def test_cleanup_releases_the_dataset_and_project_references(mock_app_context):
    command = EditCommand(mock_app_context, "ds-1", (0, 0), old_value=1, new_value=2)
    command.dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1]}))
    command.project = Mock()

    command.cleanup()

    assert command.dataset is None
    assert command.project is None
