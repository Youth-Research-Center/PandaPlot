"""Tests for MainMenu."""
from unittest.mock import Mock, patch

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QWidget

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.commands.composite_command import CompositeCommand
from pandaplot.gui.components.main_menu.main_menu import MainMenu
from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel
from pandaplot.models.events import UIEvents
from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.help.help_catalog import HelpCatalog
from pandaplot.services.help.help_types import HelpCategory, HelpTopic
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
    command_executor.get_undo_description.return_value = None
    command_executor.get_redo_description.return_value = None
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

        command_executor = Mock()
        app_context.get_command_executor.return_value = command_executor
        action = _find_help_action(menu, "Open Example Project...")
        assert action.isEnabled()

        with patch("pandaplot.gui.dialogs.examples_dialog.ExamplesDialog") as dialog_cls:
            dialog = dialog_cls.return_value
            dialog.exec.return_value = True
            dialog.selected_path = "/examples/sample.pplot"

            action.trigger()

        dialog_cls.assert_called_once()
        command_executor.execute_command.assert_called_once()
        assert command_executor.execute_command.call_args[0][0].file_path == "/examples/sample.pplot"

    def test_help_menu_has_welcome_action(self, app_context):
        menu = MainMenu(parent=None, app_context=app_context)
        tab_container = Mock()
        original_side_effect = app_context.get_manager.side_effect

        def _get_manager(manager_type, *args, **kwargs):
            from pandaplot.gui.components.tabs.tab_container import TabContainer
            if manager_type is TabContainer:
                return tab_container
            return original_side_effect(manager_type, *args, **kwargs)

        app_context.get_manager.side_effect = _get_manager
        action = _find_help_action(menu, "Welcome")
        assert action.isEnabled()

        with patch("pandaplot.gui.dialogs.examples_dialog.ExamplesDialog") as dialog_cls:
            action.trigger()

        tab_container.show_welcome_tab.assert_called_once_with()
        dialog_cls.assert_not_called()

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
        dialog.deleteLater.assert_called_once_with()
        assert executed_command.as_untitled_copy is True

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
        dialog.deleteLater.assert_called_once_with()

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


def _help_catalog() -> HelpCatalog:
    return HelpCatalog(
        [
            HelpTopic(id="t.first", title="First topic", category=HelpCategory.STATISTICS, summary="First summary."),
            HelpTopic(id="t.second", title="Second topic", category=HelpCategory.FITTING, summary="Second summary."),
        ]
    )


def _help_requested_handler(app_context):
    for call in app_context.event_bus.subscribe.call_args_list:
        if call.args[0] == UIEvents.HELP_REQUESTED:
            return call.args[1]
    raise AssertionError("MainMenu did not subscribe to HELP_REQUESTED")


