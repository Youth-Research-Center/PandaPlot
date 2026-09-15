"""Tests for NewProjectCommand (#209): dedicated naming dialog and
dirty-aware replace confirmation. Also covers cleanup() (see Command.cleanup)."""
from unittest.mock import Mock

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.project.new_project_command import NewProjectCommand
from pandaplot.models.events import EventBus
from pandaplot.models.state.app_state import AppState


def _make_app_context(*, has_project=False, is_modified=False):
    app_context = Mock()
    app_context.get_app_state.return_value.has_project = has_project
    app_context.get_app_state.return_value.is_modified = is_modified
    return app_context


def test_no_current_project_creates_without_confirmation():
    app_context = _make_app_context(has_project=False)
    app_context.get_ui_controller.return_value.show_new_project_dialog.return_value = "My Project"

    command = NewProjectCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS

    app_context.get_ui_controller.return_value.show_question.assert_not_called()
    loaded = app_context.get_app_state.return_value.load_project.call_args.args[0]
    assert loaded.name == "My Project"


def test_unmodified_current_project_creates_without_confirmation():
    """Regression (#209): the old blanket confirmation fired even when the
    current project had nothing unsaved to lose."""
    app_context = _make_app_context(has_project=True, is_modified=False)
    app_context.get_ui_controller.return_value.show_new_project_dialog.return_value = "My Project"

    command = NewProjectCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS

    app_context.get_ui_controller.return_value.show_question.assert_not_called()


def test_modified_current_project_asks_for_confirmation():
    app_context = _make_app_context(has_project=True, is_modified=True)
    app_context.get_ui_controller.return_value.show_question.return_value = True
    app_context.get_ui_controller.return_value.show_new_project_dialog.return_value = "My Project"

    command = NewProjectCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS

    app_context.get_ui_controller.return_value.show_question.assert_called_once()
    app_context.get_app_state.return_value.load_project.assert_called_once()


def test_declining_confirmation_aborts_without_creating():
    app_context = _make_app_context(has_project=True, is_modified=True)
    app_context.get_ui_controller.return_value.show_question.return_value = False

    command = NewProjectCommand(app_context)
    assert command.execute() is CommandResult.FAILURE

    app_context.get_app_state.return_value.load_project.assert_not_called()


def test_cancelling_the_naming_dialog_aborts_without_creating():
    app_context = _make_app_context(has_project=False)
    app_context.get_ui_controller.return_value.show_new_project_dialog.return_value = None

    command = NewProjectCommand(app_context)
    assert command.execute() is CommandResult.NOOP

    app_context.get_app_state.return_value.load_project.assert_not_called()


def test_new_project_uses_the_entered_name():
    app_context = _make_app_context(has_project=False)
    app_context.get_ui_controller.return_value.show_new_project_dialog.return_value = "Custom Name"

    command = NewProjectCommand(app_context)
    command.execute()

    loaded = app_context.get_app_state.return_value.load_project.call_args.args[0]
    assert loaded.name == "Custom Name"


def test_marks_project_modified_is_false():
    """NewProjectCommand sets AppState's dirty flag itself (via
    load_project) and must not be double-counted by CommandExecutor's
    generic on_project_modified hook."""
    command = NewProjectCommand(_make_app_context())
    assert command.marks_project_modified() is False


def test_undo_restores_the_previous_projects_dirty_state():
    """Regression (PR #235 review): load_project() (called by undo() to
    restore the previous project) unconditionally clears is_modified, since
    it assumes a fresh disk load. Undoing NewProjectCommand instead restores
    a project that may still have had unsaved changes -- those must survive,
    not be silently reported as saved."""
    app_state = AppState(EventBus())
    previous_project = Mock()
    previous_project.name = "Previous"
    app_state.load_project(previous_project)
    app_state.mark_modified()

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value.show_new_project_dialog.return_value = "New"

    command = NewProjectCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS

    assert command.undo() is CommandResult.SUCCESS
    assert app_state.current_project is previous_project
    assert app_state.is_modified is True


