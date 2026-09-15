"""Tests for MainMenu."""
from unittest.mock import Mock, patch

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.main_menu.main_menu import MainMenu
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager

_FAKE_PALETTE = {
    "card_bg": "#FFFFFF",
    "base_fg": "#000000",
    "card_border": "#DDDDDD",
    "accent": "#4A90E2",
    "card_pressed": "#DEE2E6",
}


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    app_state = Mock()
    app_state.has_project = False
    app_state.current_project = None
    ctx.get_app_state.return_value = app_state

    # MainMenu queries can_undo()/can_redo() as soon as the Edit menu is
    # built (_create_edit_menu -> _update_undo_redo_actions), and QAction.
    # setEnabled requires an actual bool -- an unconfigured Mock() return
    # value raises a TypeError there, breaking every test that constructs
    # a MainMenu regardless of what it's actually testing.
    command_executor = Mock()
    command_executor.can_undo.return_value = False
    command_executor.can_redo.return_value = False
    ctx.get_command_executor.return_value = command_executor

    theme_manager = Mock()
    theme_manager.get_surface_palette.return_value = dict(_FAKE_PALETTE)

    def _get_manager(manager_type, *args, **kwargs):
        if manager_type is ThemeManager:
            return theme_manager
        return Mock()

    ctx.get_manager.side_effect = _get_manager
    return ctx


def _find_help_action(menu: MainMenu, text: str) -> QAction:
    help_menu = next(m for m in menu.findChildren(type(menu.actions()[0].menu())) if m.title() == "Help")
    return next(a for a in help_menu.actions() if a.text() == text)


class TestMainMenuHelpMenu:
    def test_help_menu_has_open_example_project_action(self, app_context):
        menu = MainMenu(parent=None, app_context=app_context)

        action = _find_help_action(menu, "Open Example Project...")

        assert action is not None

    def test_help_menu_has_welcome_action(self, app_context):
        menu = MainMenu(parent=None, app_context=app_context)

        action = _find_help_action(menu, "Welcome")

        assert action is not None

    def test_show_welcome_tab_delegates_to_the_tab_container_manager(self, app_context):
        menu = MainMenu(parent=None, app_context=app_context)
        tab_container = Mock()
        original_side_effect = app_context.get_manager.side_effect

        def _get_manager(manager_type, *args, **kwargs):
            from pandaplot.gui.components.tabs.tab_container import TabContainer
            if manager_type is TabContainer:
                return tab_container
            return original_side_effect(manager_type, *args, **kwargs)

        app_context.get_manager.side_effect = _get_manager

        menu.show_welcome_tab()

        tab_container.show_welcome_tab.assert_called_once_with()

    def test_open_example_project_loads_selected_example(self, app_context):
        menu = MainMenu(parent=None, app_context=app_context)
        command_executor = Mock()
        app_context.get_command_executor.return_value = command_executor

        with patch("pandaplot.gui.dialogs.examples_dialog.ExamplesDialog") as dialog_cls:
            dialog = dialog_cls.return_value
            dialog.exec.return_value = True
            dialog.selected_path = "/examples/sample.pplot"

            menu.show_examples_dialog()

        command_executor.execute_command.assert_called_once()
        executed_command = command_executor.execute_command.call_args[0][0]
        assert executed_command.file_path == "/examples/sample.pplot"

    def test_open_example_project_does_nothing_when_dialog_cancelled(self, app_context):
        menu = MainMenu(parent=None, app_context=app_context)
        command_executor = Mock()
        app_context.get_command_executor.return_value = command_executor

        with patch("pandaplot.gui.dialogs.examples_dialog.ExamplesDialog") as dialog_cls:
            dialog = dialog_cls.return_value
            dialog.exec.return_value = False
            dialog.selected_path = None

            menu.show_examples_dialog()

        command_executor.execute_command.assert_not_called()

    def test_open_example_project_delegates_the_unsaved_changes_guard(self, app_context):
        """Regression (PR #235 review): this used to ask its own "replace
        the open project?" question inline, duplicating (and only partially
        matching -- it didn't check is_modified, or "already open") the
        equivalent guard in OpenProjectCommand. That guard now lives in
        LoadProjectCommand itself (see test_load_project_command.py's
        TestLoadProjectCommandGuards), so this handler always hands off to
        it unconditionally, with no inline check of its own -- even when a
        project is already open."""
        app_context.get_app_state().has_project = True
        menu = MainMenu(parent=None, app_context=app_context)
        command_executor = Mock()
        app_context.get_command_executor.return_value = command_executor
        ui_controller = Mock()
        app_context.get_ui_controller.return_value = ui_controller

        with patch("pandaplot.gui.dialogs.examples_dialog.ExamplesDialog") as dialog_cls:
            dialog = dialog_cls.return_value
            dialog.exec.return_value = True
            dialog.selected_path = "/examples/sample.pplot"

            menu.show_examples_dialog()

        ui_controller.show_question.assert_not_called()
        command_executor.execute_command.assert_called_once()
        executed_command = command_executor.execute_command.call_args[0][0]
        assert executed_command.file_path == "/examples/sample.pplot"