class TestMainMenuHelpTopics:
    @pytest.fixture(autouse=True)
    def _small_catalog(self, monkeypatch):
        monkeypatch.setattr("pandaplot.gui.dialogs.help.help_window.get_help_catalog", _help_catalog)

    def test_help_topics_action_is_first_in_help_menu_and_followed_by_separator(self, app_context):
        menu = MainMenu(parent=None, app_context=app_context)
        help_menu = next(m for m in menu.findChildren(type(menu.actions()[0].menu())) if m.title() == "Help")

        actions = help_menu.actions()

        assert actions[0].text() == "Help Topics..."
        assert actions[1].isSeparator()
        assert actions[0].parent() is help_menu

    def test_help_topics_action_has_help_contents_shortcut(self, app_context):
        menu = MainMenu(parent=None, app_context=app_context)

        action = _find_help_action(menu, "Help Topics...")

        assert action.shortcut() == QKeySequence(QKeySequence.StandardKey.HelpContents)

    def test_help_topics_action_opens_window_on_first_topic_not_on_checked_flag(self, qtbot, app_context):
        menu = MainMenu(parent=None, app_context=app_context)

        _find_help_action(menu, "Help Topics...").trigger()

        window = menu._help_window
        qtbot.addWidget(window)
        assert window.isVisible()
        assert window.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "t.first"

    def test_help_requested_event_opens_window_on_topic(self, qtbot, app_context):
        menu = MainMenu(parent=None, app_context=app_context)
        handler = _help_requested_handler(app_context)

        handler({"topic_id": "t.second"})

        window = menu._help_window
        qtbot.addWidget(window)
        assert window.isVisible()
        assert window.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "t.second"
        assert "Second summary." in window.browser.toPlainText()

    def test_help_requested_without_topic_shows_first_topic(self, qtbot, app_context):
        menu = MainMenu(parent=None, app_context=app_context)

        _help_requested_handler(app_context)({"topic_id": None})

        qtbot.addWidget(menu._help_window)
        assert menu._help_window.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "t.first"

    def test_second_request_reuses_the_same_window(self, qtbot, app_context):
        menu = MainMenu(parent=None, app_context=app_context)
        handler = _help_requested_handler(app_context)

        handler({"topic_id": "t.first"})
        first_window = menu._help_window
        qtbot.addWidget(first_window)
        handler({"topic_id": "t.second"})

        assert menu._help_window is first_window
        assert first_window.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "t.second"

    def test_minimized_window_is_restored_on_next_request(self, qtbot, app_context):
        menu = MainMenu(parent=None, app_context=app_context)
        menu.show_help("t.first")
        window = menu._help_window
        qtbot.addWidget(window)
        window.setWindowState(Qt.WindowState.WindowMinimized)
        assert window.windowState() & Qt.WindowState.WindowMinimized

        menu.show_help("t.second")

        assert not window.windowState() & Qt.WindowState.WindowMinimized
        assert not window.isMinimized()
        assert window.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "t.second"

    def test_closed_window_is_reopened_on_next_request(self, qtbot, app_context):
        menu = MainMenu(parent=None, app_context=app_context)
        menu.show_help("t.first")
        window = menu._help_window
        qtbot.addWidget(window)
        window.close()

        menu.show_help("t.second")

        assert menu._help_window is window
        assert window.isVisible()


