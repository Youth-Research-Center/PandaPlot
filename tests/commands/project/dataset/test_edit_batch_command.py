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
from pandaplot.models.events.event_types import DatasetEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.formula_column import FormulaColumnSpec
from pandaplot.models.state.app_context import AppContext


@pytest.fixture
def mock_app_context():
    app_context = Mock(spec=AppContext)
    app_context.app_state = Mock()
    app_context.get_app_state.return_value = app_context.app_state
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

    with caplog.at_level(logging.WARNING), pytest.MonkeyPatch.context() as mp:
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


def test_edit_batch_command_updates_modified_at_on_execute_undo_redo(mock_app_context, sample_project):
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
    dataset.modified_at = "2020-01-01T00:00:00.000000"
    sample_project.find_item.return_value = dataset

    command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[10]])

    assert command.execute() is CommandResult.SUCCESS
    assert dataset.modified_at != "2020-01-01T00:00:00.000000"

    dataset.modified_at = "2020-01-01T00:00:00.000000"
    assert command.undo() is CommandResult.SUCCESS
    assert dataset.modified_at != "2020-01-01T00:00:00.000000"

    dataset.modified_at = "2020-01-01T00:00:00.000000"
    assert command.redo() is CommandResult.SUCCESS
    assert dataset.modified_at != "2020-01-01T00:00:00.000000"


def _dataset_with_live_column() -> Dataset:
    """a and c are plain; b is a live formula column over a."""
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({
        "a": [1.0, 2.0, 3.0], "b": [2.0, 4.0, 6.0], "c": [7.0, 8.0, 9.0],
    }))
    dataset.set_formula_column(dataset.column_id("b"), FormulaColumnSpec(
        expression="x * 2", source_column_ids=[dataset.column_id("a")], live=True,
    ))
    return dataset


def test_a_batch_overlapping_a_live_formula_column_is_refused_untouched(mock_app_context, sample_project):
    """Pasting over a derived column is rejected as a whole -- including the
    rows the paste would have appended -- rather than half-applied."""
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    dataset = _dataset_with_live_column()
    before = dataset.data.copy()
    sample_project.find_item.return_value = dataset
    # Two columns starting at "a" reach into "b", and five rows overrun the three that exist.
    command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[9.0, 9.0]] * 5)

    assert command.execute() is CommandResult.FAILURE

    pd.testing.assert_frame_equal(dataset.data, before)
    mock_app_context.get_ui_controller().show_warning_message.assert_called_once()
    message = mock_app_context.get_ui_controller().show_warning_message.call_args.args[1]
    assert "'b'" in message
    mock_app_context.event_bus.emit.assert_not_called()


def test_a_batch_that_skips_the_live_column_is_allowed(mock_app_context, sample_project):
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    dataset = _dataset_with_live_column()
    sample_project.find_item.return_value = dataset
    command = EditBatchCommand(mock_app_context, "ds-1", 0, 2, [[70.0], [80.0]])

    assert command.execute() is CommandResult.SUCCESS
    assert dataset.data["c"].tolist() == [70.0, 80.0, 9.0]
    assert dataset.data["b"].tolist() == [2.0, 4.0, 6.0]


def test_a_batch_on_the_source_column_is_allowed(mock_app_context, sample_project):
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    dataset = _dataset_with_live_column()
    sample_project.find_item.return_value = dataset
    command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[10.0], [20.0]])

    assert command.execute() is CommandResult.SUCCESS
    assert dataset.data["a"].tolist() == [10.0, 20.0, 3.0]


@pytest.fixture
def project_with_dataset(mock_app_context, sample_project):
    """A 2x2 dataset reachable through the current project."""
    mock_app_context.app_state.has_project = True
    mock_app_context.app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]}))
    sample_project.find_item.return_value = dataset
    return dataset


def _data_changed_payloads(app_context):
    return [c.args[1] for c in app_context.event_bus.emit.call_args_list if c.args[0] == DatasetEvents.DATASET_DATA_CHANGED]


