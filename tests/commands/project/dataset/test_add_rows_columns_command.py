import logging
from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.dataset.add_rows_columns_command import (
    AddRowsColumnsCommand,
)
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import DatasetOperationEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state import AppContext, AppState


@pytest.fixture
def mock_app_context():
    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    ui_controller = Mock(spec=UIController)
    ui_controller.parent_widget = None  # not on the spec: set on the instance

    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = ui_controller
    app_state.event_bus = Mock()
    app_state.event_bus.emit = Mock()
    app_state.has_project = True

    return app_context, app_state, ui_controller


@pytest.fixture
def project_with(mock_app_context):
    """Build a project whose find_item resolves the given dataset."""
    _, app_state, _ = mock_app_context

    def _build(dataset):
        project = Mock()
        project.find_item = Mock(return_value=dataset)
        project.get_all_items = Mock(return_value=[dataset])
        app_state.current_project = project
        return project

    return _build


def _emitted(app_state):
    return {call.args[0]: call.args[1] for call in app_state.event_bus.emit.call_args_list}


class TestAddRowsColumnsCommand:
    def test_grows_the_table_to_the_requested_size(self, mock_app_context, project_with):
        app_context, app_state, _ = mock_app_context
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
        project_with(dataset)

        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=4, target_columns=3)

        assert command.execute() is CommandResult.SUCCESS
        assert dataset.data.shape == (4, 3)
        assert list(dataset.data.columns) == ["a", "Column2", "Column3"]

    def test_new_cells_use_per_column_defaults(self, mock_app_context, project_with):
        app_context, _, _ = mock_app_context
        data = pd.DataFrame({"i": [1], "f": [1.5], "s": ["x"], "b": [True]})
        dataset = Dataset(id="ds-1", name="Test", data=data)
        project_with(dataset)

        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=2, target_columns=5)

        assert command.execute() is CommandResult.SUCCESS
        added_row = dataset.data.iloc[1]
        assert added_row["i"] == 0
        assert added_row["f"] == 0.0
        assert added_row["s"] == ""
        assert bool(added_row["b"]) is False
        # New columns match AddColumnsCommand's default: float64 zeros.
        assert str(dataset.data["Column5"].dtype) == "float64"
        assert dataset.data["Column5"].tolist() == [0.0, 0.0]

    def test_rows_only_leaves_the_columns_untouched(self, mock_app_context, project_with):
        app_context, app_state, _ = mock_app_context
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
        project_with(dataset)

        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=5, target_columns=1)

        assert command.execute() is CommandResult.SUCCESS
        assert dataset.data.shape == (5, 1)
        emitted = _emitted(app_state)
        assert DatasetOperationEvents.DATASET_ROW_ADDED in emitted
        assert DatasetOperationEvents.DATASET_COLUMN_ADDED not in emitted
        assert emitted[DatasetOperationEvents.DATASET_ROW_ADDED]["row_positions"] == [2, 3, 4]

    def test_columns_only_emits_the_appended_positions(self, mock_app_context, project_with):
        app_context, app_state, _ = mock_app_context
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
        project_with(dataset)

        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=2, target_columns=3)

        assert command.execute() is CommandResult.SUCCESS
        emitted = _emitted(app_state)
        assert DatasetOperationEvents.DATASET_ROW_ADDED not in emitted
        assert emitted[DatasetOperationEvents.DATASET_COLUMN_ADDED]["column_positions"] == [1, 2]

    def test_a_smaller_target_never_drops_data(self, mock_app_context, project_with):
        app_context, _, ui_controller = mock_app_context
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]}))
        project_with(dataset)

        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=1, target_columns=1)

        assert command.execute() is CommandResult.NOOP
        assert dataset.data.shape == (3, 2)
        ui_controller.show_info_message.assert_called_once()

    def test_new_column_names_do_not_collide_with_existing_ones(self, mock_app_context, project_with):
        app_context, _, _ = mock_app_context
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"Column2": [1], "Column3": [2]}))
        project_with(dataset)

        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=1, target_columns=4)

        assert command.execute() is CommandResult.SUCCESS
        assert len(set(dataset.data.columns)) == 4
        assert list(dataset.data.columns)[:2] == ["Column2", "Column3"]

    def test_an_empty_dataset_gets_both_columns_and_rows(self, mock_app_context, project_with):
        app_context, _, _ = mock_app_context
        dataset = Dataset(id="ds-1", name="Empty", data=pd.DataFrame())
        project_with(dataset)

        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=3, target_columns=2)

        assert command.execute() is CommandResult.SUCCESS
        assert dataset.data.shape == (3, 2)

    def test_undo_restores_the_original_data(self, mock_app_context, project_with):
        app_context, app_state, _ = mock_app_context
        original = pd.DataFrame({"a": [1, 2]})
        dataset = Dataset(id="ds-1", name="Test", data=original.copy())
        project_with(dataset)

        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=4, target_columns=2)
        assert command.execute() is CommandResult.SUCCESS
        assert command.undo() is CommandResult.SUCCESS

        pd.testing.assert_frame_equal(dataset.data, original)
        emitted = _emitted(app_state)
        assert emitted[DatasetOperationEvents.DATASET_ROW_REMOVED]["row_positions"] == [2, 3]
        assert emitted[DatasetOperationEvents.DATASET_COLUMN_REMOVED]["column_positions"] == [1]

    def test_undo_is_a_no_op_when_execute_did_nothing(self, mock_app_context, project_with):
        app_context, _, _ = mock_app_context
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
        project_with(dataset)

        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=1, target_columns=1)
        assert command.execute() is CommandResult.NOOP
        command.undo()

        assert dataset.data.shape == (2, 1)

    def test_redo_reapplies_without_reprompting(self, mock_app_context, project_with):
        app_context, _, _ = mock_app_context
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
        project_with(dataset)

        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=4, target_columns=2)
        assert command.execute() is CommandResult.SUCCESS
        assert command.undo() is CommandResult.SUCCESS
        assert command.redo() is CommandResult.SUCCESS

        assert dataset.data.shape == (4, 2)

    def test_requires_an_open_project(self, mock_app_context):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False

        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=4, target_columns=2)

        assert command.execute() is CommandResult.FAILURE
        ui_controller.show_warning_message.assert_called_once()

    def test_requires_an_open_project_logs_a_warning(self, mock_app_context, caplog):
        app_context, app_state, _ = mock_app_context
        app_state.has_project = False

        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=4, target_columns=2)

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "no project" in caplog.text.lower()

    def test_current_project_none_logs_a_warning(self, mock_app_context, caplog):
        app_context, app_state, _ = mock_app_context
        app_state.has_project = True
        app_state.current_project = None

        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=4, target_columns=2)

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "current_project is none" in caplog.text.lower()

    def test_reports_a_missing_dataset(self, mock_app_context, project_with):
        app_context, _, ui_controller = mock_app_context
        project = project_with(Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1]})))
        project.find_item.return_value = None

        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=4, target_columns=2)

        assert command.execute() is CommandResult.FAILURE
        ui_controller.show_error_message.assert_called_once()

    def test_reports_a_missing_dataset_logs_a_warning(self, mock_app_context, project_with, caplog):
        app_context, _, _ = mock_app_context
        project = project_with(Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1]})))
        project.find_item.return_value = None

        command = AddRowsColumnsCommand(app_context, "missing-ds", target_rows=4, target_columns=2)

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "missing-ds" in caplog.text

    def test_no_dataset_selected_logs_a_warning(self, mock_app_context, project_with, caplog):
        app_context, _, _ = mock_app_context
        project_with(Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1]})))

        command = AddRowsColumnsCommand(app_context, dataset_id=None, target_rows=4, target_columns=2)

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "no dataset selected" in caplog.text.lower()

    def test_item_not_a_dataset_logs_a_warning(self, mock_app_context, project_with, caplog):
        app_context, _, _ = mock_app_context
        project_with(Mock(spec=[]))  # not a Dataset instance

        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=4, target_columns=2)

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "ds-1" in caplog.text

    def test_undo_logs_warning_when_nothing_to_undo(self, mock_app_context, caplog):
        app_context, _, _ = mock_app_context
        command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=4, target_columns=2)

        with caplog.at_level(logging.WARNING):
            result = command.undo()
        assert "ds-1" in caplog.text
        assert result is CommandResult.FAILURE


