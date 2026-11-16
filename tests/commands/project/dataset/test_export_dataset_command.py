"""Tests for ExportDatasetCommand's failure-path logging.

Only exercises the warning-logging behavior added when execute()/redo()
early-return on a genuine failure condition; not a full command test suite.
"""

import logging
from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.dataset.export_dataset_command import ExportDatasetCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState


def test_marks_project_modified_is_false():
    """Regression (PR #235 review): exporting only writes an external file
    and never mutates the project, so it must not flag the project as
    having unsaved changes."""
    assert ExportDatasetCommand(Mock(spec=AppContext), "ds-1").marks_project_modified() is False


@pytest.fixture
def mock_app_context():
    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    ui_controller = Mock(spec=UIController)

    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = ui_controller
    app_context.get_task_scheduler.return_value = Mock()

    return app_context, app_state, ui_controller


@pytest.fixture
def sample_project():
    project = Mock()
    project.find_item = Mock()
    return project


def test_execute_logs_warning_when_no_project(mock_app_context, caplog):
    app_context, app_state, _ui_controller = mock_app_context
    app_state.has_project = False
    command = ExportDatasetCommand(app_context, "ds-1")

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "no project" in caplog.text.lower()


def test_execute_logs_warning_when_current_project_none(mock_app_context, caplog):
    app_context, app_state, _ui_controller = mock_app_context
    app_state.has_project = True
    app_state.current_project = None
    command = ExportDatasetCommand(app_context, "ds-1")

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "current_project is None" in caplog.text


def test_execute_logs_warning_when_dataset_not_found(mock_app_context, sample_project, caplog):
    app_context, app_state, _ui_controller = mock_app_context
    app_state.has_project = True
    app_state.current_project = sample_project
    sample_project.find_item.return_value = None
    command = ExportDatasetCommand(app_context, "missing-ds")

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "missing-ds" in caplog.text


def test_execute_logs_warning_when_item_not_a_dataset(mock_app_context, sample_project, caplog):
    app_context, app_state, _ui_controller = mock_app_context
    app_state.has_project = True
    app_state.current_project = sample_project
    sample_project.find_item.return_value = object()
    command = ExportDatasetCommand(app_context, "ds-1")

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "ds-1" in caplog.text and "not a Dataset" in caplog.text


def test_execute_logs_warning_when_dataset_empty(mock_app_context, sample_project, caplog):
    app_context, app_state, _ui_controller = mock_app_context
    app_state.has_project = True
    app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame())
    sample_project.find_item.return_value = dataset
    command = ExportDatasetCommand(app_context, "ds-1")

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "ds-1" in caplog.text and "no data" in caplog.text.lower()


def test_redo_logs_warning_when_nothing_to_redo(mock_app_context, caplog):
    app_context, _app_state, _ui_controller = mock_app_context
    command = ExportDatasetCommand(app_context, "ds-1")

    with caplog.at_level(logging.WARNING):
        assert command.redo() is CommandResult.FAILURE
    assert "cannot redo" in caplog.text.lower()


def test_occupies_undo_slot_returns_false(mock_app_context):
    """ExportDatasetCommand's undo() is a documented no-op, so it must never
    occupy an undo slot -- its only call site (DatasetTab.export_data) relies
    on this to keep it off the undo stack when routed through
    CommandExecutor.execute_command()."""
    app_context, _app_state, _ui_controller = mock_app_context
    command = ExportDatasetCommand(app_context, "ds-1")

    assert command.occupies_undo_slot() is False


def test_cleanup_releases_the_project_and_dataset_references(mock_app_context, sample_project):
    app_context, _app_state, _ui_controller = mock_app_context
    command = ExportDatasetCommand(app_context, "ds-1")
    command.project = sample_project
    command.dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1]}))

    command.cleanup()

    assert command.project is None
    assert command.dataset is None


