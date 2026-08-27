import logging
import math
from unittest.mock import Mock, patch

import pytest

from pandaplot.commands.project.dataset.create_empty_dataset_command import CreateEmptyDatasetCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project import Project
from pandaplot.models.state import AppContext, AppState


class TestCreateEmptyDatasetCommand:
    @pytest.fixture
    def mock_app_context(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock(spec=UIController)
        ui_controller.parent_widget = None

        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller
        app_state.event_bus = Mock()
        app_state.event_bus.emit = Mock()

        return app_context, app_state, ui_controller

    @pytest.fixture
    def sample_project(self):
        project = Project("Test Project")
        project.find_item = Mock()
        project.add_item = Mock()
        project.remove_item = Mock()
        return project

    def test_programmatic_name_skips_dialog_and_uses_legacy_shape(
        self, mock_app_context, sample_project
    ):
        """When dataset_name is supplied (e.g. by a test or other programmatic
        caller), no dialog opens and the dataset keeps today's fixed
        3-column/1-row/'' shape -- there is no channel to pass rows/cols/fill
        without the dialog, so this path is intentionally unchanged."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        with patch(
            "pandaplot.commands.project.dataset.create_empty_dataset_command.NewDatasetDialog"
        ) as mock_dialog_cls:
            command = CreateEmptyDatasetCommand(app_context, dataset_name="Programmatic")
            result = command.execute()

        assert result is True
        mock_dialog_cls.assert_not_called()
        dataset = sample_project.add_item.call_args[0][0]
        assert list(dataset.data.columns) == ["Column1", "Column2", "Column3"]
        assert dataset.data.shape == (1, 3)
        # pandas>=3.0 (pinned in pyproject.toml) infers pure-string columns as
        # the "str" dtype rather than legacy "object"; the assertion tracks
        # that actual behavior rather than a pre-pandas-3.0 assumption.
        assert str(dataset.data["Column1"].dtype) == "str"
        assert dataset.data["Column1"].tolist() == [""]

    def test_dialog_accepted_builds_float64_dataframe_with_nan(
        self, mock_app_context, sample_project
    ):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        mock_dialog = Mock()
        mock_dialog.exec.return_value = 1  # QDialog.DialogCode.Accepted == 1
        mock_dialog.get_dataset_name.return_value = "My Dataset"
        mock_dialog.get_rows.return_value = 5
        mock_dialog.get_columns.return_value = 2
        mock_dialog.get_fill_value.return_value = math.nan

        with patch(
            "pandaplot.commands.project.dataset.create_empty_dataset_command.NewDatasetDialog",
            return_value=mock_dialog,
        ):
            command = CreateEmptyDatasetCommand(app_context)
            result = command.execute()

        assert result is True
        dataset = sample_project.add_item.call_args[0][0]
        assert dataset.name == "My Dataset"
        assert list(dataset.data.columns) == ["Column1", "Column2"]
        assert dataset.data.shape == (5, 2)
        assert str(dataset.data["Column1"].dtype) == "float64"
        assert dataset.data["Column1"].isna().all()

    def test_dialog_accepted_with_zero_fill_value(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        mock_dialog = Mock()
        mock_dialog.exec.return_value = 1
        mock_dialog.get_dataset_name.return_value = "Zeros"
        mock_dialog.get_rows.return_value = 3
        mock_dialog.get_columns.return_value = 1
        mock_dialog.get_fill_value.return_value = 0.0

        with patch(
            "pandaplot.commands.project.dataset.create_empty_dataset_command.NewDatasetDialog",
            return_value=mock_dialog,
        ):
            command = CreateEmptyDatasetCommand(app_context)
            result = command.execute()

        assert result is True
        dataset = sample_project.add_item.call_args[0][0]
        assert dataset.data.shape == (3, 1)
        assert str(dataset.data["Column1"].dtype) == "float64"
        assert dataset.data["Column1"].tolist() == [0.0, 0.0, 0.0]

    def test_dialog_cancelled_aborts_creation(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        mock_dialog = Mock()
        mock_dialog.exec.return_value = 0  # QDialog.DialogCode.Rejected == 0

        with patch(
            "pandaplot.commands.project.dataset.create_empty_dataset_command.NewDatasetDialog",
            return_value=mock_dialog,
        ):
            command = CreateEmptyDatasetCommand(app_context)
            result = command.execute()

        assert result is False
        sample_project.add_item.assert_not_called()
        app_state.event_bus.emit.assert_not_called()

    def test_redo_reuses_dialog_shape_instead_of_legacy_default(
        self, mock_app_context, sample_project
    ):
        """Regression test: create a dataset via the dialog with a non-default
        shape, undo it, then redo it. Before the fix, redo() re-ran execute()
        with self.dataset_name already set, which took the 'programmatic name'
        branch and silently rebuilt the dataset as the legacy 1x3/'' shape
        instead of the shape originally chosen in the dialog."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        mock_dialog = Mock()
        mock_dialog.exec.return_value = 1  # QDialog.DialogCode.Accepted == 1
        mock_dialog.get_dataset_name.return_value = "My Dataset"
        mock_dialog.get_rows.return_value = 5
        mock_dialog.get_columns.return_value = 2
        mock_dialog.get_fill_value.return_value = math.nan

        with patch(
            "pandaplot.commands.project.dataset.create_empty_dataset_command.NewDatasetDialog",
            return_value=mock_dialog,
        ):
            command = CreateEmptyDatasetCommand(app_context)
            result = command.execute()

        assert result is True

        # Undo removes the dataset.
        command.undo()

        # Redo re-runs execute(); the dialog must NOT be re-opened, and the
        # dataset re-added should match the originally chosen shape.
        with patch(
            "pandaplot.commands.project.dataset.create_empty_dataset_command.NewDatasetDialog"
        ) as mock_dialog_cls_on_redo:
            redo_result = command.redo()

        assert redo_result is True
        mock_dialog_cls_on_redo.assert_not_called()

        assert sample_project.add_item.call_count == 2
        first_dataset = sample_project.add_item.call_args_list[0][0][0]
        redone_dataset = sample_project.add_item.call_args_list[1][0][0]

        for dataset in (first_dataset, redone_dataset):
            assert list(dataset.data.columns) == ["Column1", "Column2"]
            assert dataset.data.shape == (5, 2)
            assert str(dataset.data["Column1"].dtype) == "float64"
            assert dataset.data["Column1"].isna().all()

    def test_no_project_loaded_shows_warning_before_opening_dialog(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False

        with patch(
            "pandaplot.commands.project.dataset.create_empty_dataset_command.NewDatasetDialog"
        ) as mock_dialog_cls, caplog.at_level(logging.WARNING):
            command = CreateEmptyDatasetCommand(app_context)
            result = command.execute()

        assert result is False
        mock_dialog_cls.assert_not_called()
        ui_controller.show_warning_message.assert_called_once_with(
            "Create Dataset", "Please open or create a project first."
        )
        assert "no project" in caplog.text.lower()

    def test_execute_logs_warning_when_current_project_none(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None

        command = CreateEmptyDatasetCommand(app_context, dataset_name="Programmatic")
        with caplog.at_level(logging.WARNING):
            result = command.execute()

        assert result is False
        assert "current_project is None" in caplog.text

    def test_undo_logs_warning_when_nothing_to_undo(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        command = CreateEmptyDatasetCommand(app_context, dataset_name="Never executed")

        with caplog.at_level(logging.WARNING):
            command.undo()
        assert "cannot undo" in caplog.text.lower()

    def test_redo_logs_warning_when_no_dataset_name(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        command = CreateEmptyDatasetCommand(app_context)

        with caplog.at_level(logging.WARNING):
            command.redo()
        assert "cannot redo" in caplog.text.lower()

    def test_cleanup_releases_the_dataset_id_and_project_reference(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        command = CreateEmptyDatasetCommand(app_context, dataset_name="Programmatic")
        command.dataset_id = "ds-1"
        command.project = sample_project

        command.cleanup()

        assert command.dataset_id is None
        assert command.project is None
