"""Tests for LoadProjectCommand's cleanup() (see Command.cleanup)."""
from unittest.mock import Mock

import pytest

from pandaplot.commands.project.project.load_project_command import LoadProjectCommand


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
