"""Tests for SaveProjectCommand / SaveProjectAsCommand logging behavior."""

import logging
from unittest.mock import Mock

import pandas as pd

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.project.save_project_command import (
    SaveProjectAsCommand,
    SaveProjectCommand,
)
from pandaplot.models.events import EventBus
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state.app_state import AppState


def _make_app_context(*, has_project=True, current_project=None, project_file_path=None):
    app_state = Mock()
    app_state.has_project = has_project
    app_state.current_project = current_project
    app_state.project_file_path = project_file_path

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = Mock()
    return app_context, app_state


def test_execute_logs_a_warning_when_save_already_in_progress(caplog):
    app_context, _app_state = _make_app_context()
    command = SaveProjectCommand(app_context)
    command.is_saving = True

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "SaveProjectCommand.execute" in caplog.text


def test_execute_logs_a_warning_when_no_project_loaded(caplog):
    app_context, _app_state = _make_app_context(has_project=False)
    command = SaveProjectCommand(app_context)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "SaveProjectCommand.execute" in caplog.text


def test_execute_logs_a_warning_when_current_project_none(caplog):
    app_context, _app_state = _make_app_context(has_project=True, current_project=None)
    command = SaveProjectCommand(app_context)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "SaveProjectCommand.execute" in caplog.text


def test_save_as_execute_logs_a_warning_when_no_project_loaded(caplog):
    app_context, _app_state = _make_app_context(has_project=False)
    command = SaveProjectAsCommand(app_context)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "SaveProjectAsCommand.execute" in caplog.text


def test_save_as_execute_logs_a_warning_when_current_project_none(caplog):
    app_context, _app_state = _make_app_context(has_project=True, current_project=None)
    command = SaveProjectAsCommand(app_context)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "SaveProjectAsCommand.execute" in caplog.text


def test_marks_project_modified_is_false():
    """SaveProjectCommand clears AppState's dirty flag itself (via
    mark_saved) and must not be double-counted by CommandExecutor's generic
    on_project_modified hook. SaveProjectAsCommand inherits this."""
    app_context, _ = _make_app_context()
    assert SaveProjectCommand(app_context).marks_project_modified() is False
    assert SaveProjectAsCommand(app_context).marks_project_modified() is False


def test_on_save_result_marks_the_project_saved():
    """Regression (#209): a successful save must clear AppState.is_modified
    so the title bar / close confirmation stop treating the project as
    having unsaved changes."""
    project = Mock()
    project.name = "P"
    app_context, app_state = _make_app_context(has_project=True, current_project=project, project_file_path="/p.pplot")

    command = SaveProjectCommand(app_context)
    command.previous_file_path = "/p.pplot"
    command._dispatch_project = project  # as execute() would capture it
    command._on_save_result({"success": True, "project": project, "path": "/p.pplot"})

    app_state.mark_saved.assert_called_once()


def test_on_save_result_does_not_mark_saved_on_failure():
    app_context, app_state = _make_app_context()
    command = SaveProjectCommand(app_context)

    command._on_save_result({"success": False, "error": "disk full"})

    app_state.mark_saved.assert_not_called()


def _make_real_app_context(project_file_path):
    """A real AppState (not a Mock) with a project already loaded and
    modified -- needed to exercise mark_saved's revision-guard logic, which
    a Mock's recorded-call-args can't meaningfully stand in for."""
    app_state = AppState(EventBus())
    project = Mock()
    project.name = "P"
    project.project_file_path = project_file_path
    app_state.load_project(project)
    app_state.mark_modified()

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = Mock()
    app_context.get_manager.return_value = Mock()
    return app_context, app_state, project


def test_on_save_result_skips_clearing_modified_when_a_newer_edit_happened_during_save():
    """Regression: a save that started at revision N must not clear
    is_modified if another command modified the project in the async gap
    between the background save finishing and this callback running --
    that edit isn't reflected in what was actually written to disk."""
    app_context, app_state, project = _make_real_app_context("/p.pplot")

    command = SaveProjectCommand(app_context)
    command.previous_file_path = "/p.pplot"
    command._dispatch_project = project  # as execute() would capture it
    command._save_started_revision = app_state.modification_revision  # as execute() would capture it

    app_state.mark_modified()  # a newer edit lands before _on_save_result runs

    command._on_save_result({"success": True, "project": project, "path": "/p.pplot"})

    assert app_state.is_modified is True


