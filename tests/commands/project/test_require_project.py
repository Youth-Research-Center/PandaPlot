"""Tests for ensure_project_or_offer_create."""
from unittest.mock import Mock

from pandaplot.commands.project.project.new_project_command import NewProjectCommand
from pandaplot.commands.project.require_project import ensure_project_or_offer_create


def _app_context(*, has_project: bool):
    app_state = Mock()
    app_state.has_project = has_project
    app_state.current_project = Mock() if has_project else None

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    return app_context, app_state


def test_returns_true_immediately_when_a_project_is_already_open():
    app_context, _ = _app_context(has_project=True)

    result = ensure_project_or_offer_create(app_context, "Title", "Message")

    assert result is True
    app_context.get_ui_controller.assert_not_called()


def test_returns_false_when_the_user_cancels():
    app_context, _ = _app_context(has_project=False)
    app_context.get_ui_controller.return_value.show_action_or_cancel.return_value = False

    result = ensure_project_or_offer_create(app_context, "Title", "Message")

    assert result is False
    app_context.get_command_executor.return_value.execute_command.assert_not_called()


def test_creates_a_project_and_returns_true_when_the_user_accepts():
    app_context, app_state = _app_context(has_project=False)
    app_context.get_ui_controller.return_value.show_action_or_cancel.return_value = True

    def _execute_command(command):
        # Simulate NewProjectCommand.execute() loading a project.
        app_state.has_project = True
        app_state.current_project = Mock()

    app_context.get_command_executor.return_value.execute_command.side_effect = _execute_command

    result = ensure_project_or_offer_create(app_context, "Title", "Message")

    assert result is True
    app_context.get_command_executor.return_value.execute_command.assert_called_once()
    created_command = app_context.get_command_executor.return_value.execute_command.call_args.args[0]
    assert isinstance(created_command, NewProjectCommand)


def test_returns_false_if_project_creation_did_not_actually_load_a_project():
    """Defensive: don't claim success if the command somehow didn't result
    in a loaded project (e.g. NewProjectCommand's own internal confirm was
    declined -- not reachable in practice from this call site, since it only
    triggers when no project is open, but this pins the contract)."""
    app_context, _ = _app_context(has_project=False)
    app_context.get_ui_controller.return_value.show_action_or_cancel.return_value = True
    # execute_command is left as a no-op Mock: app_state never gets a project.

    result = ensure_project_or_offer_create(app_context, "Title", "Message")

    assert result is False
