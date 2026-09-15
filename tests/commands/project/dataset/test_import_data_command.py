"""Tests for ImportDataCommand's read path (_read_frames).

Covers that the wizard's parse options are honored and that multi-sheet Excel
workbooks yield one correctly-named dataset per selected sheet. The interactive
wizard and background threading are not exercised here.
"""

import logging
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.commands.project.dataset.add_imported_datasets_command import AddImportedDatasetsCommand
from pandaplot.commands.project.dataset.import_data_command import ImportDataCommand
from pandaplot.models.project.items import Dataset
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


def test_cleanup_does_not_raise():
    """ImportDataCommand never occupies an undo slot (see #301), so
    CommandExecutor never calls cleanup() on it -- this only guards the
    documented no-op."""
    command = ImportDataCommand(Mock())

    command.cleanup()  # must not raise


def test_occupies_undo_slot_is_false():
    """The dispatching command must not land on the undo stack -- the real,
    undoable effect is AddImportedDatasetsCommand, executed once the
    background read completes (see #301)."""
    command = ImportDataCommand(Mock())

    assert command.occupies_undo_slot() is False


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
        app_state.event_bus = Mock()
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
            assert command.execute() is CommandResult.FAILURE
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
        assert result is CommandResult.FAILURE  # failure because the *import* wizard was cancelled, not the project offer

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
            assert command.execute() is CommandResult.FAILURE
        assert "no project" in caplog.text.lower()
        ui_controller.show_action_or_cancel.assert_called_once()

    def test_undo_is_a_success_noop(self, mock_app_context):
        """Unreachable via CommandExecutor (occupies_undo_slot() is False),
        so undo() is just a documented no-op -- see #301."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        command = ImportDataCommand(app_context)

        assert command.undo() is CommandResult.SUCCESS


class TestOnImportResult:
    """Tests for `_on_import_result`'s handoff to AddImportedDatasetsCommand:
    the real, undo-tracked effect of a completed import (see #301)."""

    @pytest.fixture
    def mock_app_context(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock()
        project = Mock()

        app_state.has_project = True
        app_state.current_project = project
        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller
        app_context.get_task_scheduler.return_value = Mock()

        return app_context, app_state, ui_controller, project

    def _dataset(self, name="ds"):
        return Dataset(name=name, data=pd.DataFrame({"a": [1, 2]}))

    def test_success_constructs_and_executes_add_imported_datasets_command(self, mock_app_context):
        app_context, app_state, ui_controller, project = mock_app_context
        command = ImportDataCommand(app_context, folder_id="folder-1")
        command.project = project
        executor = app_context.get_command_executor.return_value
        executor.execute_command.return_value = True
        dataset = self._dataset("ds")

        command._on_import_result({"success": True, "datasets": [dataset], "file_path": "/tmp/ds.csv"})

        executor.execute_command.assert_called_once()
        (executed_command,), _ = executor.execute_command.call_args
        assert isinstance(executed_command, AddImportedDatasetsCommand)
        assert executed_command.datasets == [dataset]
        assert executed_command.folder_id == "folder-1"
        assert executed_command.file_path == "/tmp/ds.csv"
        ui_controller.show_info_message.assert_called_once()
        ui_controller.show_error_message.assert_not_called()

    def test_failure_to_add_shows_error_and_no_success_message(self, mock_app_context):
        """If AddImportedDatasetsCommand itself fails to execute (e.g. the
        project rejects a duplicate id), the failure must be surfaced to the
        user instead of silently reporting success."""
        app_context, app_state, ui_controller, project = mock_app_context
        command = ImportDataCommand(app_context)
        command.project = project
        executor = app_context.get_command_executor.return_value
        executor.execute_command.return_value = False

        command._on_import_result({"success": True, "datasets": [self._dataset()], "file_path": "/tmp/ds.csv"})

        ui_controller.show_error_message.assert_called_once()
        title, message = ui_controller.show_error_message.call_args[0]
        assert title == "Import Failed"
        ui_controller.show_info_message.assert_not_called()


class TestImportDataCommandUndoStackIntegrity:
    """Regression tests for #301: an Undo triggered while the background
    import is still running must not corrupt the undo/redo stacks. Uses a
    real CommandExecutor (not a mock) since the bug was in how the executor's
    stack bookkeeping interacted with this command's occupies_undo_slot()."""

    @pytest.fixture
    def wired_app_context(self, tmp_path):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock()
        task_scheduler = Mock()

        inserted_items = {}

        def _add_item(item, parent_id=None):
            item.parent_id = parent_id
            inserted_items[item.id] = item

        def _find_item(item_id):
            return inserted_items.get(item_id)

        def _remove_item(item):
            inserted_items.pop(item.id, None)

        project = Mock()
        project.add_item.side_effect = _add_item
        project.find_item.side_effect = _find_item
        project.remove_item.side_effect = _remove_item

        app_state.has_project = True
        app_state.current_project = project
        app_state.event_bus = Mock()

        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller
        app_context.get_task_scheduler.return_value = task_scheduler

        executor = CommandExecutor()
        app_context.get_command_executor.return_value = executor

        csv_path = tmp_path / "data.csv"
        csv_path.write_text("a,b\n1,2\n", encoding="utf-8")

        return app_context, ui_controller, task_scheduler, project, executor, str(csv_path)

    @patch("pandaplot.gui.dialogs.import_wizard_dialog.ImportWizardDialog")
    def test_undo_mid_import_leaves_stacks_consistent(self, mock_dialog_cls, wired_app_context):
        from PySide6.QtWidgets import QDialog

        app_context, ui_controller, task_scheduler, project, executor, csv_path = wired_app_context

        dialog = mock_dialog_cls.return_value
        dialog.exec.return_value = QDialog.DialogCode.Accepted
        dialog.get_file_path.return_value = csv_path
        dialog.get_import_options.return_value = ImportOptions(file_format=CSV_FORMAT)
        dialog.get_dataset_name.return_value = "data"
        dialog.get_selected_sheets.return_value = None

        command = ImportDataCommand(app_context)
        assert executor.execute_command(command) is True

        # execute() only dispatched the background read; nothing landed on
        # the undo stack yet, so this command isn't occupying a slot with
        # empty undo state -- the exact scenario that used to corrupt the
        # stacks (see #301).
        assert executor.undo_stack == []
        assert executor.redo_stack == []

        # An Undo triggered "mid-import" now correctly finds nothing to
        # undo, instead of popping this command and reporting a bogus undo.
        assert executor.undo() is False
        assert executor.undo_stack == []
        assert executor.redo_stack == []

        # The background read now completes: TaskScheduler.run_task was
        # called with the on_result callback that _on_import_result wires up.
        _, run_task_kwargs = task_scheduler.run_task.call_args
        on_result = run_task_kwargs["on_result"]
        dataset = Dataset(name="data", data=pd.DataFrame({"a": [1], "b": [2]}))
        on_result({"success": True, "datasets": [dataset], "file_path": csv_path})

        # Only now does a real, undo-tracked command land on the stack.
        assert len(executor.undo_stack) == 1
        assert isinstance(executor.undo_stack[0], AddImportedDatasetsCommand)
        assert project.find_item(dataset.id) is dataset

        # Undo now genuinely works.
        assert executor.undo() is True
        assert project.find_item(dataset.id) is None
        assert len(executor.redo_stack) == 1
