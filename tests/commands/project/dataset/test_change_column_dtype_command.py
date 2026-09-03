import logging
from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.dataset.change_column_dtype_command import ChangeColumnDtypeCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state import AppContext, AppState


class TestChangeColumnDtypeCommand:
    """Test suite for ChangeColumnDtypeCommand."""

    @pytest.fixture
    def mock_app_context(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock(spec=UIController)

        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller
        app_context.event_bus = Mock()
        app_context.event_bus.emit = Mock()

        return app_context, app_state, ui_controller

    @pytest.fixture
    def sample_project(self):
        project = Mock()
        project.find_item = Mock()
        return project

    def test_int_column_with_only_whole_numbers_converts_to_float64(self, mock_app_context, sample_project):
        """A column of whole-number ints (e.g. 1, 2, 3) must actually become
        float64 when the user picks 'Decimal' -- pd.to_numeric alone keeps
        such a column as int64 since every value downcasts cleanly."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2, 3]}))
        sample_project.find_item.return_value = dataset

        command = ChangeColumnDtypeCommand(app_context, "ds-1", 0, "float64")
        result = command.execute()

        assert result is CommandResult.SUCCESS
        assert str(dataset.data["a"].dtype) == "float64"

    def test_column_already_of_target_dtype_is_a_noop(self, mock_app_context, sample_project):
        """Nothing is converted (or pushed onto the undo stack) when the
        column is already the requested dtype."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1.0, 2.0, 3.0]}))
        sample_project.find_item.return_value = dataset

        command = ChangeColumnDtypeCommand(app_context, "ds-1", 0, "float64")
        result = command.execute()

        assert result is CommandResult.NOOP
        ui_controller.show_info_message.assert_called_once()


class TestChangeColumnDtypeCommandLogging:
    """Tests that genuine failure paths log a warning instead of failing silently."""

    @pytest.fixture
    def mock_app_context(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock(spec=UIController)

        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller
        app_context.event_bus = Mock()
        app_context.event_bus.emit = Mock()

        return app_context, app_state, ui_controller

    @pytest.fixture
    def sample_project(self):
        project = Mock()
        project.find_item = Mock()
        return project

    def test_execute_logs_warning_when_no_project(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        command = ChangeColumnDtypeCommand(app_context, "ds-1", 0, "float64")

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "no project" in caplog.text.lower()

    def test_execute_logs_warning_when_current_project_none(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None
        command = ChangeColumnDtypeCommand(app_context, "ds-1", 0, "float64")

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "current_project is None" in caplog.text

    def test_execute_logs_warning_when_dataset_not_found(self, mock_app_context, sample_project, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        sample_project.find_item.return_value = None
        command = ChangeColumnDtypeCommand(app_context, "missing-ds", 0, "float64")

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "missing-ds" in caplog.text

    def test_execute_logs_warning_when_item_not_a_dataset(self, mock_app_context, sample_project, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        sample_project.find_item.return_value = object()
        command = ChangeColumnDtypeCommand(app_context, "ds-1", 0, "float64")

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "ds-1" in caplog.text and "not a Dataset" in caplog.text

    def test_execute_logs_warning_when_dataset_empty(self, mock_app_context, sample_project, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame())
        sample_project.find_item.return_value = dataset
        command = ChangeColumnDtypeCommand(app_context, "ds-1", 0, "float64")

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "ds-1" in caplog.text and "no data" in caplog.text.lower()

    def test_execute_logs_warning_when_column_index_out_of_range(self, mock_app_context, sample_project, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
        sample_project.find_item.return_value = dataset
        command = ChangeColumnDtypeCommand(app_context, "ds-1", 5, "float64")

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "5" in caplog.text

    def test_execute_logs_warning_when_conversion_fails(self, mock_app_context, sample_project, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
        sample_project.find_item.return_value = dataset
        command = ChangeColumnDtypeCommand(app_context, "ds-1", 0, "unsupported_type")

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "ds-1" in caplog.text and "conversion" in caplog.text.lower()

    def test_undo_logs_warning_when_nothing_to_undo(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        command = ChangeColumnDtypeCommand(app_context, "ds-1", 0, "float64")

        with caplog.at_level(logging.WARNING):
            command.undo()
        assert "ds-1" in caplog.text

    def test_redo_logs_warning_when_nothing_to_redo(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        command = ChangeColumnDtypeCommand(app_context, "ds-1", 0, "float64")

        with caplog.at_level(logging.WARNING):
            command.redo()
        assert "ds-1" in caplog.text


def test_cleanup_releases_the_original_data_snapshot():
    app_context = Mock(spec=AppContext)
    app_context.get_app_state.return_value = Mock(spec=AppState)
    app_context.get_ui_controller.return_value = Mock()

    command = ChangeColumnDtypeCommand(app_context, "ds-1", 0, "float64")
    command.original_data = pd.Series([1, 2, 3])

    command.cleanup()

    assert command.original_data is None