def test_redo_restores_the_created_project_without_reprompting():
    """Regression (PR #235 review): redo() used to delegate to execute(),
    which re-asks the unsaved-changes confirmation and re-opens the naming
    dialog -- redoing should silently replay the original creation instead."""
    app_context = _make_app_context(has_project=False)
    app_context.get_ui_controller.return_value.show_new_project_dialog.return_value = "My Project"

    command = NewProjectCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    created = command.created_project

    app_context.get_ui_controller.return_value.show_new_project_dialog.reset_mock()
    app_context.get_ui_controller.return_value.show_question.reset_mock()
    app_context.get_app_state.return_value.load_project.reset_mock()

    assert command.redo() is CommandResult.SUCCESS

    app_context.get_ui_controller.return_value.show_new_project_dialog.assert_not_called()
    app_context.get_ui_controller.return_value.show_question.assert_not_called()
    redone = app_context.get_app_state.return_value.load_project.call_args.args[0]
    assert redone is created


def test_undo_flushes_pending_note_edits_before_restoring_the_previous_project(monkeypatch):
    """Regression (PR #352 review): a note edited in the newly-created
    project, right before the user hits Undo, can still be mid-debounce --
    no EditNoteCommand has run yet to invalidate anything, so nothing else
    protects this swap. Must flush first, same as execute()."""
    app_state = AppState(EventBus())
    previous_project = Mock()
    previous_project.name = "Previous"
    app_state.load_project(previous_project)

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value.show_new_project_dialog.return_value = "New"

    command = NewProjectCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS

    calls = []
    monkeypatch.setattr(
        "pandaplot.commands.project.project.new_project_command.flush_pending_edits",
        lambda ctx: calls.append(ctx) or True,
    )

    assert command.undo() is CommandResult.SUCCESS
    assert calls == [app_context]
    assert app_state.current_project is previous_project


def test_redo_restores_the_created_projects_dirty_state():
    """Regression (PR #352 review): a note edited in the newly-created
    project (flushed during undo(), or dirtied by any other command) must
    not have that dirty state silently discarded when redo() reinstalls
    this exact project via load_project(), which unconditionally reports
    whatever it loads as clean."""
    app_state = AppState(EventBus())
    previous_project = Mock()
    previous_project.name = "Previous"
    app_state.load_project(previous_project)

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value.show_new_project_dialog.return_value = "New"

    command = NewProjectCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    created_project = command.created_project

    # Simulate a note edit (or any command) dirtying the newly-created
    # project after it was created.
    app_state.mark_modified()

    assert command.undo() is CommandResult.SUCCESS
    assert app_state.current_project is previous_project

    assert command.redo() is CommandResult.SUCCESS
    assert app_state.current_project is created_project
    assert app_state.is_modified is True


def test_undo_restores_a_dirty_state_that_arose_after_a_prior_redo():
    """The previous_was_modified snapshot must be refreshed on every redo(),
    not just captured once at the original execute() -- otherwise an edit
    made to the previous project during the window between an undo() and a
    later redo() gets silently forgotten the next time undo() runs again."""
    app_state = AppState(EventBus())
    previous_project = Mock()
    previous_project.name = "Previous"
    app_state.load_project(previous_project)

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value.show_new_project_dialog.return_value = "New"

    command = NewProjectCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    assert command.undo() is CommandResult.SUCCESS
    assert app_state.current_project is previous_project

    # Dirty the previous project while it's active, in the window between
    # this undo() and the redo() below.
    app_state.mark_modified()

    assert command.redo() is CommandResult.SUCCESS
    assert command.undo() is CommandResult.SUCCESS
    assert app_state.current_project is previous_project
    assert app_state.is_modified is True


