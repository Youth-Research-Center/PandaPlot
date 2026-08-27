"""Tests for ImportDataCommand's read path (_read_frames).

Covers that the wizard's parse options are honored and that multi-sheet Excel
workbooks yield one correctly-named dataset per selected sheet. The interactive
wizard and background threading are not exercised here.
"""

import logging
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from pandaplot.commands.project.dataset.import_data_command import ImportDataCommand
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.services.data_import import CSV_FORMAT, EXCEL_FORMAT, ImportOptions


def _make_command(file_path, options, name, sheets=None):
    command = ImportDataCommand(Mock())
    command.file_path = file_path
    command.import_options = options
    command.dataset_name = name
    command.selected_sheets = sheets
    return command


def test_read_frames_honors_delimiter_and_header(tmp_path):
    path = tmp_path / "data.csv"
    path.write_text("10;20;30\n40;50;60\n", encoding="utf-8")
    options = ImportOptions(file_format=CSV_FORMAT, delimiter=";", has_header=False)

    command = _make_command(str(path), options, "data")
    frames = command._read_frames()

    assert len(frames) == 1
    name, df = frames[0]
    assert name == "data"
    assert list(df.columns) == ["Column 1", "Column 2", "Column 3"]
    assert df.iloc[0].tolist() == [10, 20, 30]


def test_cleanup_releases_the_imported_datasets():
    from pandaplot.models.project.items.dataset import Dataset

    command = ImportDataCommand(Mock())
    command.imported_datasets = [Dataset(name="ds", data=pd.DataFrame({"a": [1, 2]}))]

    command.cleanup()

    assert command.imported_datasets == []


def test_read_frames_single_excel_sheet_named_after_file(tmp_path):
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"a": [1, 2]}).to_excel(writer, sheet_name="One", index=False)
        pd.DataFrame({"b": [3]}).to_excel(writer, sheet_name="Two", index=False)

    command = _make_command(str(path), ImportOptions(file_format=EXCEL_FORMAT), "book", sheets=["One"])
    frames = command._read_frames()

    assert len(frames) == 1
    assert frames[0][0] == "book"
    assert list(frames[0][1].columns) == ["a"]


def test_read_frames_multiple_excel_sheets_suffixed(tmp_path):
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"a": [1, 2]}).to_excel(writer, sheet_name="One", index=False)
        pd.DataFrame({"b": [3]}).to_excel(writer, sheet_name="Two", index=False)
        pd.DataFrame({"c": [7, 8, 9]}).to_excel(writer, sheet_name="Three", index=False)

    command = _make_command(str(path), ImportOptions(file_format=EXCEL_FORMAT), "book", sheets=["One", "Three"])
    frames = command._read_frames()

    assert [name for name, _ in frames] == ["book - One", "book - Three"]
    assert frames[1][1].shape == (3, 1)


def test_read_frames_falls_back_to_first_sheet_when_none_selected(tmp_path):
    path = tmp_path / "book.xlsx"
    with pd.ExcelWriter(path) as writer:
        pd.DataFrame({"a": [1]}).to_excel(writer, sheet_name="Only", index=False)

    options = ImportOptions(file_format=EXCEL_FORMAT, sheet_name="Only")
    command = _make_command(str(path), options, "book", sheets=None)
    frames = command._read_frames()

    assert len(frames) == 1
    assert list(frames[0][1].columns) == ["a"]


class TestImportDataCommandLogging:
    """Tests that genuine failure paths log a warning instead of failing silently."""

    @pytest.fixture
    def mock_app_context(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock()

        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller
        app_context.get_task_scheduler.return_value = Mock()

        return app_context, app_state, ui_controller

    def test_execute_logs_warning_when_no_project(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        ui_controller.show_action_or_cancel.return_value = False
        command = ImportDataCommand(app_context)

        with caplog.at_level(logging.WARNING):
            assert command.execute() is False
        assert "no project" in caplog.text.lower()
        ui_controller.show_action_or_cancel.assert_called_once()

    @patch("pandaplot.gui.dialogs.import_wizard_dialog.ImportWizardDialog")
    def test_execute_continues_after_the_user_creates_a_project(self, mock_dialog_cls, mock_app_context):
        from PySide6.QtWidgets import QDialog

        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        ui_controller.show_action_or_cancel.return_value = True

        project = Mock()

        def _execute_command(command):
            app_state.has_project = True
            app_state.current_project = project

        app_context.get_command_executor.return_value.execute_command.side_effect = _execute_command

        mock_dialog = mock_dialog_cls.return_value
        mock_dialog.exec.return_value = QDialog.DialogCode.Rejected  # cancel the *import* wizard itself

        command = ImportDataCommand(app_context)
        result = command.execute()

        # Proceeded past the "no project" gate (opened the import wizard)
        # instead of returning False immediately for lack of a project.
        mock_dialog_cls.assert_called_once()
        assert result is False  # false because the *import* wizard was cancelled, not the project offer

    def test_execute_logs_warning_when_current_project_none(self, mock_app_context, caplog):
        """has_project=True but current_project=None is the same inconsistent
        state the "no project" branch already recovers from -- it must also
        offer to create a project here, not silently fail."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None
        ui_controller.show_action_or_cancel.return_value = False
        command = ImportDataCommand(app_context)

        with caplog.at_level(logging.WARNING):
            assert command.execute() is False
        assert "no project" in caplog.text.lower()
        ui_controller.show_action_or_cancel.assert_called_once()

    def test_undo_logs_warning_when_nothing_to_undo(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        command = ImportDataCommand(app_context)

        with caplog.at_level(logging.WARNING):
            command.undo()
        assert "cannot undo" in caplog.text.lower()
