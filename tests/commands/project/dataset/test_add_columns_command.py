import logging
from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.dataset.add_columns_command import AddColumnsCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state import AppContext, AppState


class TestAddColumnsCommandDefaultDtype:
    """Test suite for AddColumnsCommand's default (no default_values) column dtype."""

    @pytest.fixture
    def mock_app_context(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock(spec=UIController)

        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller
        app_state.event_bus = Mock()
        app_state.event_bus.emit = Mock()

        return app_context, app_state, ui_controller

    @pytest.fixture
    def sample_project(self):
        project = Mock()
        project.find_item = Mock()
        return project

    def test_new_column_defaults_to_float64_zero_when_dataset_has_only_strings(
        self, mock_app_context, sample_project
    ):
        """Before this change, a dataset with only string columns made new
        columns default to '' (object dtype). They must now default to
        float64 filled with 0.0 regardless of existing column types."""
        app_context, app_state, _ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": ["x", "y"]}))
        sample_project.find_item.return_value = dataset

        command = AddColumnsCommand(
            app_context, "ds-1", column_names=["b"], reference_positions=[0], side="right"
        )
        result = command.execute()

        assert result is CommandResult.SUCCESS
        assert str(dataset.data["b"].dtype) == "float64"
        assert dataset.data["b"].tolist() == [0.0, 0.0]

    def test_new_column_defaults_to_float64_zero_when_dataset_has_numeric_columns(
        self, mock_app_context, sample_project
    ):
        """Before this change, a dataset with an existing numeric column made
        new columns default to int-ish 0. They must now be float64 with 0.0,
        same as the string case -- the heuristic branch is gone entirely."""
        app_context, app_state, _ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2, 3]}))
        sample_project.find_item.return_value = dataset

        command = AddColumnsCommand(
            app_context, "ds-1", column_names=["b"], reference_positions=[0], side="right"
        )
        result = command.execute()

        assert result is CommandResult.SUCCESS
        assert str(dataset.data["b"].dtype) == "float64"
        assert dataset.data["b"].tolist() == [0.0, 0.0, 0.0]

    def test_explicit_default_value_still_honored(self, mock_app_context, sample_project):
        """Passing an explicit default_values entry must still bypass the
        float64/0.0 default and keep today's type-preserving behavior."""
        app_context, app_state, _ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2, 3]}))
        sample_project.find_item.return_value = dataset

        command = AddColumnsCommand(
            app_context, "ds-1", column_names=["b"], reference_positions=[0], side="right",
            default_values=["hello"]
        )
        result = command.execute()

        assert result is CommandResult.SUCCESS
        assert dataset.data["b"].tolist() == ["hello", "hello", "hello"]


class TestAddColumnsCommandLogging:
    """Tests that genuine failure paths log a warning instead of failing silently."""

    @pytest.fixture
    def mock_app_context(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock(spec=UIController)

        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller
        app_state.event_bus = Mock()
        app_state.event_bus.emit = Mock()

        return app_context, app_state, ui_controller

    @pytest.fixture
    def sample_project(self):
        project = Mock()
        project.find_item = Mock()
        return project

    def test_execute_logs_warning_when_no_column_names(self, mock_app_context, caplog):
        app_context, _app_state, _ui_controller = mock_app_context
        command = AddColumnsCommand(app_context, "ds-1", column_names=[], reference_positions=[])

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "no column names" in caplog.text.lower()

    def test_execute_logs_warning_when_lengths_mismatch(self, mock_app_context, caplog):
        app_context, _app_state, _ui_controller = mock_app_context
        command = AddColumnsCommand(app_context, "ds-1", column_names=["a", "b"], reference_positions=[0])

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "2" in caplog.text and "1" in caplog.text

    def test_execute_logs_warning_when_no_project(self, mock_app_context, caplog):
        app_context, app_state, _ui_controller = mock_app_context
        app_state.has_project = False
        command = AddColumnsCommand(app_context, "ds-1", column_names=["b"], reference_positions=[0])

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "no project" in caplog.text.lower()

    def test_execute_logs_warning_when_current_project_none(self, mock_app_context, caplog):
        app_context, app_state, _ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None
        command = AddColumnsCommand(app_context, "ds-1", column_names=["b"], reference_positions=[0])

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "current_project is None" in caplog.text

    def test_execute_logs_warning_when_dataset_not_found(self, mock_app_context, sample_project, caplog):
        app_context, app_state, _ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        sample_project.find_item.return_value = None
        command = AddColumnsCommand(app_context, "missing-ds", column_names=["b"], reference_positions=[0])

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "missing-ds" in caplog.text

    def test_execute_logs_warning_when_item_not_a_dataset(self, mock_app_context, sample_project, caplog):
        app_context, app_state, _ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        sample_project.find_item.return_value = object()
        command = AddColumnsCommand(app_context, "ds-1", column_names=["b"], reference_positions=[0])

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "ds-1" in caplog.text and "not a Dataset" in caplog.text

    def test_execute_logs_warning_when_dataset_empty(self, mock_app_context, sample_project, caplog):
        app_context, app_state, _ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame())
        sample_project.find_item.return_value = dataset
        command = AddColumnsCommand(app_context, "ds-1", column_names=["b"], reference_positions=[0])

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "ds-1" in caplog.text and "no data" in caplog.text.lower()

    def test_execute_logs_warning_when_reference_position_out_of_bounds(self, mock_app_context, sample_project, caplog):
        app_context, app_state, _ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
        sample_project.find_item.return_value = dataset
        command = AddColumnsCommand(app_context, "ds-1", column_names=["b"], reference_positions=[5])

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "5" in caplog.text

    def test_execute_logs_warning_when_columns_already_exist(self, mock_app_context, sample_project, caplog):
        app_context, app_state, _ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
        sample_project.find_item.return_value = dataset
        command = AddColumnsCommand(app_context, "ds-1", column_names=["a"], reference_positions=[0])

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "already exist" in caplog.text.lower()

    def test_execute_logs_warning_when_duplicate_names_in_input(self, mock_app_context, sample_project, caplog):
        app_context, app_state, _ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
        sample_project.find_item.return_value = dataset
        command = AddColumnsCommand(app_context, "ds-1", column_names=["b", "b"], reference_positions=[0, 0])

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "duplicate column names" in caplog.text.lower()

    def test_undo_logs_warning_when_nothing_to_undo(self, mock_app_context, caplog):
        app_context, _app_state, _ui_controller = mock_app_context
        command = AddColumnsCommand(app_context, "ds-1", column_names=["b"], reference_positions=[0])

        with caplog.at_level(logging.WARNING):
            result = command.undo()
        assert "ds-1" in caplog.text
        assert result is CommandResult.FAILURE


