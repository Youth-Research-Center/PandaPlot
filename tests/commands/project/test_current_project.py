"""Tests for get_current_project."""
from unittest.mock import Mock

from pandaplot.commands.project.current_project import get_current_project


def test_returns_the_current_project_when_one_is_open():
    project = Mock()
    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project
    app_context = Mock()
    app_context.get_app_state.return_value = app_state

    assert get_current_project(app_context) is project


def test_returns_none_when_has_project_is_false():
    app_state = Mock()
    app_state.has_project = False
    app_context = Mock()
    app_context.get_app_state.return_value = app_state

    assert get_current_project(app_context) is None


def test_returns_none_when_current_project_is_none_despite_has_project():
    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = None
    app_context = Mock()
    app_context.get_app_state.return_value = app_state

    assert get_current_project(app_context) is None
