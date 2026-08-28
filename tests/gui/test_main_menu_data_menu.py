"""Tests for the main menu's Data menu."""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from pandaplot.gui.components.main_menu.main_menu import MainMenu
from pandaplot.models.events import ProjectEvents, UIEvents
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


def _data_menu(menu):
    for action in menu.actions():
        if action.menu() is not None and action.menu().title() == "Data":
            return action.menu()
    raise AssertionError("Data menu not found")


def _subscribed(app_context):
    return {
        event_type: handler
        for event_type, handler in (call.args for call in app_context.event_bus.subscribe.call_args_list)
    }


def test_data_menu_has_an_add_rows_columns_action():
    parent = QWidget()
    menu = MainMenu(parent=parent, app_context=_fake_app_context(datasets=[Mock(spec=Dataset)]))

    titles = [action.text() for action in _data_menu(menu).actions()]
    assert "Add Rows / Columns..." in titles
    assert titles.index("Add Rows / Columns...") == titles.index("Import Images...") + 1


def test_add_rows_columns_action_disabled_with_no_datasets():
    parent = QWidget()
    menu = MainMenu(parent=parent, app_context=_fake_app_context(datasets=[]))

    assert menu.add_rows_columns_action.isEnabled() is False


def test_add_rows_columns_action_enabled_with_a_dataset():
    parent = QWidget()
    menu = MainMenu(parent=parent, app_context=_fake_app_context(datasets=[Mock(spec=Dataset)]))

    assert menu.add_rows_columns_action.isEnabled() is True


def test_add_rows_columns_action_is_refreshed_when_the_project_is_closed():
    app_context = _fake_app_context(datasets=[Mock(spec=Dataset)])
    parent = QWidget()
    menu = MainMenu(parent=parent, app_context=app_context)
    assert menu.add_rows_columns_action.isEnabled() is True

    app_state = app_context.get_app_state.return_value
    app_state.has_project = False
    app_state.current_project = None
    _subscribed(app_context)[ProjectEvents.PROJECT_CLOSED]({})

    assert menu.add_rows_columns_action.isEnabled() is False


def test_active_dataset_is_tracked_from_the_active_tab():
    """The dataset of the active tab is what the Data menu's dialogs preselect."""
    app_context = _fake_app_context(datasets=[Mock(spec=Dataset)])
    parent = QWidget()
    menu = MainMenu(parent=parent, app_context=app_context)
    assert menu.active_dataset_id is None

    on_tab_changed = _subscribed(app_context)[UIEvents.TAB_CHANGED]
    on_tab_changed({"tab_type": "dataset", "tab_id": "ds-7"})
    assert menu.active_dataset_id == "ds-7"

    # Switching to a non-dataset tab clears it rather than keeping a stale id.
    on_tab_changed({"tab_type": "chart", "tab_id": "ch-1"})
    assert menu.active_dataset_id is None
