"""Tests for RenameProjectCommand (renames the Project itself, not a tree item)."""

import logging
from unittest.mock import Mock

import pytest

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

    assert command.execute() is True
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
    assert command.execute() is False
    assert project.name == "Original Name"
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_empty_name_rejected_logs_a_warning(env, caplog):
    app_context, project = env
    command = RenameProjectCommand(app_context, "   ")
    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "Original Name" in caplog.text


def test_unchanged_name_is_silent_noop(env):
    app_context, project = env
    command = RenameProjectCommand(app_context, "Original Name")
    assert command.execute() is False
    assert project.name == "Original Name"
    app_context.get_ui_controller.return_value.show_error_message.assert_not_called()


def test_no_project_loaded(env):
    app_context, project = env
    app_context.get_app_state.return_value.has_project = False

    command = RenameProjectCommand(app_context, "New Name")
    assert command.execute() is False
    assert project.name == "Original Name"


def test_no_project_loaded_logs_a_warning(env, caplog):
    app_context, project = env
    app_context.get_app_state.return_value.has_project = False

    command = RenameProjectCommand(app_context, "New Name")
    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
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
