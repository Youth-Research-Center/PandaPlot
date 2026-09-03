"""Tests for CreateChartCommand -- the undoable command that actually adds a
built Chart to the project. Split out of CreateChartFromWizardCommand so the
wizard-opening command (fire-and-forget, never on the undo stack) and the
real, undoable effect are separate commands (#185)."""
from unittest.mock import Mock

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.chart import CreateChartCommand
from pandaplot.models.project.items import Chart


@pytest.fixture
def app_context_with_project():
    project = Mock()
    inserted_items = {}

    def _add_item(item, parent_id=None):
        item.parent_id = parent_id
        inserted_items[item.id] = item

    def _remove_item_by_id(item_id):
        item = inserted_items.pop(item_id, None)
        if item is not None:
            item.parent_id = None

    project.add_item.side_effect = _add_item
    project.remove_item_by_id.side_effect = _remove_item_by_id

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()
    return app_context, project


def _chart():
    return Chart(name="Test Chart", chart_type="line")


def test_execute_adds_the_chart_to_the_project(app_context_with_project):
    app_context, project = app_context_with_project
    chart = _chart()

    command = CreateChartCommand(app_context, chart, parent_id="folder-1")
    result = command.execute()

    assert result is CommandResult.SUCCESS
    project.add_item.assert_called_once_with(chart, parent_id="folder-1")


def test_execute_emits_chart_created_event(app_context_with_project):
    app_context, _ = app_context_with_project
    chart = _chart()

    command = CreateChartCommand(app_context, chart)
    command.execute()

    app_context.event_bus.emit.assert_called_once()
    event_name, event_data = app_context.event_bus.emit.call_args[0]
    assert event_data["chart_id"] == chart.id


def test_undo_removes_the_chart(app_context_with_project):
    app_context, project = app_context_with_project
    chart = _chart()
    command = CreateChartCommand(app_context, chart)
    command.execute()

    command.undo()

    project.remove_item_by_id.assert_called_once_with(chart.id)


def test_redo_readds_the_same_chart_instance(app_context_with_project):
    app_context, project = app_context_with_project
    chart = _chart()
    command = CreateChartCommand(app_context, chart, parent_id="folder-1")
    command.execute()

    command.undo()
    command.redo()

    assert project.add_item.call_count == 2
    assert project.add_item.call_args == ((chart,), {"parent_id": "folder-1"})


def test_undo_without_project_does_not_raise(app_context_with_project):
    app_context, _ = app_context_with_project
    chart = _chart()
    command = CreateChartCommand(app_context, chart)
    command.execute()
    app_context.get_app_state.return_value.has_project = False

    command.undo()  # must not raise


def test_execute_returns_false_when_add_item_raises(app_context_with_project):
    app_context, project = app_context_with_project
    chart = _chart()
    project.add_item.side_effect = ValueError("Duplicate item ID")

    command = CreateChartCommand(app_context, chart)
    result = command.execute()

    assert result is CommandResult.FAILURE


def test_cleanup_does_not_raise_and_keeps_chart_for_redo(app_context_with_project):
    """cleanup() must not null out self.chart -- redo() calls execute(),
    which re-adds self.chart, so it needs to stay alive for the lifetime of
    the command even after cleanup() (see Command.cleanup)."""
    app_context, project = app_context_with_project
    chart = _chart()
    command = CreateChartCommand(app_context, chart)
    command.execute()

    command.cleanup()  # must not raise

    assert command.chart is chart
