"""Tests for OpenProjectCommand logging behavior."""

import logging
from unittest.mock import Mock, patch

from pandaplot.commands.project.project.open_project_command import OpenProjectCommand


def test_invalid_project_file_logs_a_warning(caplog):
    app_context = Mock()
    app_context.ui_controller.show_open_project_dialog.return_value = "bad_path.pplot"

    command = OpenProjectCommand(app_context)
    with patch.object(command.project_manager, "validate_project_file", return_value=False):
        with caplog.at_level(logging.WARNING):
            command.execute()

    assert command.was_executed is False
    assert "bad_path.pplot" in caplog.text


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
