"""Tests for RenameProjectCommand (renames the Project itself, not a tree item)."""

import logging
from unittest.mock import Mock, patch

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.project.rename_project_command import RenameProjectCommand
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project import Project


@pytest.fixture
def env():
    project = Project("Original Name")

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project
    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = Mock()
    app_context.event_bus = Mock()
    return app_context, project


def test_rename_updates_project_name(env):
    app_context, project = env
    command = RenameProjectCommand(app_context, "New Name")

    assert command.execute() is CommandResult.SUCCESS
    assert project.name == "New Name"


def test_undo_and_redo_round_trip(env):
    app_context, project = env
    command = RenameProjectCommand(app_context, "New Name")
    command.execute()

    command.undo()
    assert project.name == "Original Name"

    command.redo()
    assert project.name == "New Name"


def test_empty_name_rejected(env):
    app_context, project = env
    command = RenameProjectCommand(app_context, "   ")
    assert command.execute() is CommandResult.FAILURE
    assert project.name == "Original Name"
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_empty_name_rejected_logs_a_warning(env, caplog):
    app_context, _project = env
    command = RenameProjectCommand(app_context, "   ")
    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "Original Name" in caplog.text


def test_unchanged_name_is_silent_noop(env):
    app_context, project = env
    command = RenameProjectCommand(app_context, "Original Name")
    assert command.execute() is CommandResult.NOOP
    assert project.name == "Original Name"
    app_context.get_ui_controller.return_value.show_error_message.assert_not_called()


def test_no_project_loaded(env):
    app_context, project = env
    app_context.get_app_state.return_value.has_project = False

    command = RenameProjectCommand(app_context, "New Name")
    assert command.execute() is CommandResult.FAILURE
    assert project.name == "Original Name"


def test_no_project_loaded_logs_a_warning(env, caplog):
    app_context, _project = env
    app_context.get_app_state.return_value.has_project = False

    command = RenameProjectCommand(app_context, "New Name")
    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "New Name" in caplog.text


def test_cleanup_does_not_raise(env):
    app_context, _project = env
    command = RenameProjectCommand(app_context, "New Name")
    command.execute()
    command.cleanup()


def test_event_emitted_on_rename(env):
    app_context, project = env
    command = RenameProjectCommand(app_context, "New Name")
    command.execute()

    calls = [c for c in app_context.event_bus.emit.call_args_list
             if c.args[0] == ProjectEvents.PROJECT_CHANGED]
    assert len(calls) == 1
    assert calls[0].args[1]["project"] is project


def test_execute_failure_passes_the_exception_to_the_dialog():
    app_context = Mock()
    app_context.get_ui_controller.return_value = Mock()
    error = RuntimeError("boom")
    with patch("pandaplot.commands.project.project.rename_project_command.get_current_project", side_effect=error):
        command = RenameProjectCommand(app_context, "New")
        assert command.execute() is CommandResult.FAILURE
    show = app_context.get_ui_controller.return_value.show_error_message
    show.assert_called_once_with("Rename Project Error", "Couldn't rename the project.", error=error)


def test_undo_and_redo_abort_when_another_project_is_open():
    from pandaplot.models.events.event_bus import EventBus
    from pandaplot.models.state.app_state import AppState

    project_a = Project("A")
    app_state = AppState(EventBus())
    app_state.load_project(project_a)
    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = Mock()
    app_context.event_bus = Mock()
    command = RenameProjectCommand(app_context, "A renamed")
    assert command.execute() is CommandResult.SUCCESS

    project_b = Project("B")
    app_state.load_project(project_b)

    assert command.undo() is CommandResult.ABORTED
    assert command.redo() is CommandResult.ABORTED
    assert project_b.name == "B"
    assert project_a.name == "A renamed"

    app_state.load_project(project_a)
    assert command.undo() is CommandResult.SUCCESS
    assert project_a.name == "A"