class TestMainMenuUndoRedoActions:
    """Regression (#206): Undo/Redo were always enabled regardless of
    whether CommandExecutor actually had anything to undo/redo."""

    def test_starts_disabled_when_history_is_empty(self, app_context):
        menu = MainMenu(parent=None, app_context=app_context)

        assert menu.undo_action.isEnabled() is False
        assert menu.redo_action.isEnabled() is False

    def test_starts_enabled_when_history_already_has_entries(self, app_context):
        """Defensive: reflects CommandExecutor's actual state at menu-build
        time rather than assuming it's always empty."""
        app_context.get_command_executor().can_undo.return_value = True
        app_context.get_command_executor().can_redo.return_value = True

        menu = MainMenu(parent=None, app_context=app_context)

        assert menu.undo_action.isEnabled() is True
        assert menu.redo_action.isEnabled() is True

    def test_history_changed_event_updates_enabled_state(self, app_context):
        menu = MainMenu(parent=None, app_context=app_context)
        assert menu.undo_action.isEnabled() is False

        app_context.get_command_executor().can_undo.return_value = True
        menu._update_undo_redo_actions()

        assert menu.undo_action.isEnabled() is True
        assert menu.redo_action.isEnabled() is False

    def test_subscribes_to_history_changed_event(self, app_context):
        from pandaplot.models.events.event_types import AppEvents

        menu = MainMenu(parent=None, app_context=app_context)

        subscribed_events = [event_type for event_type, _handler in menu._subscriptions]
        assert AppEvents.HISTORY_CHANGED in subscribed_events

    def test_undo_action_triggers_command_executor_undo(self, app_context):
        menu = MainMenu(parent=None, app_context=app_context)
        command_executor = app_context.get_command_executor()

        # trigger() on a disabled QAction is a no-op (doesn't emit
        # triggered) -- enable it directly rather than going through
        # _update_undo_redo_actions, so this test exercises only the
        # trigger -> command_executor.undo() wiring, not the enabled-state
        # logic (covered separately above).
        menu.undo_action.setEnabled(True)
        menu.undo_action.trigger()

        command_executor.undo.assert_called_once()

    def test_redo_action_triggers_command_executor_redo(self, app_context):
        menu = MainMenu(parent=None, app_context=app_context)
        command_executor = app_context.get_command_executor()

        menu.redo_action.setEnabled(True)
        menu.redo_action.trigger()

        command_executor.redo.assert_called_once()


