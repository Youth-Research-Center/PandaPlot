"""Logging-only tests for DescriptiveStatsCommand's failure paths.

DescriptiveStatsCommand does not otherwise have a dedicated test file; these
tests cover only the warning logging added for genuine failures in execute()
and undo() (see issue-184-audit-command-logging).
"""

import logging
from unittest.mock import Mock

from pandaplot.commands.project.dataset.descriptive_stats_command import DescriptiveStatsCommand
from pandaplot.models.state import AppContext, AppState


def _make_app_context(has_project=True, current_project=None):
    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = has_project
    app_state.current_project = current_project
    app_state.event_bus = Mock()
    app_context.get_app_state.return_value = app_state
    return app_context, app_state


def test_execute_logs_a_warning_when_no_project_loaded(caplog):
    app_context, _ = _make_app_context(has_project=False, current_project=None)
    command = DescriptiveStatsCommand(app_context, "ds-1", ["A"])

    with caplog.at_level(logging.WARNING):
        assert command.execute() is False
    assert "no project" in caplog.text.lower()
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_undo_logs_a_warning_when_no_project_loaded(caplog):
    app_context, _ = _make_app_context(has_project=True, current_project=None)
    command = DescriptiveStatsCommand(app_context, "ds-1", ["A"])
    command.result_dataset_id = "result-1"

    with caplog.at_level(logging.WARNING):
        assert command.undo() is False
    assert "result-1" in caplog.text


def test_execute_surfaces_compute_failure_to_the_user():
    project = Mock()
    project.find_item.return_value = None  # source dataset not found
    app_context, _ = _make_app_context(has_project=True, current_project=project)
    command = DescriptiveStatsCommand(app_context, "ds-1", ["A"])

    assert command.execute() is False
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
    _title, message = app_context.get_ui_controller.return_value.show_error_message.call_args.args
    assert "not available" in message