class TestBatchEditExpansion:
    """A paste that overruns the dataset grows it first; undo and redo replay both steps."""

    def test_paste_past_the_edges_grows_the_dataset_and_undo_redo_replay_it(self, mock_app_context, project_with_dataset):
        dataset = project_with_dataset
        before = dataset.data.copy()
        command = EditBatchCommand(mock_app_context, "ds-1", 1, 1, [[10.0, 11.0], [12.0, 13.0]])

        assert command.execute() is CommandResult.SUCCESS

        assert dataset.data.shape == (3, 3)
        assert dataset.data.iloc[1:3, 1:3].values.tolist() == [[10.0, 11.0], [12.0, 13.0]]
        assert dataset.data.iloc[0, 0] == 1.0
        after = dataset.data.copy()

        assert command.undo() is CommandResult.SUCCESS
        pd.testing.assert_frame_equal(dataset.data, before)

        assert command.redo() is CommandResult.SUCCESS
        pd.testing.assert_frame_equal(dataset.data, after)
        # execute, undo and redo all tell subscribers which dataset changed.
        assert [p["dataset_id"] for p in _data_changed_payloads(mock_app_context)] == ["ds-1", "ds-1", "ds-1"]

    @pytest.mark.xfail(strict=True, reason="#667: AddColumnsCommand.redo() re-runs execute() and mints new column IDs")
    def test_redo_keeps_the_ids_of_columns_the_paste_added(self, mock_app_context, project_with_dataset):
        dataset = project_with_dataset
        command = EditBatchCommand(mock_app_context, "ds-1", 0, 1, [[10.0, 11.0]])
        assert command.execute() is CommandResult.SUCCESS
        column_ids_after = dict(dataset.column_ids)

        assert command.undo() is CommandResult.SUCCESS
        assert command.redo() is CommandResult.SUCCESS

        assert dict(dataset.column_ids) == column_ids_after

    def test_failed_column_expansion_rolls_back_the_rows_it_added(self, mock_app_context, project_with_dataset, monkeypatch):
        """A paste that cannot add its columns must not leave behind the rows it
        added first: execute() returns FAILURE, so nothing could undo them."""
        dataset = project_with_dataset
        before = dataset.data.copy()
        monkeypatch.setattr(
            "pandaplot.commands.project.dataset.edit_batch_command.AddColumnsCommand.execute",
            lambda self: CommandResult.FAILURE,
        )
        command = EditBatchCommand(mock_app_context, "ds-1", 1, 1, [[10.0, 11.0], [12.0, 13.0]])

        assert command.execute() is CommandResult.FAILURE

        pd.testing.assert_frame_equal(dataset.data, before)
        assert command.executed_commands == []
        assert "Failed to add 1 columns" in mock_app_context.get_ui_controller().show_error_message.call_args.args[1]

    def test_a_cell_that_cannot_be_written_rolls_back_the_whole_paste(self, mock_app_context, project_with_dataset):
        dataset = project_with_dataset
        before = dataset.data.copy()
        # The third row needs a new row; its second cell cannot be stored in a float column.
        command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[10.0, 11.0], [12.0, 13.0], [14.0, [1, 2]]])

        assert command.execute() is CommandResult.FAILURE

        pd.testing.assert_frame_equal(dataset.data, before)
        assert command.executed_commands == []
        mock_app_context.event_bus.emit.assert_not_called()
        assert mock_app_context.get_ui_controller().show_error_message.call_args.args[0] == "Batch Edit Error"

    def test_a_cell_that_cannot_be_written_restores_the_cells_already_written(self, mock_app_context, project_with_dataset):
        dataset = project_with_dataset
        before = dataset.data.copy()
        command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[10.0], [[1, 2]]])

        assert command.execute() is CommandResult.FAILURE

        pd.testing.assert_frame_equal(dataset.data, before)
        assert command.old_data is None
        assert command.undo() is CommandResult.FAILURE

    def test_dataset_with_columns_but_no_rows_cannot_grow(self, mock_app_context, project_with_dataset):
        dataset = project_with_dataset
        dataset.set_data(pd.DataFrame({"a": pd.Series([], dtype=float)}))
        command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[1.0]])

        assert command.execute() is CommandResult.FAILURE

        assert dataset.data.empty
        assert command.dataset is None
        assert command.redo() is CommandResult.FAILURE

    def test_dataset_with_rows_but_no_columns_cannot_grow(self, mock_app_context, project_with_dataset):
        dataset = project_with_dataset
        dataset.set_data(pd.DataFrame(index=[0, 1]))
        command = EditBatchCommand(mock_app_context, "ds-1", 0, 0, [[1.0]])

        assert command.execute() is CommandResult.FAILURE

        assert dataset.data.shape == (2, 0)
        assert command.dataset is None
