"""Tests for ChartFinder."""
import logging
from unittest.mock import Mock

from pandaplot.commands.project.chart.chart_finder import ChartFinder
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.note import Note


def _make_app_context(found_item):
    project = Mock()
    project.find_item.return_value = found_item

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    return app_context


def test_find_returns_the_chart_when_it_exists():
    chart = Chart(name="Test Chart", chart_type="line")
    app_context = _make_app_context(chart)

    assert ChartFinder(app_context).find(chart.id) is chart


def test_find_returns_none_when_no_project_is_open():
    app_state = Mock()
    app_state.has_project = False
    app_context = Mock()
    app_context.get_app_state.return_value = app_state

    assert ChartFinder(app_context).find("missing") is None


def test_find_returns_none_when_item_not_found():
    app_context = _make_app_context(None)

    assert ChartFinder(app_context).find("missing") is None


def test_find_returns_none_and_logs_a_warning_when_item_is_not_a_chart(caplog):
    wrong_item = Note(name="Not a chart")
    app_context = _make_app_context(wrong_item)

    with caplog.at_level(logging.WARNING):
        result = ChartFinder(app_context).find(wrong_item.id)

    assert result is None
    assert wrong_item.id in caplog.text