class TestAddRowsColumnsCommandPrompt:
    def test_prompts_for_the_target_when_none_was_given(self, mock_app_context, project_with, monkeypatch):
        app_context, _, _ = mock_app_context
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
        project_with(dataset)

        dialog = Mock()
        dialog.exec.return_value = 1  # QDialog.DialogCode.Accepted
        dialog.get_dataset_id.return_value = "ds-1"
        dialog.get_target_rows.return_value = 5
        dialog.get_target_columns.return_value = 2
        dialog_cls = Mock(return_value=dialog)
        monkeypatch.setattr(
            "pandaplot.gui.dialogs.dataset.add_rows_columns_dialog.AddRowsColumnsDialog",
            dialog_cls,
        )

        command = AddRowsColumnsCommand(app_context)

        assert command.execute() is CommandResult.SUCCESS
        assert dataset.data.shape == (5, 2)
        # The dialog is offered the datasets in the project, with their sizes.
        options = dialog_cls.call_args.args[0]
        assert [(o.id, o.rows, o.columns) for o in options] == [("ds-1", 2, 1)]

    def test_cancelling_the_dialog_changes_nothing(self, mock_app_context, project_with, monkeypatch):
        app_context, _, _ = mock_app_context
        dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2]}))
        project_with(dataset)

        dialog = Mock()
        dialog.exec.return_value = 0  # QDialog.DialogCode.Rejected
        monkeypatch.setattr(
            "pandaplot.gui.dialogs.dataset.add_rows_columns_dialog.AddRowsColumnsDialog",
            Mock(return_value=dialog),
        )

        command = AddRowsColumnsCommand(app_context)

        assert command.execute() is CommandResult.FAILURE
        assert dataset.data.shape == (2, 1)

    def test_warns_when_the_project_has_no_datasets(self, mock_app_context):
        app_context, app_state, ui_controller = mock_app_context
        project = Mock()
        project.get_all_items = Mock(return_value=[])
        app_state.current_project = project

        command = AddRowsColumnsCommand(app_context)

        assert command.execute() is CommandResult.FAILURE
        ui_controller.show_warning_message.assert_called_once()

    def test_warns_when_the_project_has_no_datasets_logs_a_warning(self, mock_app_context, caplog):
        app_context, app_state, _ = mock_app_context
        project = Mock()
        project.get_all_items = Mock(return_value=[])
        app_state.current_project = project

        command = AddRowsColumnsCommand(app_context)

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "no datasets" in caplog.text.lower()


def test_cleanup_releases_the_original_data_snapshot():
    app_context = Mock(spec=AppContext)
    app_context.get_app_state.return_value = Mock(spec=AppState)
    app_context.get_ui_controller.return_value = Mock()

    command = AddRowsColumnsCommand(app_context, "ds-1", target_rows=4, target_columns=3)
    command.original_data = pd.DataFrame({"a": [1, 2, 3]})

    command.cleanup()

    assert command.original_data is None