def test_on_save_result_clears_modified_when_no_newer_edit_happened():
    app_context, app_state, project = _make_real_app_context("/p.pplot")

    command = SaveProjectCommand(app_context)
    command.previous_file_path = "/p.pplot"
    command._dispatch_project = project
    command._save_started_revision = app_state.modification_revision

    command._on_save_result({"success": True, "project": project, "path": "/p.pplot"})

    assert app_state.is_modified is False


def test_on_save_result_restores_modified_after_path_change_when_a_newer_edit_happened():
    """save_path != previous_file_path takes the load_project() branch,
    which unconditionally clears is_modified as a side effect of installing
    the (same) project object under its new path -- a newer edit during
    that async gap must still survive that reset."""
    app_context, app_state, project = _make_real_app_context("/new.pplot")

    command = SaveProjectCommand(app_context)
    command.previous_file_path = "/old.pplot"  # different -> triggers the load_project branch
    command._dispatch_project = project
    command._save_started_revision = app_state.modification_revision

    app_state.mark_modified()  # a newer edit lands before _on_save_result runs

    command._on_save_result({"success": True, "project": project, "path": "/new.pplot"})

    assert app_state.is_modified is True


def test_on_save_result_discards_a_result_for_a_project_that_is_no_longer_current():
    """Regression (PR #235 review): _on_save_result used to re-read
    AppState.current_project unconditionally, so if the active project
    changed (opened/created/closed) while a save was writing the *old*
    project to disk in the background, this would install the stale save
    result onto whatever project happens to be current now."""
    project = Mock()
    project.name = "Old"
    other_project = Mock()
    other_project.name = "New"
    app_context, app_state = _make_app_context(
        has_project=True, current_project=other_project, project_file_path="/other.pplot")

    command = SaveProjectCommand(app_context)
    command.previous_file_path = "/p.pplot"
    command._dispatch_project = project  # captured when the save for "Old" started

    command._on_save_result({"success": True, "project": project, "path": "/p.pplot"})

    app_state.mark_saved.assert_not_called()
    app_state.load_project.assert_not_called()


def test_on_save_result_does_not_discard_when_the_project_is_still_current():
    project = Mock()
    project.name = "P"
    app_context, app_state = _make_app_context(has_project=True, current_project=project, project_file_path="/p.pplot")

    command = SaveProjectCommand(app_context)
    command.previous_file_path = "/p.pplot"
    command._dispatch_project = project

    command._on_save_result({"success": True, "project": project, "path": "/p.pplot"})

    app_state.mark_saved.assert_called_once()


def test_save_project_task_uses_the_captured_project_and_path_not_app_state():
    """Regression (PR #235 review): the background task used to re-read
    AppState.current_project/project_file_path itself, racing the main
    thread. It must instead only ever touch the project/save_path passed
    into it."""
    app_context, _app_state = _make_app_context(has_project=True, current_project=Mock(), project_file_path="/other.pplot")
    project_manager = Mock()
    app_context.get_manager.return_value = project_manager

    command = SaveProjectCommand(app_context)
    captured_project = Mock()
    captured_project.name = "Captured"
    captured_project.project_file_path = "/captured.pplot"

    result = command._save_project_task(None, project=captured_project, save_path="/captured.pplot")

    project_manager.save_project.assert_called_once_with(captured_project, "/captured.pplot")
    assert result == {"success": True, "error": None, "path": "/captured.pplot", "project": captured_project}


def test_execute_captures_dispatch_project_and_begins_the_global_save_guard():
    app_context, app_state = _make_app_context(has_project=True, current_project=Mock(), project_file_path="/p.pplot")
    app_state.current_project.name = "P"
    app_state.is_saving = False
    app_state.modification_revision = 0
    task_scheduler = Mock()
    app_context.get_task_scheduler.return_value = task_scheduler

    command = SaveProjectCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS

    assert command._dispatch_project is app_state.current_project
    app_state.begin_save.assert_called_once()
    _, kwargs = task_scheduler.run_task.call_args
    assert kwargs["task_arguments"] == {"project": app_state.current_project, "save_path": "/p.pplot"}


