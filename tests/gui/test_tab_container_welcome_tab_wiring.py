"""Tests for TabContainer.create_welcome_tab's signal wiring to TabContainerCommandManager.

create_welcome_tab connects each of WelcomeTab's seven signals directly to a
method on self.command_manager (see issue #251's TabContainer/
TabContainerCommandManager split). That wiring is a plain string of attribute
names with no other test coverage, so a typo (e.g.
`handle_recent_projects` instead of `handle_recent_project`) would only
surface as an AttributeError when a user actually clicked the welcome tab.

These tests build a minimal-but-real TabContainer (via __new__, like
test_tab_container_create_chart.py) with a real QTabWidget as the pane and a
Mock(spec=TabContainerCommandManager) as the command manager, call the real
create_welcome_tab, and then emit each of the real WelcomeTab's signals -
asserting the corresponding command_manager method fires. Using `spec=`
(rather than a bare Mock()) means a wrong attribute name on the connect()
calls raises AttributeError immediately instead of silently succeeding.
"""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QTabWidget

from pandaplot.gui.components.tabs.tab_container import TabContainer
from pandaplot.gui.components.tabs.tab_container_command_manager import TabContainerCommandManager


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_container_with_welcome_tab():
    """Build a bare TabContainer, call the real create_welcome_tab, and return
    (container, welcome_tab)."""
    container = TabContainer.__new__(TabContainer)
    container.app_context = Mock()
    container.command_manager = Mock(spec=TabContainerCommandManager)
    container._active_pane = QTabWidget()
    container.panes = [container._active_pane]

    welcome_tab = container.create_welcome_tab()
    assert welcome_tab is not None
    return container, welcome_tab


def test_new_project_requested_wired_to_handle_new_project():
    container, welcome_tab = _make_container_with_welcome_tab()

    welcome_tab.new_project_requested.emit()

    container.command_manager.handle_new_project.assert_called_once_with()


def test_open_project_requested_wired_to_handle_open_project():
    container, welcome_tab = _make_container_with_welcome_tab()

    welcome_tab.open_project_requested.emit()

    container.command_manager.handle_open_project.assert_called_once_with()


def test_recent_project_selected_wired_to_handle_recent_project():
    container, welcome_tab = _make_container_with_welcome_tab()

    welcome_tab.recent_project_selected.emit("/path/to/project.ppp")

    container.command_manager.handle_recent_project.assert_called_once_with(
        "/path/to/project.ppp"
    )


def test_import_data_requested_wired_to_handle_import_data():
    container, welcome_tab = _make_container_with_welcome_tab()

    welcome_tab.import_data_requested.emit()

    container.command_manager.handle_import_data.assert_called_once_with()


def test_example_project_selected_wired_to_handle_example_project():
    container, welcome_tab = _make_container_with_welcome_tab()

    welcome_tab.example_project_selected.emit("/path/to/example.ppp")

    container.command_manager.handle_example_project.assert_called_once_with(
        "/path/to/example.ppp"
    )


def test_create_dataset_requested_wired_to_handle_create_dataset():
    container, welcome_tab = _make_container_with_welcome_tab()

    welcome_tab.create_dataset_requested.emit()

    container.command_manager.handle_create_dataset.assert_called_once_with()


def test_create_chart_requested_wired_to_handle_create_chart():
    container, welcome_tab = _make_container_with_welcome_tab()

    welcome_tab.create_chart_requested.emit()

    container.command_manager.handle_create_chart.assert_called_once_with()