class TestExportFailureMessages:
    """The export worker sends a plain-language ErrorDescription, never raw exception text (#595)."""

    def _command(self, mock_app_context, export_path, export_format="CSV (Comma Separated Values)"):
        app_context, _app_state, _ui_controller = mock_app_context
        command = ExportDatasetCommand(app_context, "ds-1")
        command.dataset = Dataset(name="ds", data=pd.DataFrame({"a": [1, 2]}))
        command.export_path = export_path
        command.export_format = export_format
        return command

    def test_unwritable_path_gives_a_described_failure(self, mock_app_context, tmp_path):
        from pandaplot.utils.error_messages import ErrorDescription

        blocker = tmp_path / "blocker"
        blocker.write_text("a file, not a folder", encoding="utf-8")
        command = self._command(mock_app_context, str(blocker / "out.csv"))

        result = command._export_data_task(None)

        assert result["success"] is False
        description = result["error_description"]
        assert isinstance(description, ErrorDescription)
        assert description.reason == "The computer could not read or write the file."
        assert description.details

    def test_non_exception_failure_keeps_its_plain_reason(self, mock_app_context):
        command = self._command(mock_app_context, "/tmp/out.xyz", export_format="Bogus")

        result = command._export_data_task(None)

        assert result["success"] is False
        assert result["error_description"].reason == "PandaPlot cannot export to this file format."
        assert result["error_description"].details == ""

    def test_failed_export_dialog_shows_the_description_not_the_raw_text(self, mock_app_context):
        from pandaplot.utils.error_messages import describe_error

        _app_context, _app_state, ui_controller = mock_app_context
        command = self._command(mock_app_context, "/tmp/out.csv")
        description = describe_error(PermissionError("denied"))

        command._on_export_result({"success": False, "error": "Error during data export: raw", "error_description": description})

        ui_controller.show_error_message.assert_called_once_with("Export Failed", "Couldn't export the dataset.", error=description)

    def test_worker_error_signal_passes_the_exception(self, mock_app_context):
        _app_context, _app_state, ui_controller = mock_app_context
        command = self._command(mock_app_context, "/tmp/out.csv")
        error = OSError("disk full")

        command._on_export_error((OSError, error, "traceback"))

        ui_controller.show_error_message.assert_called_once_with("Export Error", "Couldn't export the dataset.", error=error)


CSV_FORMAT = "CSV (Comma Separated Values)"


@pytest.fixture
def export_context(mock_app_context, sample_project, sync_task_scheduler):
    """An app context whose current project holds one non-empty dataset and whose
    task scheduler runs the export inline."""
    app_context, app_state, ui_controller = mock_app_context
    app_context.get_task_scheduler.return_value = sync_task_scheduler
    app_state.has_project = True
    app_state.current_project = sample_project
    dataset = Dataset(id="ds-1", name="Measurements", data=pd.DataFrame({"x": [1, 2, 3], "y": [4.0, 5.5, 6.0]}))
    sample_project.find_item.return_value = dataset
    return app_context, ui_controller, dataset


class TestExecuteEndToEnd:
    """execute() asks for a path, runs the export through the task scheduler and reports the outcome."""

    def test_cancelled_dialog_writes_nothing_and_starts_no_task(self, export_context, tmp_path):
        app_context, ui_controller, _dataset = export_context
        ui_controller.show_export_dataset_dialog.return_value = None
        scheduler = Mock()
        app_context.get_task_scheduler.return_value = scheduler
        command = ExportDatasetCommand(app_context, "ds-1")

        assert command.execute() is CommandResult.FAILURE

        scheduler.run_task.assert_not_called()
        assert command.is_exporting is False
        assert command.export_path is None
        assert list(tmp_path.iterdir()) == []

    def test_successful_export_writes_the_file_and_reports_success(self, export_context, tmp_path):
        app_context, ui_controller, dataset = export_context
        target = tmp_path / "nested" / "out.csv"
        ui_controller.show_export_dataset_dialog.return_value = (str(target), CSV_FORMAT)
        command = ExportDatasetCommand(app_context, "ds-1")

        assert command.execute() is CommandResult.SUCCESS

        pd.testing.assert_frame_equal(pd.read_csv(target), dataset.data)
        assert command.is_exporting is False
        ui_controller.show_error_message.assert_not_called()
        titles = [call.args[0] for call in ui_controller.show_info_message.call_args_list]
        assert titles == ["Export Starting", "Export Successful"]
        assert str(target) in ui_controller.show_info_message.call_args_list[-1].args[1]

    def test_disk_error_during_export_reports_failure_and_clears_busy_flag(self, export_context, tmp_path):
        app_context, ui_controller, _dataset = export_context
        blocker = tmp_path / "blocker"
        blocker.write_text("a file, not a folder", encoding="utf-8")
        ui_controller.show_export_dataset_dialog.return_value = (str(blocker / "out.csv"), CSV_FORMAT)
        command = ExportDatasetCommand(app_context, "ds-1")

        # execute() only dispatches the export, so it succeeds; the failure arrives through the result callback.
        assert command.execute() is CommandResult.SUCCESS

        assert command.is_exporting is False
        ui_controller.show_error_message.assert_called_once()
        assert ui_controller.show_error_message.call_args.args[:2] == ("Export Failed", "Couldn't export the dataset.")

    def test_unexpected_exception_returns_failure_and_shows_error(self, export_context):
        app_context, ui_controller, _dataset = export_context
        error = RuntimeError("dialog exploded")
        ui_controller.show_export_dataset_dialog.side_effect = error
        command = ExportDatasetCommand(app_context, "ds-1")

        assert command.execute() is CommandResult.FAILURE

        ui_controller.show_error_message.assert_called_once_with("Export Dataset Error", "Couldn't export the dataset.", error=error)

    def test_undo_is_a_noop_and_redo_rewrites_the_same_file(self, export_context, tmp_path):
        app_context, ui_controller, dataset = export_context
        target = tmp_path / "out.csv"
        ui_controller.show_export_dataset_dialog.return_value = (str(target), CSV_FORMAT)
        command = ExportDatasetCommand(app_context, "ds-1")
        assert command.execute() is CommandResult.SUCCESS

        assert command.undo() is CommandResult.NOOP
        assert target.exists(), "undo must not delete the exported file"

        target.unlink()
        assert command.redo() is CommandResult.SUCCESS

        pd.testing.assert_frame_equal(pd.read_csv(target), dataset.data)
        # redo replays the original export; it must not ask for a path again.
        ui_controller.show_export_dataset_dialog.assert_called_once()

    def test_redo_refuses_while_an_export_is_still_running(self, mock_app_context):
        app_context, _app_state, _ui_controller = mock_app_context
        scheduler = Mock()
        app_context.get_task_scheduler.return_value = scheduler
        command = ExportDatasetCommand(app_context, "ds-1")
        command.export_path = "/tmp/out.csv"
        command.export_format = CSV_FORMAT
        command.is_exporting = True

        assert command.redo() is CommandResult.FAILURE

        scheduler.run_task.assert_not_called()