def test_execute_rejects_a_concurrent_save_from_another_writer():
    """Regression (PR #235 review): a second, uncoordinated write to the
    same project file (e.g. the exit-time autosave in unsaved_changes.py)
    while a SaveProjectCommand is already saving could corrupt the file --
    ProjectDataManager.save() opens it in write mode. AppState.is_saving is
    the single source of truth every writer must check, not just this
    command instance's own is_saving flag."""
    app_context, app_state = _make_app_context(has_project=True, current_project=Mock(), project_file_path="/p.pplot")
    app_state.is_saving = True  # another writer (e.g. auto-save) is mid-save

    command = SaveProjectCommand(app_context)
    assert command.execute() is CommandResult.FAILURE
    app_context.get_task_scheduler.return_value.run_task.assert_not_called()


def test_on_save_finished_ends_the_global_save_guard():
    app_context, app_state = _make_app_context()
    command = SaveProjectCommand(app_context)

    command._on_save_finished()

    app_state.end_save.assert_called_once()


def test_does_not_occupy_undo_slot():
    app_context, _app_state = _make_app_context()
    command = SaveProjectCommand(app_context)

    assert command.occupies_undo_slot() is False


def test_undo_is_a_documented_noop():
    app_context, _app_state = _make_app_context()
    command = SaveProjectCommand(app_context)

    assert command.undo() is CommandResult.NOOP


def test_redo_is_a_documented_noop():
    app_context, _app_state = _make_app_context()
    command = SaveProjectCommand(app_context)

    assert command.redo() is CommandResult.NOOP


def test_save_task_failure_carries_an_error_description(tmp_path):
    from pandaplot.utils.error_messages import ErrorDescription

    app_context, _app_state = _make_app_context()
    project_manager = Mock()
    project_manager.save_project.side_effect = PermissionError("[Errno 13] Permission denied: '/x.pplot'")
    app_context.get_manager.return_value = project_manager
    project = Mock()
    project.project_file_path = "/x.pplot"
    command = SaveProjectCommand(app_context)

    result = command._save_project_task(None, project=project, save_path="/x.pplot")

    assert result["success"] is False
    description = result["error_description"]
    assert isinstance(description, ErrorDescription)
    assert description.reason == "PandaPlot is not allowed to open or change this file."
    assert "Permission denied" in description.details


def test_failed_save_dialog_shows_the_description_not_the_raw_text():
    from pandaplot.utils.error_messages import describe_error

    app_context, _app_state = _make_app_context()
    command = SaveProjectCommand(app_context)
    command._dispatch_project = _app_state.current_project
    description = describe_error(OSError(28, "No space left on device"))

    command._on_save_result({"success": False, "error": "Error during project save: raw", "error_description": description})

    app_context.get_ui_controller.return_value.show_error_message.assert_called_once_with(
        "Save Failed", "Couldn't save the project.", error=description
    )


def test_failed_save_without_a_description_falls_back_to_a_plain_reason():
    app_context, _app_state = _make_app_context()
    command = SaveProjectCommand(app_context)
    command._dispatch_project = _app_state.current_project

    command._on_save_result({"success": False, "error": "disk full"})

    kwargs = app_context.get_ui_controller.return_value.show_error_message.call_args.kwargs
    assert kwargs["error"].reason == "The project could not be saved."
    assert kwargs["error"].details == ""