def test_cleanup_releases_the_original_data_snapshot():
    app_context = Mock(spec=AppContext)
    app_context.get_app_state.return_value = Mock(spec=AppState)
    app_context.get_ui_controller.return_value = Mock()

    command = AddColumnsCommand(
        app_context, "ds-1", column_names=["b"], reference_positions=[0], side="right"
    )
    command.original_data = pd.DataFrame({"a": [1, 2, 3]})

    command.cleanup()

    assert command.original_data is None


class TestAddColumnsRedoReplay:
    """#667: redo() replays the first insertion and keeps the added columns' ids."""

    @pytest.fixture
    def context_with_dataset(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock(spec=UIController)
        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller
        app_state.event_bus = Mock()
        app_state.has_project = True
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1.0, 2.0], "b": [3.0, 4.0]}))
        project = Mock()
        project.find_item = Mock(return_value=dataset)
        app_state.current_project = project
        return app_context, app_state, ui_controller, dataset

    def test_redo_restores_the_column_ids_of_the_first_execute(self, context_with_dataset):
        app_context, _app_state, _ui, dataset = context_with_dataset
        command = AddColumnsCommand(app_context, "ds-1", column_names=["L", "R"], reference_positions=[0, 1], side="left")
        assert command.execute() is CommandResult.SUCCESS
        ids_after_execute = list(dataset.column_ids.items())
        data_after_execute = dataset.data.copy()

        assert command.undo() is CommandResult.SUCCESS
        assert command.redo() is CommandResult.SUCCESS

        assert list(dataset.column_ids.items()) == ids_after_execute
        pd.testing.assert_frame_equal(dataset.data, data_after_execute)

    def test_redo_does_not_retake_the_undo_snapshot_or_prompt(self, context_with_dataset):
        app_context, app_state, ui_controller, _dataset = context_with_dataset
        command = AddColumnsCommand(app_context, "ds-1", column_names=["c"], reference_positions=[1])
        assert command.execute() is CommandResult.SUCCESS
        snapshot = command.original_data
        assert command.undo() is CommandResult.SUCCESS
        app_state.event_bus.emit.reset_mock()

        assert command.redo() is CommandResult.SUCCESS

        assert command.original_data is snapshot
        assert ui_controller.method_calls == []
        app_state.event_bus.emit.assert_called_once()
        assert app_state.event_bus.emit.call_args.args[1]["column_positions"] == [2]

    def test_redo_twice_after_two_undos_keeps_the_same_ids(self, context_with_dataset):
        app_context, _app_state, _ui, dataset = context_with_dataset
        command = AddColumnsCommand(app_context, "ds-1", column_names=["c"], reference_positions=[1])
        assert command.execute() is CommandResult.SUCCESS
        created_id = dataset.column_id("c")

        for _ in range(2):
            assert command.undo() is CommandResult.SUCCESS
            assert command.redo() is CommandResult.SUCCESS

        assert dataset.column_id("c") == created_id

    def test_redo_aborts_when_the_column_already_exists(self, context_with_dataset):
        app_context, _app_state, _ui, dataset = context_with_dataset
        command = AddColumnsCommand(app_context, "ds-1", column_names=["c"], reference_positions=[1])
        assert command.execute() is CommandResult.SUCCESS
        before = dataset.data.copy()

        assert command.redo() is CommandResult.ABORTED

        pd.testing.assert_frame_equal(dataset.data, before)

    def test_redo_without_a_successful_execute_is_aborted(self, context_with_dataset):
        app_context, _app_state, _ui, _dataset = context_with_dataset
        command = AddColumnsCommand(app_context, "ds-1", column_names=["c"], reference_positions=[1])

        assert command.redo() is CommandResult.ABORTED