class TestExportTask:
    """The background export function for every format and failure shape."""

    def _command(self, mock_app_context, export_path, export_format=CSV_FORMAT):
        app_context, _app_state, _ui_controller = mock_app_context
        command = ExportDatasetCommand(app_context, "ds-1")
        command.dataset = Dataset(name="ds", data=pd.DataFrame({"a": [1, 2], "b": ["x", "y"]}))
        command.export_path = export_path
        command.export_format = export_format
        return command

    @pytest.mark.parametrize(
        ("export_format", "reader"),
        [
            ("TSV (Tab Separated Values)", lambda path: pd.read_csv(path, sep="\t")),
            ("JSON (Records format)", lambda path: pd.read_json(path, orient="records")),
            ("Pickle (pandas format)", pd.read_pickle),
        ],
    )
    def test_formats_round_trip_and_report_progress(self, mock_app_context, tmp_path, export_format, reader):
        extension = ExportDatasetCommand.SUPPORTED_FORMATS[export_format]["extension"]
        target = tmp_path / f"out{extension}"
        command = self._command(mock_app_context, str(target), export_format)
        progress: list[float] = []

        result = command._export_data_task(progress.append)

        assert result == {"success": True, "error": None, "path": str(target)}
        pd.testing.assert_frame_equal(reader(target), command.dataset.data)
        assert progress == [0.1, 0.2, 0.3, 0.4, 0.5, 0.9, 1.0]

    def test_html_export_writes_a_table(self, mock_app_context, tmp_path):
        target = tmp_path / "out.html"
        command = self._command(mock_app_context, str(target), "HTML Table")

        assert command._export_data_task(None)["success"] is True

        assert "<table" in target.read_text(encoding="utf-8")

    def test_missing_export_path_fails_without_writing(self, mock_app_context):
        command = self._command(mock_app_context, None)

        result = command._export_data_task(None)

        assert result["success"] is False
        assert result["error"] == "Missing dataset or export path"
        assert result["path"] is None

    def test_dataframe_without_the_export_method_fails_cleanly(self, mock_app_context, tmp_path):
        command = self._command(mock_app_context, str(tmp_path / "out.csv"))
        command.dataset = Mock(spec=Dataset)
        command.dataset.data = Mock(spec=[])

        result = command._export_data_task(None)

        assert result["success"] is False
        assert "not supported in this pandas version" in result["error"]
        assert not (tmp_path / "out.csv").exists()

    @pytest.mark.parametrize(
        ("export_format", "method_name", "missing_library", "expected"),
        [
            ("Excel Workbook", "to_excel", "No module named 'openpyxl'", "requires openpyxl"),
            ("Parquet", "to_parquet", "Missing optional dependency 'pyarrow'", "requires pyarrow or fastparquet"),
        ],
    )
    def test_missing_optional_writer_library_gives_install_hint(
        self, mock_app_context, tmp_path, monkeypatch, export_format, method_name, missing_library, expected
    ):
        command = self._command(mock_app_context, str(tmp_path / "out.bin"), export_format)
        monkeypatch.setattr(pd.DataFrame, method_name, Mock(side_effect=ImportError(missing_library)))

        result = command._export_data_task(None)

        assert result["success"] is False
        assert expected in result["error"]
        assert result["error_description"].details

    @pytest.mark.parametrize(("export_format", "method_name"), [("Excel Workbook", "to_excel"), ("Parquet", "to_parquet")])
    def test_unrelated_import_error_is_reported_as_a_generic_failure(self, mock_app_context, tmp_path, monkeypatch, export_format, method_name):
        command = self._command(mock_app_context, str(tmp_path / "out.bin"), export_format)
        monkeypatch.setattr(pd.DataFrame, method_name, Mock(side_effect=ImportError("some other module")))

        result = command._export_data_task(None)

        assert result["success"] is False
        assert result["error"].startswith("Error during data export:")
        assert "install" not in result["error"]

    @pytest.mark.parametrize(("export_format", "method_name"), [("Excel Workbook", "to_excel"), ("Parquet", "to_parquet")])
    def test_optional_writer_formats_call_the_pandas_writer(self, mock_app_context, tmp_path, monkeypatch, export_format, method_name):
        target = str(tmp_path / "out.bin")
        command = self._command(mock_app_context, target, export_format)
        writer = Mock()
        monkeypatch.setattr(pd.DataFrame, method_name, writer)

        assert command._export_data_task(None)["success"] is True

        writer.assert_called_once_with(target, index=False)