def test_save_of_a_project_whose_path_is_inside_the_examples_dir_asks_for_a_new_location(tmp_path, monkeypatch):
    """Defence in depth (#607): a project that still carries a bundled example's
    path must never be written back to it; Save behaves as Save As."""
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    monkeypatch.setattr("pandaplot.utils.examples.get_examples_dir", lambda: examples_dir)
    app_context, app_state = _make_app_context(
        has_project=True, current_project=Mock(), project_file_path=str(examples_dir / "demo.pplot")
    )
    app_state.current_project.name = "P"
    app_state.is_saving = False
    app_state.modification_revision = 0
    chosen = str(tmp_path / "copy.pplot")
    app_context.get_ui_controller.return_value.show_save_project_dialog.return_value = chosen
    task_scheduler = Mock()
    app_context.get_task_scheduler.return_value = task_scheduler

    assert SaveProjectCommand(app_context).execute() is CommandResult.SUCCESS

    app_context.get_ui_controller.return_value.show_save_project_dialog.assert_called_once()
    _, kwargs = task_scheduler.run_task.call_args
    assert kwargs["task_arguments"]["save_path"] == chosen


def _examples_app_context(tmp_path, monkeypatch, *, project_file_path=None):
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    monkeypatch.setattr("pandaplot.utils.examples.get_examples_dir", lambda: examples_dir)
    app_context, app_state = _make_app_context(has_project=True, current_project=Mock(), project_file_path=project_file_path)
    app_state.current_project.name = "P"
    app_state.is_saving = False
    app_state.modification_revision = 0
    task_scheduler = Mock()
    app_context.get_task_scheduler.return_value = task_scheduler
    return app_context, app_state, examples_dir, task_scheduler


def test_save_as_into_the_examples_dir_is_refused(tmp_path, monkeypatch):
    """Regression (#607 review): Save As must not write a project into the bundled examples folder,
    or later saves (Ctrl+S, auto-save, the save on quit) would overwrite a bundled example."""
    app_context, app_state, examples_dir, task_scheduler = _examples_app_context(tmp_path, monkeypatch, project_file_path=str(tmp_path / "mine.pplot"))
    ui_controller = app_context.get_ui_controller.return_value
    ui_controller.show_save_project_dialog.return_value = str(examples_dir / "demo.pplot")

    assert SaveProjectAsCommand(app_context).execute() is CommandResult.FAILURE

    task_scheduler.run_task.assert_not_called()
    app_state.begin_save.assert_not_called()
    ui_controller.show_warning_message.assert_called_once()


def test_first_save_into_the_examples_dir_is_refused(tmp_path, monkeypatch):
    app_context, _app_state, examples_dir, task_scheduler = _examples_app_context(tmp_path, monkeypatch)
    ui_controller = app_context.get_ui_controller.return_value
    ui_controller.show_save_project_dialog.return_value = str(examples_dir / "sub" / "new.pplot")

    assert SaveProjectCommand(app_context).execute() is CommandResult.FAILURE

    task_scheduler.run_task.assert_not_called()
    ui_controller.show_warning_message.assert_called_once()


def _install_project(disk_env, path=None, name="Lab"):
    project = Project(name=name)
    project.add_item(Dataset(id="ds-1", name="Data", data=pd.DataFrame({"t": [0.0, 1.0], "v": [3.5, 4.5]})))
    project.project_file_path = str(path) if path is not None else None
    disk_env.app_state.load_project(project)
    disk_env.app_state.mark_modified()
    return project


