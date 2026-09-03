"""Tests for OpenProjectCommand logging behavior."""

import logging
from unittest.mock import Mock, patch

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.project.open_project_command import OpenProjectCommand


def test_invalid_project_file_logs_a_warning(caplog):
    app_context = Mock()
    app_context.ui_controller.show_open_project_dialog.return_value = "bad_path.pplot"

    command = OpenProjectCommand(app_context)
    with patch.object(command.project_manager, "validate_project_file", return_value=False):
        with caplog.at_level(logging.WARNING):
            result = command.execute()

    assert command.was_executed is False
    assert "bad_path.pplot" in caplog.text
    assert result is CommandResult.FAILURE


def test_execute_returns_noop_when_user_cancels_the_open_dialog():
    app_context = Mock()
    app_context.ui_controller.show_open_project_dialog.return_value = None

    command = OpenProjectCommand(app_context)
    result = command.execute()

    assert command.was_executed is False
    assert result is CommandResult.NOOP


def test_execute_returns_noop_when_user_cancels_replacing_current_project():
    app_context = Mock()
    app_context.ui_controller.show_open_project_dialog.return_value = "path.pplot"
    app_context.app_state.has_project = True
    app_context.ui_controller.show_question.return_value = False

    command = OpenProjectCommand(app_context)
    with patch.object(command.project_manager, "validate_project_file", return_value=True):
        result = command.execute()

    assert command.was_executed is False
    assert result is CommandResult.NOOP


def test_execute_returns_success_when_project_opens():
    app_context = Mock()
    app_context.ui_controller.show_open_project_dialog.return_value = "path.pplot"
    app_context.app_state.has_project = False

    command = OpenProjectCommand(app_context)
    with patch.object(command.project_manager, "validate_project_file", return_value=True):
        result = command.execute()

    assert command.was_executed is True
    assert result is CommandResult.SUCCESS


def test_execute_returns_failure_when_load_command_fails():
    """The wrapped LoadProjectCommand's result must not be discarded --
    OpenProjectCommand previously ignored it and always reported SUCCESS
    once the file dialog and validation passed, even if the load itself
    failed."""
    app_context = Mock()
    app_context.ui_controller.show_open_project_dialog.return_value = "path.pplot"
    app_context.app_state.has_project = False

    command = OpenProjectCommand(app_context)
    with patch.object(command.project_manager, "validate_project_file", return_value=True):
        with patch(
            "pandaplot.commands.project.project.open_project_command.LoadProjectCommand"
        ) as mock_load_cls:
            mock_load_cls.return_value.execute.return_value = CommandResult.FAILURE
            result = command.execute()

    assert command.was_executed is False
    assert result is CommandResult.FAILURE


def test_execute_returns_failure_on_unexpected_exception():
    app_context = Mock()
    app_context.ui_controller.show_open_project_dialog.side_effect = RuntimeError("boom")

    command = OpenProjectCommand(app_context)
    result = command.execute()

    assert command.was_executed is False
    assert result is CommandResult.FAILURE


def test_undo_returns_noop_when_nothing_was_executed():
    app_context = Mock()
    command = OpenProjectCommand(app_context)

    assert command.undo() is CommandResult.NOOP


def test_undo_delegates_to_the_wrapped_load_command():
    app_context = Mock()
    command = OpenProjectCommand(app_context)
    command.was_executed = True
    load_command = Mock()
    load_command.undo.return_value = CommandResult.SUCCESS
    command.load_command = load_command

    assert command.undo() is CommandResult.SUCCESS
    load_command.undo.assert_called_once_with()


def test_redo_delegates_to_the_wrapped_load_command():
    app_context = Mock()
    command = OpenProjectCommand(app_context)
    command.was_executed = True
    load_command = Mock()
    load_command.redo.return_value = CommandResult.SUCCESS
    command.load_command = load_command

    assert command.redo() is CommandResult.SUCCESS
    load_command.redo.assert_called_once_with()


def test_redo_re_executes_when_nothing_was_executed():
    app_context = Mock()
    app_context.ui_controller.show_open_project_dialog.return_value = None
    command = OpenProjectCommand(app_context)

    assert command.redo() is CommandResult.NOOP


def test_cleanup_forwards_to_the_wrapped_load_command():
    app_context = Mock()
    command = OpenProjectCommand(app_context)
    load_command = Mock()
    command.load_command = load_command

    command.cleanup()

    load_command.cleanup.assert_called_once_with()
    assert command.load_command is None


def test_cleanup_isolates_a_raising_load_command():
    """If the wrapped LoadProjectCommand's cleanup() raises, load_command must
    still be released to None, and the exception must not propagate out of
    OpenProjectCommand.cleanup()."""
    app_context = Mock()
    command = OpenProjectCommand(app_context)
    load_command = Mock()
    load_command.cleanup.side_effect = RuntimeError("boom")
    command.load_command = load_command

    command.cleanup()  # must not raise

    assert command.load_command is None
