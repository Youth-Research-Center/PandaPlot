"""Tests for CloseProjectCommand."""

from unittest.mock import Mock

from pandaplot.commands.project.project.close_project_command import CloseProjectCommand
from pandaplot.models.state import AppContext, AppState


def _make_app_context(has_project=True):
    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = has_project
    app_context.get_app_state.return_value = app_state
    return app_context, app_state


def test_execute_closes_the_project():
    app_context, app_state = _make_app_context()
    command = CloseProjectCommand(app_context)
    assert command.execute() is True
    app_state.close_project.assert_called_once()


def test_execute_surfaces_unexpected_failure_to_the_user():
    app_context, app_state = _make_app_context()
    app_state.close_project.side_effect = RuntimeError("disk error")

    command = CloseProjectCommand(app_context)
    assert command.execute() is False
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
    _title, message = app_context.get_ui_controller.return_value.show_error_message.call_args.args
    assert "disk error" in message