def test_undo_aborts_and_reports_an_error_when_flush_fails(monkeypatch):
    """Regression (PR #352 review): must return ABORTED, not FAILURE --
    CommandExecutor.undo() moves the command to the redo stack regardless
    of result, so FAILURE here would record this creation as undone (and
    installable via a later Redo) even though nothing actually changed."""
    app_context = _make_app_context()
    command = NewProjectCommand(app_context)
    command.previous_project = Mock()
    monkeypatch.setattr(
        "pandaplot.commands.project.project.new_project_command.flush_pending_edits",
        lambda ctx: False,
    )

    assert command.undo() is CommandResult.ABORTED
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
    app_context.get_app_state.return_value.load_project.assert_not_called()


def test_redo_flushes_pending_note_edits_before_restoring_the_created_project(monkeypatch):
    """Regression (PR #352 review): same race as undo(), but on redo() --
    a note edited in the project that's about to be replaced (by redoing
    the creation) must be flushed first."""
    app_context = _make_app_context(has_project=False)
    app_context.get_ui_controller.return_value.show_new_project_dialog.return_value = "My Project"
    command = NewProjectCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS
    created = command.created_project

    calls = []
    monkeypatch.setattr(
        "pandaplot.commands.project.project.new_project_command.flush_pending_edits",
        lambda ctx: calls.append(ctx) or True,
    )

    assert command.redo() is CommandResult.SUCCESS
    assert calls == [app_context]
    redone = app_context.get_app_state.return_value.load_project.call_args.args[0]
    assert redone is created


def test_redo_aborts_and_reports_an_error_when_flush_fails(monkeypatch):
    """Regression (PR #352 review): must return ABORTED, not FAILURE -- see
    the matching undo() test above."""
    app_context = _make_app_context()
    command = NewProjectCommand(app_context)
    command.created_project = Mock()
    monkeypatch.setattr(
        "pandaplot.commands.project.project.new_project_command.flush_pending_edits",
        lambda ctx: False,
    )

    assert command.redo() is CommandResult.ABORTED
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
    app_context.get_app_state.return_value.load_project.assert_not_called()


def test_execute_flushes_pending_note_edits_before_checking_modified(monkeypatch):
    """Regression (#318): a note's debounced edit must be flushed (and so
    reflected in is_modified) before this command decides whether creating
    a new project would discard anything."""
    calls = []
    monkeypatch.setattr(
        "pandaplot.commands.project.project.new_project_command.flush_pending_edits",
        lambda ctx: calls.append(ctx) or True,
    )
    app_context = _make_app_context(has_project=True, is_modified=False)
    app_context.get_ui_controller.return_value.show_new_project_dialog.return_value = "My Project"

    command = NewProjectCommand(app_context)
    assert command.execute() is CommandResult.SUCCESS

    assert calls == [app_context]
    app_context.get_ui_controller.return_value.show_question.assert_not_called()


def test_execute_fails_and_reports_an_error_when_flush_fails(monkeypatch):
    """Regression (PR #352 review): a flush failure means a note edit is
    still stuck unsaved -- must refuse to create the new project (which
    would discard the current one) instead of silently proceeding."""
    monkeypatch.setattr(
        "pandaplot.commands.project.project.new_project_command.flush_pending_edits",
        lambda ctx: False,
    )
    app_context = _make_app_context(has_project=True, is_modified=False)

    command = NewProjectCommand(app_context)
    assert command.execute() is CommandResult.FAILURE

    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
    app_context.get_ui_controller.return_value.show_new_project_dialog.assert_not_called()


def test_redo_without_a_prior_execute_fails():
    """If execute() never completed (so nothing was ever pushed onto the
    undo stack in the first place), redo() must not crash trying to
    restore a project that was never created."""
    app_context = _make_app_context(has_project=False)
    command = NewProjectCommand(app_context)

    assert command.redo() is CommandResult.FAILURE
    app_context.get_app_state.return_value.load_project.assert_not_called()


@pytest.fixture
def env():
    app_state = Mock()
    app_state.has_project = True
    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = Mock()
    return app_context


def test_cleanup_releases_the_previous_project_reference(env):
    command = NewProjectCommand(env)
    command.previous_project = Mock()
    command.created_project = Mock()

    command.cleanup()

    assert command.previous_project is None
    assert command.created_project is None
