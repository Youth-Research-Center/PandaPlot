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
from pandaplot.models.project import Project
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.image import ImageGallery
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


def test_cleanup_is_a_documented_noop():
    """ImportDataCommand never occupies an undo slot (see #301), so
    CommandExecutor never calls cleanup() on it -- this only guards the
    documented no-op."""
    command = ImportDataCommand(Mock())
    state_before = dict(vars(command))

    assert command.cleanup() is None

    assert vars(command) == state_before


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
        app_context, app_state, _ui_controller = mock_app_context
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
        app_context, _app_state, ui_controller, project = mock_app_context
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
        app_context, _app_state, ui_controller, project = mock_app_context
        command = ImportDataCommand(app_context)
        command.project = project
        executor = app_context.get_command_executor.return_value
        executor.execute_command.return_value = False

        command._on_import_result({"success": True, "datasets": [self._dataset()], "file_path": "/tmp/ds.csv"})

        ui_controller.show_error_message.assert_called_once()
        title, _message = ui_controller.show_error_message.call_args[0]
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

        app_context, _ui_controller, task_scheduler, project, executor, csv_path = wired_app_context

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


class TestImportFailureMessages:
    """The import worker sends a plain-language ErrorDescription, never raw exception text (#595)."""

    def test_ragged_csv_gives_a_described_failure(self, tmp_path):
        from pandaplot.utils.error_messages import ErrorDescription

        path = tmp_path / "ragged.csv"
        path.write_text("a,b\n1,2\n3,4,5,6\n7,8\n", encoding="utf-8")
        command = _make_command(str(path), ImportOptions(file_format=CSV_FORMAT, delimiter=",", has_header=True), "ragged")

        result = command._import_data_task(None)

        assert result["success"] is False
        description = result["error_description"]
        assert isinstance(description, ErrorDescription)
        assert description.reason == "The rows in the file do not match its columns."
        assert "ParserError" in description.details

    def test_empty_file_keeps_its_plain_reason(self, tmp_path):
        path = tmp_path / "header_only.csv"
        path.write_text("a,b\n", encoding="utf-8")
        command = _make_command(str(path), ImportOptions(file_format=CSV_FORMAT, delimiter=",", has_header=True), "header_only")

        result = command._import_data_task(None)

        assert result["success"] is False
        assert result["error_description"].reason == "The selected file is empty."
        assert result["error_description"].details == ""

    def test_failed_import_dialog_shows_the_description_not_the_raw_text(self):
        from pandaplot.utils.error_messages import describe_error

        app_context = Mock()
        command = ImportDataCommand(app_context)
        description = describe_error(UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"))

        command._on_import_result({"success": False, "error": "Failed to read file: raw", "error_description": description})

        command.ui_controller.show_error_message.assert_called_once_with(
            "Import Failed", "Couldn't import the data.", error=description
        )

    def test_worker_error_signal_passes_the_exception(self):
        command = ImportDataCommand(Mock())
        error = MemoryError()

        command._on_import_error((MemoryError, error, "traceback"))

        command.ui_controller.show_error_message.assert_called_once_with(
            "Import Data Error", "Couldn't import the data.", error=error
        )


WIZARD_PATH = "pandaplot.gui.dialogs.import_wizard_dialog.ImportWizardDialog"


@pytest.fixture
def import_env(tmp_path, sync_task_scheduler):
    """A real project and CommandExecutor, with the background read run inline."""
    project = Project(name="Import target")
    app_state = Mock(spec=AppState)
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = Mock()
    ui_controller = Mock()
    executor = CommandExecutor()

    app_context = Mock(spec=AppContext)
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = ui_controller
    app_context.get_task_scheduler.return_value = sync_task_scheduler
    app_context.get_command_executor.return_value = executor

    csv_path = tmp_path / "data.csv"
    csv_path.write_text("a,b\n1,2\n3,4\n", encoding="utf-8")
    return app_context, app_state, ui_controller, project, executor, str(csv_path)


def _accept_wizard(mock_dialog_cls, file_path, name="data", sheets=None):
    from PySide6.QtWidgets import QDialog

    dialog = mock_dialog_cls.return_value
    dialog.exec.return_value = QDialog.DialogCode.Accepted
    dialog.get_file_path.return_value = file_path
    dialog.get_import_options.return_value = ImportOptions(file_format=CSV_FORMAT, delimiter=",", has_header=True)
    dialog.get_dataset_name.return_value = name
    dialog.get_selected_sheets.return_value = sheets
    return dialog


def _project_datasets(project):
    return [item for item in project.get_all_items() if isinstance(item, Dataset)]


class TestImportEndToEnd:
    """execute() -> background read -> AddImportedDatasetsCommand, with undo and redo through the executor."""

    @patch(WIZARD_PATH)
    def test_import_adds_dataset_and_undo_redo_replay_the_same_dataset(self, mock_dialog_cls, import_env):
        app_context, app_state, ui_controller, project, executor, csv_path = import_env
        _accept_wizard(mock_dialog_cls, csv_path)
        command = ImportDataCommand(app_context)

        assert command.execute() is CommandResult.SUCCESS

        assert command.is_importing is False
        datasets = _project_datasets(project)
        assert [d.name for d in datasets] == ["data"]
        pd.testing.assert_frame_equal(datasets[0].data, pd.DataFrame({"a": [1, 3], "b": [2, 4]}))
        assert datasets[0].source_file == csv_path
        app_state.mark_modified.assert_called_once()
        ui_controller.show_error_message.assert_not_called()
        imported_id = datasets[0].id

        assert executor.undo() is True
        assert _project_datasets(project) == []

        assert executor.redo() is True
        assert [d.id for d in _project_datasets(project)] == [imported_id]

    @patch(WIZARD_PATH)
    def test_cancelled_wizard_adds_nothing(self, mock_dialog_cls, import_env):
        from PySide6.QtWidgets import QDialog

        app_context, _app_state, _ui_controller, project, executor, _csv_path = import_env
        mock_dialog_cls.return_value.exec.return_value = QDialog.DialogCode.Rejected
        command = ImportDataCommand(app_context)

        assert command.execute() is CommandResult.FAILURE

        assert command.is_importing is False
        assert _project_datasets(project) == []
        assert executor.undo_stack == []

    def test_second_import_while_one_is_running_is_refused(self, import_env):
        app_context, _app_state, ui_controller, _project, _executor, _csv_path = import_env
        command = ImportDataCommand(app_context)
        command.is_importing = True

        assert command.execute() is CommandResult.FAILURE

        ui_controller.show_info_message.assert_called_once_with("Import In Progress", "A data import is already in progress.")

    @patch(WIZARD_PATH)
    def test_file_deleted_after_the_wizard_fails_before_reading(self, mock_dialog_cls, import_env, tmp_path):
        app_context, _app_state, ui_controller, project, _executor, _csv_path = import_env
        _accept_wizard(mock_dialog_cls, str(tmp_path / "gone.csv"))
        command = ImportDataCommand(app_context)

        assert command.execute() is CommandResult.FAILURE

        assert command.is_importing is False
        assert ui_controller.show_error_message.call_args.args[0] == "Import Data Error"
        assert _project_datasets(project) == []

    @patch(WIZARD_PATH)
    def test_unsupported_extension_is_rejected(self, mock_dialog_cls, import_env, tmp_path):
        app_context, _app_state, ui_controller, project, _executor, _csv_path = import_env
        path = tmp_path / "data.xyz"
        path.write_text("a,b\n1,2\n", encoding="utf-8")
        _accept_wizard(mock_dialog_cls, str(path))
        command = ImportDataCommand(app_context)

        assert command.execute() is CommandResult.FAILURE

        assert command.is_importing is False
        assert "Unsupported file type '.xyz'" in ui_controller.show_error_message.call_args.args[1]
        assert _project_datasets(project) == []

    @patch(WIZARD_PATH)
    def test_unexpected_error_resets_the_busy_flag(self, mock_dialog_cls, import_env):
        app_context, _app_state, ui_controller, _project, _executor, csv_path = import_env
        _accept_wizard(mock_dialog_cls, csv_path)
        error = RuntimeError("scheduler down")
        scheduler = Mock()
        scheduler.run_task.side_effect = error
        app_context.get_task_scheduler.return_value = scheduler
        command = ImportDataCommand(app_context)

        assert command.execute() is CommandResult.FAILURE

        assert command.is_importing is False
        ui_controller.show_error_message.assert_called_once_with("Import Data Error", "Couldn't import the data.", error=error)

    @patch(WIZARD_PATH)
    def test_unreadable_file_shows_error_and_adds_nothing(self, mock_dialog_cls, import_env, tmp_path):
        app_context, app_state, ui_controller, project, executor, _csv_path = import_env
        path = tmp_path / "ragged.csv"
        path.write_text("a,b\n1,2\n3,4,5,6\n", encoding="utf-8")
        _accept_wizard(mock_dialog_cls, str(path))
        command = ImportDataCommand(app_context)

        assert command.execute() is CommandResult.SUCCESS

        assert ui_controller.show_error_message.call_args.args[:2] == ("Import Failed", "Couldn't import the data.")
        assert _project_datasets(project) == []
        assert executor.undo_stack == []
        app_state.mark_modified.assert_not_called()

    def test_add_failure_leaves_the_project_unmodified(self, import_env):
        app_context, app_state, ui_controller, project, executor, _csv_path = import_env
        gallery = ImageGallery(name="Photos")
        project.add_item(gallery)
        command = ImportDataCommand(app_context, folder_id=gallery.id)
        command.project = project

        command._on_import_result({"success": True, "datasets": [Dataset(name="d", data=pd.DataFrame({"a": [1]}))], "file_path": "/tmp/d.csv"})

        assert ui_controller.show_error_message.call_args.args[0] == "Import Failed"
        assert _project_datasets(project) == []
        assert executor.undo_stack == []
        app_state.mark_modified.assert_not_called()


class TestImportTask:
    """The background read function's failure shapes and progress reporting."""

    def test_progress_is_reported_in_order(self, tmp_path):
        path = tmp_path / "data.csv"
        path.write_text("a\n1\n", encoding="utf-8")
        command = _make_command(str(path), ImportOptions(file_format=CSV_FORMAT, delimiter=",", has_header=True), "data")
        progress: list[float] = []

        result = command._import_data_task(progress.append)

        assert result["success"] is True
        assert progress == [0.1, 0.2, 0.6, 0.9, 1.0]

    def test_missing_file_returns_a_described_failure(self, tmp_path):
        command = _make_command(str(tmp_path / "gone.csv"), None, "gone")

        result = command._import_data_task(None)

        assert result["success"] is False
        assert result["datasets"] == []
        assert result["error"].startswith("File not found")
        assert result["error_description"].details

    def test_all_selected_sheets_empty_names_the_sheets(self, tmp_path):
        path = tmp_path / "book.xlsx"
        with pd.ExcelWriter(path) as writer:
            pd.DataFrame().to_excel(writer, sheet_name="One", index=False)
            pd.DataFrame().to_excel(writer, sheet_name="Two", index=False)
        command = _make_command(str(path), ImportOptions(file_format=EXCEL_FORMAT), "book", sheets=["One", "Two"])

        result = command._import_data_task(None)

        assert result["success"] is False
        assert result["error"] == "The selected sheet(s) contain no data."

    def test_empty_sheets_are_dropped_from_a_multi_sheet_import(self, tmp_path):
        path = tmp_path / "book.xlsx"
        with pd.ExcelWriter(path) as writer:
            pd.DataFrame({"a": [1]}).to_excel(writer, sheet_name="Full", index=False)
            pd.DataFrame().to_excel(writer, sheet_name="Blank", index=False)
        command = _make_command(str(path), ImportOptions(file_format=EXCEL_FORMAT), "book", sheets=["Full", "Blank"])

        result = command._import_data_task(None)

        assert result["success"] is True
        assert [d.name for d in result["datasets"]] == ["book - Full"]

    def test_unexpected_error_after_reading_returns_a_failure(self, tmp_path, monkeypatch):
        from pandaplot.commands.project.dataset import import_data_command

        path = tmp_path / "data.csv"
        path.write_text("a\n1\n", encoding="utf-8")
        command = _make_command(str(path), ImportOptions(file_format=CSV_FORMAT, delimiter=",", has_header=True), "data")
        monkeypatch.setattr(import_data_command, "Dataset", Mock(side_effect=MemoryError("out of memory")))

        result = command._import_data_task(None)

        assert result["success"] is False
        assert result["datasets"] == []
        assert result["error"].startswith("Error during data import:")


class TestImportResultGuards:
    """_on_import_result must not add datasets to a project that changed while the read ran."""

    @pytest.fixture
    def env(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock()
        project = Mock()
        app_state.has_project = True
        app_state.current_project = project
        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller
        app_context.get_task_scheduler.return_value = Mock()
        command = ImportDataCommand(app_context)
        command.project = project
        command.is_importing = True
        return command, app_context, app_state, ui_controller

    def _result(self, count=1):
        datasets = [Dataset(name=f"ds{i}", data=pd.DataFrame({"a": [1, 2]})) for i in range(count)]
        return {"success": True, "datasets": datasets, "file_path": "/tmp/book.xlsx"}

    def test_project_closed_during_import_adds_nothing(self, env):
        command, app_context, app_state, ui_controller = env
        app_state.has_project = False

        command._on_import_result(self._result())

        app_context.get_command_executor.assert_not_called()
        assert ui_controller.show_warning_message.call_args.args[0] == "Import Cancelled"
        assert "closed" in ui_controller.show_warning_message.call_args.args[1]
        assert command.is_importing is False
        app_state.mark_modified.assert_not_called()

    def test_project_replaced_during_import_adds_nothing(self, env):
        command, app_context, app_state, ui_controller = env
        app_state.current_project = Mock()

        command._on_import_result(self._result())

        app_context.get_command_executor.assert_not_called()
        assert "changed" in ui_controller.show_warning_message.call_args.args[1]
        app_state.mark_modified.assert_not_called()

    def test_multi_sheet_success_lists_every_dataset(self, env):
        command, app_context, app_state, ui_controller = env
        app_context.get_command_executor.return_value.execute_command.return_value = True

        command._on_import_result(self._result(count=2))

        message = ui_controller.show_info_message.call_args.args[1]
        assert "Successfully imported 2 sheets as datasets" in message
        assert "- ds0 (2 rows, 1 cols)" in message and "- ds1 (2 rows, 1 cols)" in message
        app_state.mark_modified.assert_called_once()

    def test_success_without_datasets_is_reported_as_a_failure(self, env):
        command, app_context, _app_state, ui_controller = env

        command._on_import_result({"success": True, "datasets": [], "file_path": "/tmp/x.csv"})

        app_context.get_command_executor.assert_not_called()
        ui_controller.show_error_message.assert_called_once_with("Import Failed", "Missing datasets or project in import result")

    def test_failed_result_without_description_uses_a_generic_one(self, env):
        command, _app_context, _app_state, ui_controller = env

        command._on_import_result({"success": False, "error": "boom"})

        assert ui_controller.show_error_message.call_args.kwargs["error"].reason == "The data could not be imported."

    def test_exception_while_adding_is_reported_not_raised(self, env):
        command, app_context, app_state, ui_controller = env
        error = RuntimeError("executor broke")
        app_context.get_command_executor.return_value.execute_command.side_effect = error

        command._on_import_result(self._result())

        ui_controller.show_error_message.assert_called_once_with("Import Error", "Couldn't import the data.", error=error)
        app_state.mark_modified.assert_not_called()

    def test_error_handler_survives_a_failing_dialog(self, env, caplog):
        command, _app_context, _app_state, ui_controller = env
        ui_controller.show_error_message.side_effect = RuntimeError("dialog failed")

        with caplog.at_level(logging.ERROR):
            command._on_import_error((OSError, OSError("disk"), "traceback"))

        assert command.is_importing is False
        assert "Error handling import error" in caplog.text

    def test_finished_handler_clears_busy_flag(self, env):
        command, *_ = env

        command._on_import_finished()

        assert command.is_importing is False

    def test_progress_handler_logs_and_survives_bad_values(self, env, caplog):
        command, *_ = env

        with caplog.at_level(logging.DEBUG, logger="ImportDataCommand"):
            command._on_import_progress(0.25)
            command._on_import_progress("bad")

        assert "Import progress: 25%" in caplog.text
        assert "Error handling import progress" in caplog.text

    def test_redo_is_a_success_noop(self, env):
        command, app_context, _app_state, _ui_controller = env

        assert command.redo() is CommandResult.SUCCESS

        app_context.get_command_executor.assert_not_called()
