"""Tests for SaveProjectCommand / SaveProjectAsCommand logging behavior."""

import logging
from unittest.mock import Mock

from pandaplot.commands.project.project.save_project_command import (
    SaveProjectAsCommand,
    SaveProjectCommand,
)


def _make_app_context(*, has_project=True, current_project=None, project_file_path=None):
    app_state = Mock()
    app_state.has_project = has_project
    app_state.current_project = current_project
    app_state.project_file_path = project_file_path

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = Mock()
    return app_context, app_state


def test_execute_logs_a_warning_when_save_already_in_progress(caplog):
    app_context, app_state = _make_app_context()
    command = SaveProjectCommand(app_context)
    command.is_saving = True

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "SaveProjectCommand.execute" in caplog.text


def test_execute_logs_a_warning_when_no_project_loaded(caplog):
    app_context, app_state = _make_app_context(has_project=False)
    command = SaveProjectCommand(app_context)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "SaveProjectCommand.execute" in caplog.text


def test_execute_logs_a_warning_when_current_project_none(caplog):
    app_context, app_state = _make_app_context(has_project=True, current_project=None)
    command = SaveProjectCommand(app_context)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "SaveProjectCommand.execute" in caplog.text


def test_save_as_execute_logs_a_warning_when_no_project_loaded(caplog):
    app_context, app_state = _make_app_context(has_project=False)
    command = SaveProjectAsCommand(app_context)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "SaveProjectAsCommand.execute" in caplog.text


def test_save_as_execute_logs_a_warning_when_current_project_none(caplog):
    app_context, app_state = _make_app_context(has_project=True, current_project=None)
    command = SaveProjectAsCommand(app_context)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "SaveProjectAsCommand.execute" in caplog.text


def test_cleanup_releases_previous_file_path_snapshot():
    app_context, _app_state = _make_app_context()
    command = SaveProjectCommand(app_context)
    command.previous_file_path = "/old/path/project.pplot"
    command.is_saving = False

    command.cleanup()

    assert command.previous_file_path is None


def test_cleanup_does_not_release_previous_file_path_while_save_in_progress():
    app_context, _app_state = _make_app_context()
    command = SaveProjectCommand(app_context)
    command.previous_file_path = "/old/path/project.pplot"
    command.is_saving = True

    command.cleanup()

    assert command.previous_file_path == "/old/path/project.pplot"