class _BlockRecorder(QObject):
    """Event filter recording whether Qt currently blocks the watched window."""

    def __init__(self) -> None:
        super().__init__()
        self.blocked = False
        self.parent_changes = 0

    def eventFilter(self, _watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.WindowBlocked:
            self.blocked = True
        elif event.type() == QEvent.Type.WindowUnblocked:
            self.blocked = False
        elif event.type() == QEvent.Type.ParentChange:
            self.parent_changes += 1
        return False


def _modal(parent: QWidget, qtbot) -> QDialog:
    dialog = QDialog(parent)
    dialog.setModal(True)
    qtbot.addWidget(dialog)
    dialog.show()
    return dialog


class TestHelpWindowWithModalDialogs:
    @pytest.fixture(autouse=True)
    def _small_catalog(self, monkeypatch):
        monkeypatch.setattr("pandaplot.gui.dialogs.help.help_window.get_help_catalog", _help_catalog)

    @pytest.fixture
    def main_window(self, qtbot):
        window = QMainWindow()
        qtbot.addWidget(window)
        window.show()
        return window

    @pytest.fixture
    def menu(self, qtbot, app_context, main_window):
        menu = MainMenu(parent=main_window, app_context=app_context)
        yield menu
        if menu._help_window is not None and shiboken6.isValid(menu._help_window):
            menu._help_window.close()
            menu._help_window.deleteLater()

    def test_without_modal_window_is_owned_by_main_window(self, menu, main_window):
        menu.show_help("t.first")

        assert menu._help_window.parentWidget() is main_window
        assert menu.window() is main_window
        assert menu._help_window.isVisible()

    def test_opens_under_active_modal_unblocked_and_returns_to_main_window(self, qtbot, menu, main_window):
        dialog = _modal(main_window, qtbot)

        menu.show_help("t.second")
        help_window = menu._help_window
        recorder = _BlockRecorder()
        help_window.installEventFilter(recorder)
        qtbot.wait(0)

        assert help_window.parentWidget() is dialog
        assert recorder.blocked is False
        assert help_window.isVisible()

        dialog.reject()
        qtbot.wait(0)

        assert shiboken6.isValid(help_window)
        assert help_window.parentWidget() is main_window
        assert help_window.isVisible()

    def test_window_open_before_modal_is_blocked_then_unblocked_by_show_help(self, qtbot, menu, main_window):
        menu.show_help("t.first")
        help_window = menu._help_window
        recorder = _BlockRecorder()
        help_window.installEventFilter(recorder)

        dialog = _modal(main_window, qtbot)
        qtbot.wait(0)
        assert recorder.blocked is True

        menu.show_help("t.first")
        qtbot.wait(0)

        assert help_window.parentWidget() is dialog
        assert recorder.blocked is False

    def test_nested_modals_hand_the_window_back_one_level_at_a_time(self, qtbot, menu, main_window):
        outer = _modal(main_window, qtbot)
        inner = _modal(outer, qtbot)
        menu.show_help("t.first")
        help_window = menu._help_window
        recorder = _BlockRecorder()
        help_window.installEventFilter(recorder)
        assert help_window.parentWidget() is inner

        inner.reject()
        qtbot.wait(0)
        assert help_window.parentWidget() is outer
        assert recorder.blocked is False

        outer.reject()
        qtbot.wait(0)
        assert help_window.parentWidget() is main_window
        assert shiboken6.isValid(help_window)

    def test_deleting_a_visible_inner_modal_hands_the_window_to_the_outer_modal(self, qtbot, menu, main_window):
        outer = _modal(main_window, qtbot)
        # Not registered with qtbot: it is deleted here, and `outer` owns it until then.
        inner = QDialog(outer)
        inner.setModal(True)
        inner.show()
        menu.show_help("t.first")
        help_window = menu._help_window
        recorder = _BlockRecorder()
        help_window.installEventFilter(recorder)
        assert help_window.parentWidget() is inner

        inner.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qtbot.wait(0)

        assert shiboken6.isValid(help_window)
        assert help_window.parentWidget() is outer
        assert recorder.blocked is False

    def test_repeated_show_help_during_one_modal_reparents_once(self, qtbot, menu, main_window):
        dialog = _modal(main_window, qtbot)
        menu.show_help("t.first")
        recorder = _BlockRecorder()
        menu._help_window.installEventFilter(recorder)

        menu.show_help("t.second")
        menu.show_help("t.first")
        assert recorder.parent_changes == 0
        assert menu._help_window.parentWidget() is dialog

        dialog.reject()
        qtbot.wait(0)

        assert recorder.parent_changes == 1
        assert menu._help_window.parentWidget() is main_window
        assert len(menu._hooked_modals) == 0

    def test_reused_dialog_is_hooked_again_on_second_showing(self, qtbot, menu, main_window):
        dialog = _modal(main_window, qtbot)
        menu.show_help("t.first")
        dialog.reject()
        qtbot.wait(0)
        assert menu._help_window.parentWidget() is main_window

        dialog.show()
        menu.show_help("t.first")
        assert menu._help_window.parentWidget() is dialog
        dialog.reject()
        qtbot.wait(0)

        assert menu._help_window.parentWidget() is main_window

    def test_deleted_window_is_recreated(self, qtbot, menu):
        menu.show_help("t.first")
        old_window = menu._help_window
        shiboken6.delete(old_window)
        assert not shiboken6.isValid(old_window)

        menu.show_help("t.second")

        assert shiboken6.isValid(menu._help_window)
        assert menu._help_window is not old_window
        assert menu._help_window.isVisible()

    def test_first_help_under_modal_is_created_under_it_and_not_pinned_to_origin(self, qtbot, menu, main_window):
        dialog = _modal(main_window, qtbot)

        menu.show_help("t.first")

        assert menu._help_window.parentWidget() is dialog
        assert not menu._help_window.testAttribute(Qt.WidgetAttribute.WA_Moved)

    def test_closing_modal_does_not_activate_the_help_window(self, qtbot, menu, main_window):
        dialog = _modal(main_window, qtbot)
        menu.show_help("t.first")
        help_window = menu._help_window

        dialog.reject()
        qtbot.wait(0)

        assert help_window.parentWidget() is main_window
        assert help_window.isVisible()
        assert QApplication.activeWindow() is not help_window
        assert not help_window.testAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

    def test_help_window_survives_modal_deleted_while_visible(self, qtbot, menu, main_window):
        dialog = _modal(main_window, qtbot)
        menu.show_help("t.first")
        help_window = menu._help_window

        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        assert shiboken6.isValid(help_window)
        assert help_window.parentWidget() is main_window
        assert len(menu._hooked_modals) == 0

    def test_help_window_survives_modal_hidden_then_deleted(self, qtbot, menu, main_window):
        dialog = _modal(main_window, qtbot)
        menu.show_help("t.first")
        help_window = menu._help_window

        dialog.hide()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

        assert shiboken6.isValid(help_window)
        assert help_window.parentWidget() is main_window

    def test_stale_window_subscriptions_are_dropped_when_recreated(self, menu, app_context):
        bus = EventBus()
        app_context.event_bus = bus
        menu.show_help("t.first")
        old_window = menu._help_window
        old_handlers = [handler for handlers in bus._subscribers.values() for handler in handlers if getattr(handler, "__self__", None) is old_window]
        assert old_handlers
        shiboken6.delete(old_window)

        menu.show_help("t.first")

        remaining = [handler for handlers in bus._subscribers.values() for handler in handlers if getattr(handler, "__self__", None) is old_window]
        assert remaining == []
        assert menu._help_window is not old_window

    def test_modal_finishing_after_menu_is_destroyed_does_not_raise(self, qtbot, main_window, app_context):
        orphan_menu = MainMenu(parent=None, app_context=app_context)
        dialog = _modal(main_window, qtbot)
        orphan_menu.show_help("t.first")
        help_window = orphan_menu._help_window
        shiboken6.delete(orphan_menu)

        dialog.reject()
        qtbot.wait(0)

        assert not dialog.isVisible()
        assert shiboken6.isValid(help_window)


class _HelpPanel(SidebarPanel):
    """Minimal sidebar panel with a "?" button that points at a help topic."""

    def __init__(self, app_context, help_topic):
        super().__init__(app_context)
        self._topic = help_topic
        self._init_ui()

    def _init_ui(self):
        self._init_panel_layout()
        self._set_title("📊 Test Panel", help_topic=self._topic)

    def _apply_theme(self):
        pass


class TestHelpButtonIntegration:
    """Clicking a panel's "?" button reaches the MainMenu through a real EventBus."""

    @pytest.fixture(autouse=True)
    def _small_catalog(self, monkeypatch):
        monkeypatch.setattr("pandaplot.gui.dialogs.help.help_window.get_help_catalog", _help_catalog)

    def test_clicking_the_help_button_opens_the_help_window_on_the_panel_topic(self, qtbot, app_context):
        app_context.event_bus = EventBus()
        menu = MainMenu(parent=None, app_context=app_context)
        panel = _HelpPanel(app_context, "t.second")
        qtbot.addWidget(panel)
        assert panel.help_button is not None

        panel.help_button.click()

        window = menu._help_window
        assert window is not None
        qtbot.addWidget(window)
        assert window.isVisible()
        assert window.tree.currentItem().data(0, Qt.ItemDataRole.UserRole) == "t.second"
        assert "Second summary." in window.browser.toPlainText()


class TestMainMenuUndoRedoActions:
    """Regression (#206): Undo/Redo were always enabled regardless of
    whether CommandExecutor actually had anything to undo/redo."""

    def test_starts_disabled_when_history_is_empty(self, app_context):
        menu = MainMenu(parent=None, app_context=app_context)

        assert menu.undo_action.text() == "Undo"
        assert menu.redo_action.text() == "Redo"
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

        command_executor = app_context.get_command_executor()
        command_executor.can_undo.return_value = True
        command_executor.get_undo_description.return_value = "Rename column"
        command_executor.get_redo_description.return_value = None
        menu._update_undo_redo_actions()

        assert menu.undo_action.text() == "Undo Rename column"
        assert menu.redo_action.text() == "Redo"
        assert menu.undo_action.isEnabled() is True
        assert menu.redo_action.isEnabled() is False

        command_executor.can_undo.return_value = False
        command_executor.can_redo.return_value = True
        command_executor.get_undo_description.return_value = None
        command_executor.get_redo_description.return_value = "Delete chart"
        menu._update_undo_redo_actions()
        assert menu.undo_action.text() == "Undo"
        assert menu.redo_action.text() == "Redo Delete chart"

    def test_ampersand_in_description_is_not_treated_as_mnemonic(self, app_context):
        command_executor = app_context.get_command_executor()
        command_executor.can_undo.return_value = True
        command_executor.get_undo_description.return_value = "Rename column A&B"
        menu = MainMenu(parent=None, app_context=app_context)

        assert menu.undo_action.text() == "Undo Rename column A&&B"

    def test_labels_follow_execute_undo_redo_and_clear_history(self, app_context):
        class NamedCommand(Command):
            def __init__(self, name):
                super().__init__()
                self.name = name

            def display_name(self):
                return self.name

            def execute(self):
                return CommandResult.SUCCESS

            def undo(self):
                return CommandResult.SUCCESS

            def redo(self):
                return CommandResult.SUCCESS

        executor = CommandExecutor()
        app_context.get_command_executor.return_value = executor
        menu = MainMenu(parent=None, app_context=app_context)
        executor.on_history_changed = menu._update_undo_redo_actions

        composite = CompositeCommand(
            [NamedCommand("Rename column")], display_name="Analyze chart series",
        )
        executor.execute_command(composite)
        assert menu.undo_action.text() == "Undo Analyze chart series"
        assert menu.undo_action.isEnabled() is True

        executor.undo()
        assert menu.undo_action.text() == "Undo"
        assert menu.redo_action.text() == "Redo Analyze chart series"

        executor.redo()
        assert menu.undo_action.text() == "Undo Analyze chart series"
        assert menu.redo_action.text() == "Redo"

        executor.clear_history()
        assert menu.undo_action.text() == "Undo"
        assert menu.redo_action.text() == "Redo"
        assert menu.undo_action.isEnabled() is False
        assert menu.redo_action.isEnabled() is False

    def test_labels_update_when_oldest_command_is_evicted(self, app_context):
        class NamedCommand(Command):
            def __init__(self, name):
                super().__init__()
                self.name = name

            def display_name(self):
                return self.name

            def execute(self):
                return CommandResult.SUCCESS

            def undo(self):
                return CommandResult.SUCCESS

            def redo(self):
                return CommandResult.SUCCESS

        executor = CommandExecutor(max_undo_levels=1)
        app_context.get_command_executor.return_value = executor
        menu = MainMenu(parent=None, app_context=app_context)
        executor.on_history_changed = menu._update_undo_redo_actions

        executor.execute_command(NamedCommand("Older action"))
        executor.execute_command(NamedCommand("Rename column"))

        assert menu.undo_action.text() == "Undo Rename column"
        assert len(executor.undo_stack) == 1

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
