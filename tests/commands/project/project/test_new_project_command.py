"""Tests for NewProjectCommand's cleanup() (see Command.cleanup)."""
from unittest.mock import Mock

import pytest

from pandaplot.commands.project.project.new_project_command import NewProjectCommand


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

    command.cleanup()

    assert command.previous_project is None
