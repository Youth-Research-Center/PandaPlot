"""Tests for LoadProjectCommand's cleanup() (see Command.cleanup) and for
surfacing items that ProjectDataManager.load() silently dropped (issue #288)."""
from unittest.mock import Mock

import pytest

from pandaplot.commands.project.project.load_project_command import LoadProjectCommand
from pandaplot.models.project.project import Project


@pytest.fixture
def env():
    app_state = Mock()
    app_state.has_project = True
    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = Mock()
    app_context.get_task_scheduler.return_value = Mock()
    app_context.get_manager.return_value = Mock()
    return app_context


def test_cleanup_releases_the_previous_and_loaded_project_references(env):
    command = LoadProjectCommand(env, "/some/path.pplot")
    command.previous_project = Mock()
    command.loaded_project = Mock()

    command.cleanup()

    assert command.previous_project is None
    assert command.loaded_project is None


def test_on_load_result_warns_when_items_failed_to_load(env):
    command = LoadProjectCommand(env, "/some/path.pplot")
    project = Project(name="My Project")
    project.failed_item_ids = ["ds-1", "chart-2"]

    command._on_load_result({
        "success": True, "error": None, "project": project, "file_path": "/some/path.pplot",
    })

    ui_controller = env.get_ui_controller.return_value
    warning_call = ui_controller.show_warning_message.call_args
    assert warning_call is not None
    title, message = warning_call.args
    assert "ds-1" in message
    assert "chart-2" in message


def test_on_load_result_does_not_warn_when_no_items_failed(env):
    command = LoadProjectCommand(env, "/some/path.pplot")
    project = Project(name="My Project")

    command._on_load_result({
        "success": True, "error": None, "project": project, "file_path": "/some/path.pplot",
    })

    ui_controller = env.get_ui_controller.return_value
    ui_controller.show_warning_message.assert_not_called()
