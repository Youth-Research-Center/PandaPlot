"""Tests for the main menu's Chart menu."""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from pandaplot.gui.components.main_menu.main_menu import MainMenu
from pandaplot.models.events import ProjectEvents
from pandaplot.models.project.items import Dataset


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _fake_app_context(datasets):
    project = Mock()
    project.get_all_items.return_value = datasets

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()
    app_context.get_manager.return_value = Mock()
    # MainMenu queries can_undo()/can_redo() as soon as the Edit menu is
    # built, and QAction.setEnabled requires an actual bool.
    command_executor = Mock()
    command_executor.can_undo.return_value = False
    command_executor.can_redo.return_value = False
    app_context.get_command_executor.return_value = command_executor
    return app_context


def test_chart_menu_sits_between_data_and_settings():
    parent = QWidget()
    menu = MainMenu(parent=parent, app_context=_fake_app_context(datasets=[]))
    menu_titles = [action.menu().title() for action in menu.actions() if action.menu() is not None]

    assert menu_titles.index("Chart") == menu_titles.index("Data") + 1
    assert menu_titles.index("Settings") == menu_titles.index("Chart") + 1


def test_create_new_action_enabled_with_no_project():
    parent = QWidget()
    app_context = _fake_app_context(datasets=[])
    app_context.get_app_state.return_value.has_project = False
    app_context.get_app_state.return_value.current_project = None
    menu = MainMenu(parent=parent, app_context=app_context)

    assert menu.create_chart_action.isEnabled() is True


def test_create_new_action_enabled_with_a_dataset():
    dataset = Mock(spec=Dataset)
    parent = QWidget()
    menu = MainMenu(parent=parent, app_context=_fake_app_context(datasets=[dataset]))

    assert menu.create_chart_action.isEnabled() is True


def test_create_new_action_enabled_with_a_project_but_no_datasets():
    parent = QWidget()
    menu = MainMenu(parent=parent, app_context=_fake_app_context(datasets=[]))

    assert menu.create_chart_action.isEnabled() is True


def test_create_new_action_stays_enabled_when_the_project_is_closed():
    """Chart creation no longer needs a project open -- CreateChartFromWizardCommand
    now offers to create one on the spot. Pins that closing a project doesn't
    regress this by re-disabling the action."""
    dataset = Mock(spec=Dataset)
    app_context = _fake_app_context(datasets=[dataset])
    parent = QWidget()
    menu = MainMenu(parent=parent, app_context=app_context)
    assert menu.create_chart_action.isEnabled() is True

    subscribed = {
        event_type: handler
        for event_type, handler in (call.args for call in app_context.event_bus.subscribe.call_args_list)
    }
    assert ProjectEvents.PROJECT_CLOSED in subscribed

    app_state = app_context.get_app_state.return_value
    app_state.has_project = False
    app_state.current_project = None
    subscribed[ProjectEvents.PROJECT_CLOSED]({})

    assert menu.create_chart_action.isEnabled() is True