class TestExportCallbacks:
    """Callback handlers never let an exception escape into the task scheduler."""

    def test_result_handler_survives_a_failing_dialog(self, mock_app_context):
        app_context, _app_state, ui_controller = mock_app_context
        command = ExportDatasetCommand(app_context, "ds-1")
        command.is_exporting = True
        ui_controller.show_info_message.side_effect = RuntimeError("dialog failed")

        command._on_export_result({"success": True, "error": None, "path": "/tmp/out.csv"})

        assert command.is_exporting is False
        ui_controller.show_error_message.assert_called_once()
        assert ui_controller.show_error_message.call_args.args[0] == "Export Error"

    def test_successful_result_without_dataset_names_it_unknown(self, mock_app_context):
        app_context, _app_state, ui_controller = mock_app_context
        command = ExportDatasetCommand(app_context, "ds-1")

        command._on_export_result({"success": True, "error": None, "path": "/tmp/out.csv"})

        assert "'Unknown'" in ui_controller.show_info_message.call_args.args[1]

    def test_failed_result_without_description_uses_a_generic_one(self, mock_app_context):
        app_context, _app_state, ui_controller = mock_app_context
        command = ExportDatasetCommand(app_context, "ds-1")

        command._on_export_result({"success": False, "error": "boom"})

        description = ui_controller.show_error_message.call_args.kwargs["error"]
        assert description.reason == "The dataset could not be exported."

    def test_error_handler_survives_a_failing_dialog(self, mock_app_context, caplog):
        app_context, _app_state, ui_controller = mock_app_context
        command = ExportDatasetCommand(app_context, "ds-1")
        command.is_exporting = True
        ui_controller.show_error_message.side_effect = RuntimeError("dialog failed")

        with caplog.at_level(logging.ERROR):
            command._on_export_error((OSError, OSError("disk full"), "traceback"))

        assert command.is_exporting is False
        assert "Error handling export error" in caplog.text

    def test_finished_handler_clears_busy_flag(self, mock_app_context):
        app_context, _app_state, _ui_controller = mock_app_context
        command = ExportDatasetCommand(app_context, "ds-1")
        command.is_exporting = True

        command._on_export_finished()

        assert command.is_exporting is False

    def test_progress_handler_logs_percentages_and_survives_bad_values(self, mock_app_context, caplog):
        app_context, _app_state, _ui_controller = mock_app_context
        command = ExportDatasetCommand(app_context, "ds-1")

        with caplog.at_level(logging.DEBUG, logger="ExportDatasetCommand"):
            command._on_export_progress(0.5)
            command._on_export_progress("not a number")

        assert "Export progress: 50%" in caplog.text
        assert "Error handling export progress" in caplog.text