class TestSaveToDisk:
    """The whole save path against real files: execute -> background write -> mark saved."""

    def test_save_writes_a_file_that_loads_back_and_clears_modified(self, disk_env, tmp_path):
        path = tmp_path / "lab.pplot"
        project = _install_project(disk_env, path)

        assert SaveProjectCommand(disk_env.app_context).execute() is CommandResult.SUCCESS

        assert disk_env.app_state.is_modified is False
        assert disk_env.app_state.is_saving is False
        reloaded = disk_env.project_manager.load_project(str(path))
        assert reloaded.name == "Lab"
        pd.testing.assert_frame_equal(reloaded.find_item("ds-1").data, project.find_item("ds-1").data)
        disk_env.session.update_project.assert_called_once_with(str(path))
        # A plain save to the existing file shows no dialog.
        disk_env.ui_controller.show_info_message.assert_not_called()

    def test_first_save_of_an_untitled_project_asks_for_a_path_and_adopts_it(self, disk_env, tmp_path):
        project = _install_project(disk_env)
        target = tmp_path / "new.pplot"
        disk_env.ui_controller.show_save_project_dialog.return_value = str(target)

        assert SaveProjectCommand(disk_env.app_context).execute() is CommandResult.SUCCESS

        disk_env.ui_controller.show_save_project_dialog.assert_called_once_with(default_name="Lab.pplot")
        assert target.exists()
        assert disk_env.app_state.current_project is project
        assert disk_env.app_state.project_file_path == str(target)
        assert disk_env.app_state.is_modified is False
        titles = [call.args[0] for call in disk_env.ui_controller.show_info_message.call_args_list]
        assert titles == ["Save Starting", "Project Saved"]

    def test_cancelled_save_dialog_writes_nothing(self, disk_env, tmp_path):
        _install_project(disk_env)
        disk_env.ui_controller.show_save_project_dialog.return_value = None

        assert SaveProjectCommand(disk_env.app_context).execute() is CommandResult.FAILURE

        assert list(tmp_path.iterdir()) == []
        assert disk_env.app_state.is_modified is True
        assert disk_env.app_state.is_saving is False
        assert disk_env.app_state.project_file_path is None

    def test_cancelled_save_as_dialog_keeps_the_current_file(self, disk_env, tmp_path):
        path = tmp_path / "lab.pplot"
        _install_project(disk_env, path)
        disk_env.ui_controller.show_save_project_dialog.return_value = ""

        assert SaveProjectAsCommand(disk_env.app_context).execute() is CommandResult.FAILURE

        assert not path.exists()
        assert disk_env.app_state.project_file_path == str(path)
        assert disk_env.app_state.is_modified is True

    def test_save_as_writes_the_new_file_and_switches_to_it(self, disk_env, tmp_path):
        original = tmp_path / "lab.pplot"
        project = _install_project(disk_env, original)
        target = tmp_path / "sub" / "copy.pplot"
        disk_env.ui_controller.show_save_project_dialog.return_value = str(target)

        assert SaveProjectAsCommand(disk_env.app_context).execute() is CommandResult.SUCCESS

        assert target.exists()
        assert not original.exists()
        assert disk_env.app_state.current_project is project
        assert disk_env.app_state.project_file_path == str(target)
        assert disk_env.app_state.is_modified is False
        disk_env.session.update_project.assert_called_once_with(str(target))

    def test_failed_save_as_keeps_the_original_file_path(self, disk_env, tmp_path):
        """A Save As that cannot write must leave the project pointing at its original
        file, so the next Save does not target the location that just failed."""
        original = tmp_path / "lab.pplot"
        _install_project(disk_env, original)
        blocker = tmp_path / "blocker"
        blocker.write_text("a file, not a folder", encoding="utf-8")
        disk_env.ui_controller.show_save_project_dialog.return_value = str(blocker / "copy.pplot")

        assert SaveProjectAsCommand(disk_env.app_context).execute() is CommandResult.SUCCESS

        assert disk_env.ui_controller.show_error_message.call_args.args[:2] == ("Save Failed", "Couldn't save the project.")
        assert disk_env.app_state.project_file_path == str(original)
        assert disk_env.app_state.is_modified is True
        assert disk_env.app_state.is_saving is False
        disk_env.session.update_project.assert_not_called()

    def test_disk_error_keeps_the_project_modified(self, disk_env, tmp_path, monkeypatch):
        path = tmp_path / "lab.pplot"
        _install_project(disk_env, path)
        monkeypatch.setattr(disk_env.project_manager, "save_project", Mock(side_effect=OSError(28, "No space left on device")))

        assert SaveProjectCommand(disk_env.app_context).execute() is CommandResult.SUCCESS

        assert disk_env.app_state.is_modified is True
        assert disk_env.app_state.is_saving is False
        assert disk_env.ui_controller.show_error_message.call_args.kwargs["error"].reason
        disk_env.session.update_project.assert_not_called()