class TestMainMenuRecentSubmenu:
    """File > Recent (#221 items 3/4): reuses the same shared
    get_recent_projects lookup WelcomeTab uses for its recent-projects cards."""

    def test_recent_submenu_lives_under_file_menu(self, app_context):
        menu = MainMenu(parent=None, app_context=app_context)

        file_menu = next(m for m in menu.findChildren(type(menu.recent_menu)) if m.title() == "File")

        assert menu.recent_menu in [a.menu() for a in file_menu.actions()]

    def test_recent_submenu_shows_tooltips(self, app_context):
        menu = MainMenu(parent=None, app_context=app_context)

        assert menu.recent_menu.toolTipsVisible() is True

    def test_shows_placeholder_when_no_recent_projects(self, app_context):
        with patch("pandaplot.gui.components.main_menu.main_menu.get_recent_projects", return_value=[]):
            menu = MainMenu(parent=None, app_context=app_context)

        actions = menu.recent_menu.actions()
        assert len(actions) == 1
        assert actions[0].text() == "No Recent Projects"
        assert actions[0].isEnabled() is False

    def test_lists_one_action_per_recent_project(self, app_context):
        recent = [
            {"name": "Project A", "path": "/a/Project A.pplot", "last_opened": "2026-08-31 10:00"},
            {"name": "Project B", "path": "/b/Project B.pplot", "last_opened": "2026-08-30 10:00"},
        ]
        with patch("pandaplot.gui.components.main_menu.main_menu.get_recent_projects", return_value=recent):
            menu = MainMenu(parent=None, app_context=app_context)

        actions = menu.recent_menu.actions()
        assert [a.text() for a in actions] == ["Project A", "Project B"]
        assert [a.toolTip() for a in actions] == ["/a/Project A.pplot", "/b/Project B.pplot"]

    def test_triggering_recent_action_loads_that_project_when_none_is_open(self, app_context):
        """No project open -> nothing to lose, so it loads without asking."""
        recent = [{"name": "Project A", "path": "/a/Project A.pplot", "last_opened": "2026-08-31 10:00"}]
        with patch("pandaplot.gui.components.main_menu.main_menu.get_recent_projects", return_value=recent):
            menu = MainMenu(parent=None, app_context=app_context)

        command_executor = Mock()
        app_context.get_command_executor.return_value = command_executor
        ui_controller = Mock()
        app_context.get_ui_controller.return_value = ui_controller

        menu.recent_menu.actions()[0].trigger()

        ui_controller.show_question.assert_not_called()
        command_executor.execute_command.assert_called_once()
        executed_command = command_executor.execute_command.call_args[0][0]
        assert executed_command.file_path == "/a/Project A.pplot"

    def test_triggering_recent_action_confirms_when_a_project_is_open(self, app_context):
        app_context.get_app_state().has_project = True
        recent = [{"name": "Project A", "path": "/a/Project A.pplot", "last_opened": "2026-08-31 10:00"}]
        with patch("pandaplot.gui.components.main_menu.main_menu.get_recent_projects", return_value=recent):
            menu = MainMenu(parent=None, app_context=app_context)

        command_executor = Mock()
        app_context.get_command_executor.return_value = command_executor
        ui_controller = Mock()
        ui_controller.show_question.return_value = True
        app_context.get_ui_controller.return_value = ui_controller

        menu.recent_menu.actions()[0].trigger()

        ui_controller.show_question.assert_called_once()
        command_executor.execute_command.assert_called_once()
        executed_command = command_executor.execute_command.call_args[0][0]
        assert executed_command.file_path == "/a/Project A.pplot"

    def test_triggering_recent_action_does_not_load_when_confirmation_declined(self, app_context):
        app_context.get_app_state().has_project = True
        recent = [{"name": "Project A", "path": "/a/Project A.pplot", "last_opened": "2026-08-31 10:00"}]
        with patch("pandaplot.gui.components.main_menu.main_menu.get_recent_projects", return_value=recent):
            menu = MainMenu(parent=None, app_context=app_context)

        command_executor = Mock()
        app_context.get_command_executor.return_value = command_executor
        ui_controller = Mock()
        ui_controller.show_question.return_value = False
        app_context.get_ui_controller.return_value = ui_controller

        menu.recent_menu.actions()[0].trigger()

        ui_controller.show_question.assert_called_once()
        command_executor.execute_command.assert_not_called()

    def test_rebuilds_on_config_updated_event(self, app_context):
        with patch("pandaplot.gui.components.main_menu.main_menu.get_recent_projects", return_value=[]):
            menu = MainMenu(parent=None, app_context=app_context)

        recent = [{"name": "Project A", "path": "/a/Project A.pplot", "last_opened": "2026-08-31 10:00"}]
        with patch("pandaplot.gui.components.main_menu.main_menu.get_recent_projects", return_value=recent):
            menu._update_recent_menu({})

        assert [a.text() for a in menu.recent_menu.actions()] == ["Project A"]

    def test_repeated_rebuilds_do_not_accumulate_stale_actions(self, app_context):
        """Regression: actions must be parented to recent_menu (not self), so
        QMenu.clear() actually deletes the previous refresh's QActions rather
        than merely detaching them while MainMenu keeps them alive forever."""
        recent = [{"name": "Project A", "path": "/a/Project A.pplot", "last_opened": "2026-08-31 10:00"}]
        with patch("pandaplot.gui.components.main_menu.main_menu.get_recent_projects", return_value=recent):
            menu = MainMenu(parent=None, app_context=app_context)
            menu._update_recent_menu({})
            menu._update_recent_menu({})
            menu._update_recent_menu({})

        # findChildren also picks up QMenu's own internal menuAction(); exclude it.
        child_actions = set(menu.recent_menu.findChildren(QAction)) - {menu.recent_menu.menuAction()}
        assert len(child_actions) == 1

    def test_subscribes_to_config_updated_event(self, app_context):
        from pandaplot.models.events.event_types import ConfigEvents

        menu = MainMenu(parent=None, app_context=app_context)

        subscribed_events = [event_type for event_type, _handler in menu._subscriptions]
        assert ConfigEvents.CONFIG_UPDATED in subscribed_events
