"""Tests for EditBatchCommand's failure-path logging.

Only exercises the warning-logging behavior added when execute()/undo()/redo()
early-return on a genuine failure condition; not a full command test suite.
"""

import logging
from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.dataset.edit_batch_command import EditBatchCommand
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
    command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[1]])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "no project" in caplog.text.lower()


def test_execute_logs_warning_when_current_project_none(mock_app_context, caplog):
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = None
    command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[1]])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "current_project is None" in caplog.text


def test_execute_logs_warning_when_dataset_not_found(mock_app_context, sample_project, caplog):
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    sample_project.find_item.return_value = None
    command = EditBatchCommand(mock_app_context, "missing-ds", 0, 0, [[1]])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "missing-ds" in caplog.text


def test_execute_logs_warning_when_item_not_a_dataset(mock_app_context, sample_project, caplog):
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    sample_project.find_item.return_value = object()
    command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[1]])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "ds-1" in caplog.text and "not a Dataset" in caplog.text


def test_execute_logs_warning_when_dataset_has_no_structure(mock_app_context, sample_project, caplog):
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1]}))
    dataset.data = None  # simulate a dataset without structure
    sample_project.find_item.return_value = dataset
    command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[1]])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "ds-1" in caplog.text and "no structure" in caplog.text.lower()


def test_execute_logs_warning_when_no_new_data(mock_app_context, sample_project, caplog):
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
    sample_project.find_item.return_value = dataset
    command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "no data provided" in caplog.text.lower()


def test_execute_logs_warning_when_row_lengths_mismatch(mock_app_context, sample_project, caplog):
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2], "b": [3, 4]}))
    sample_project.find_item.return_value = dataset
    command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[1, 2], [3]])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "row 1" in caplog.text.lower()


def test_execute_logs_warning_when_add_rows_fails(mock_app_context, sample_project, caplog):
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1], "b": [2]}))
    sample_project.find_item.return_value = dataset
    command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[1, 2], [3, 4]])

    with caplog.at_level(logging.WARNING):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "pandaplot.commands.project.dataset.edit_batch_command.AddRowsCommand.execute",
                lambda self: CommandResult.FAILURE,
            )
            assert command.execute() is CommandResult.FAILURE
    assert "failed to add" in caplog.text.lower() and "rows" in caplog.text.lower()


def test_undo_logs_warning_when_nothing_to_undo(mock_app_context, caplog):
    command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[1]])

    with caplog.at_level(logging.WARNING):
        command.undo()
    assert "ds-1" in caplog.text


def test_redo_logs_warning_when_dataset_missing(mock_app_context, caplog):
    command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[1]])
    # redo() only reaches the dataset check after a prior successful execute()
    # set `self.dataset`; simulate that attribute existing but cleared.
    command.dataset = None

    with caplog.at_level(logging.WARNING):
        command.redo()
    assert "ds-1" in caplog.text


def test_cleanup_releases_the_old_data_snapshot():
    app_context = Mock(spec=AppContext)
    app_context.app_state = Mock()
    app_context.get_ui_controller.return_value = Mock()

    command = EditBatchCommand(app_context, "ds-1", 0, 0, [[1, 2], [3, 4]])
    command.old_data = pd.DataFrame({"a": [1, 2, 3]})

    command.cleanup()

    assert command.old_data is None


def test_cleanup_cascades_to_sub_commands():
    """EditBatchCommand accumulates AddRowsCommand/AddColumnsCommand instances
    in `executed_commands` -- these hold their own undo snapshots and are never
    pushed onto CommandExecutor's stacks themselves, so nothing else would ever
    call their cleanup(). EditBatchCommand.cleanup() must do it for them."""
    app_context = Mock(spec=AppContext)
    app_context.app_state = Mock()
    app_context.get_ui_controller.return_value = Mock()

    command = EditBatchCommand(app_context, "ds-1", 0, 0, [[1, 2], [3, 4]])
    command.old_data = pd.DataFrame({"a": [1, 2, 3]})
    sub_command_1 = Mock()
    sub_command_2 = Mock()
    command.executed_commands = [sub_command_1, sub_command_2]

    command.cleanup()

    assert command.old_data is None
    sub_command_1.cleanup.assert_called_once_with()
    sub_command_2.cleanup.assert_called_once_with()
    assert command.executed_commands == []


def test_redo_returns_failure_when_called_before_execute(mock_app_context, caplog):
    command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[1]])

    with caplog.at_level(logging.WARNING):
        assert command.redo() is CommandResult.FAILURE
    assert "ds-1" in caplog.text


def test_redo_returns_failure_when_execute_failed_after_assigning_dataset(mock_app_context, sample_project, caplog):
    """execute() assigns self.dataset before validating the new_data shape,
    so a validation failure (mismatched row lengths) would leave self.dataset
    set without old_data/new_data ever having been consistently applied,
    unless execute() resets it on that failure path (it does). redo() must
    not treat this as a valid prior execution -- otherwise it would silently
    reapply a malformed, partial batch."""
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2], "b": [3, 4]}))
    sample_project.find_item.return_value = dataset
    command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[1, 2], [3]])

    assert command.execute() is CommandResult.FAILURE

    with caplog.at_level(logging.WARNING):
        assert command.redo() is CommandResult.FAILURE
    assert "ds-1" in caplog.text
    assert dataset.data["a"].tolist() == [1, 2]
    assert dataset.data["b"].tolist() == [3, 4]


def test_redo_does_not_replay_expansion_commands_when_dataset_is_unset(mock_app_context):
    """redo() must not blindly replay recorded expansion sub-commands before
    confirming this command actually executed successfully. Otherwise a
    stray redo() call after a failed execute() (e.g. row expansion
    succeeded but column expansion then failed, leaving dataset cleared but
    executed_commands non-empty) would silently re-apply the recorded
    row/column additions a second time before finally reporting FAILURE."""
    command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[1]])
    sub_command = Mock()
    command.executed_commands = [sub_command]
    command.dataset = None  # as if execute() failed and cleared it

    assert command.redo() is CommandResult.FAILURE
    sub_command.redo.assert_not_called()


def test_cleanup_isolates_a_raising_sub_command():
    """If one sub-command's cleanup() raises, the remaining sub-commands must
    still get cleaned up, executed_commands must still be cleared, and the
    exception must not propagate out of EditBatchCommand.cleanup()."""
    app_context = Mock(spec=AppContext)
    app_context.app_state = Mock()
    app_context.get_ui_controller.return_value = Mock()

    command = EditBatchCommand(app_context, "ds-1", 0, 0, [[1, 2], [3, 4]])
    command.old_data = pd.DataFrame({"a": [1, 2, 3]})
    raising_sub_command = Mock()
    raising_sub_command.cleanup.side_effect = RuntimeError("boom")
    ok_sub_command = Mock()
    command.executed_commands = [raising_sub_command, ok_sub_command]

    command.cleanup()  # must not raise

    ok_sub_command.cleanup.assert_called_once_with()
    assert command.executed_commands == []