class TestSaveFailurePaths:
    """Error handlers return explicit results and never leave the global save guard stuck."""

    def _context(self):
        app_context, app_state = _make_app_context(has_project=True, current_project=Mock(), project_file_path="/p/lab.pplot")
        app_state.current_project.name = "Lab"
        app_state.is_saving = False
        app_state.modification_revision = 0
        return app_context, app_state

    def test_dispatch_error_ends_the_save_guard(self):
        app_context, app_state = self._context()
        error = RuntimeError("thread pool gone")
        app_context.get_task_scheduler.return_value.run_task.side_effect = error
        command = SaveProjectCommand(app_context)

        assert command.execute() is CommandResult.FAILURE

        assert command.is_saving is False
        app_state.begin_save.assert_called_once()
        app_state.end_save.assert_called_once()
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once_with(
            "Save Project Error", "Couldn't save the project.", error=error
        )

    def test_save_as_dialog_error_returns_failure(self):
        app_context, _app_state = self._context()
        error = RuntimeError("dialog failed")
        app_context.get_ui_controller.return_value.show_save_project_dialog.side_effect = error

        assert SaveProjectAsCommand(app_context).execute() is CommandResult.FAILURE

        app_context.get_task_scheduler.return_value.run_task.assert_not_called()
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once_with(
            "Save Project As Error", "Couldn't save the project.", error=error
        )

    def test_save_task_reports_progress_in_order(self):
        app_context, _app_state = self._context()
        project = Mock(project_file_path="/p/lab.pplot")
        progress: list[float] = []

        result = SaveProjectCommand(app_context)._save_project_task(progress.append, project=project, save_path="/p/lab.pplot")

        assert result["success"] is True
        assert progress == [0.1, 0.3, 0.4, 0.9, 1.0]

    def test_success_without_a_path_does_not_mark_saved(self):
        app_context, app_state = self._context()
        command = SaveProjectCommand(app_context)
        command._dispatch_project = app_state.current_project

        command._on_save_result({"success": True, "project": app_state.current_project, "path": None})

        app_state.mark_saved.assert_not_called()
        app_state.event_bus.emit.assert_not_called()

    def test_an_exception_while_applying_the_result_is_reported(self):
        app_context, app_state = self._context()
        error = RuntimeError("subscriber exploded")
        app_state.mark_saved.side_effect = error
        command = SaveProjectCommand(app_context)
        command._dispatch_project = app_state.current_project
        command.previous_file_path = "/p/lab.pplot"

        command._on_save_result({"success": True, "project": app_state.current_project, "path": "/p/lab.pplot"})

        app_context.get_ui_controller.return_value.show_error_message.assert_called_once_with(
            "Save Error", "Couldn't save the project.", error=error
        )

    def test_error_handler_shows_the_exception_and_survives_a_failing_dialog(self, caplog):
        app_context, _app_state = self._context()
        ui_controller = app_context.get_ui_controller.return_value
        command = SaveProjectCommand(app_context)
        command.is_saving = True
        error = OSError("disk")

        command._on_save_error((OSError, error, "traceback"))
        ui_controller.show_error_message.assert_called_once_with("Save Project Error", "Couldn't save the project.", error=error)

        ui_controller.show_error_message.side_effect = RuntimeError("dialog failed")
        with caplog.at_level(logging.ERROR):
            command._on_save_error((OSError, error, "traceback"))
        assert command.is_saving is False
        assert "Error handling save error" in caplog.text

    def test_finished_handler_survives_end_save_raising(self, caplog):
        app_context, app_state = self._context()
        app_state.end_save.side_effect = RuntimeError("state gone")
        command = SaveProjectCommand(app_context)
        command.is_saving = True

        with caplog.at_level(logging.ERROR):
            command._on_save_finished()

        assert command.is_saving is False
        assert "Error in save finished handler" in caplog.text

    def test_progress_handler_logs_and_survives_bad_values(self, caplog):
        app_context, _app_state = self._context()
        command = SaveProjectCommand(app_context)

        with caplog.at_level(logging.DEBUG, logger="SaveProjectCommand"):
            command._on_save_progress(0.4)
            command._on_save_progress("bad")

        assert "Save progress: 40%" in caplog.text
        assert "Error handling save progress" in caplog.text

    def test_cleanup_is_a_noop(self):
        app_context, _app_state = self._context()
        command = SaveProjectCommand(app_context)
        state_before = dict(vars(command))

        assert command.cleanup() is None

        assert vars(command) == state_before
