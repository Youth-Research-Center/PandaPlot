"""Tests for SaveProjectCommand / SaveProjectAsCommand logging behavior."""

import logging
from unittest.mock import Mock

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.project.save_project_command import (
    SaveProjectAsCommand,
    SaveProjectCommand,
)
from pandaplot.models.events import EventBus
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
    app_context, app_state = _make_app_context()
    command = SaveProjectCommand(app_context)
    command.is_saving = True

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "SaveProjectCommand.execute" in caplog.text


def test_execute_logs_a_warning_when_no_project_loaded(caplog):
    app_context, app_state = _make_app_context(has_project=False)
    command = SaveProjectCommand(app_context)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "SaveProjectCommand.execute" in caplog.text


def test_execute_logs_a_warning_when_current_project_none(caplog):
    app_context, app_state = _make_app_context(has_project=True, current_project=None)
    command = SaveProjectCommand(app_context)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "SaveProjectCommand.execute" in caplog.text


def test_save_as_execute_logs_a_warning_when_no_project_loaded(caplog):
    app_context, app_state = _make_app_context(has_project=False)
    command = SaveProjectAsCommand(app_context)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "SaveProjectAsCommand.execute" in caplog.text


def test_save_as_execute_logs_a_warning_when_current_project_none(caplog):
    app_context, app_state = _make_app_context(has_project=True, current_project=None)
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
    app_context, app_state = _make_app_context(has_project=True, current_project=Mock(), project_file_path="/other.pplot")
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
