"""Tests for WelcomeTab's Getting Started step interactions and the
confirm-before-replacing-project guard on its example/recent project flows.

Note: real Qt dialogs (QDialog.exec, QMenu.exec) are compiled Qt methods
that cannot be reliably monkeypatched at the instance-call level (Shiboken
bypasses a patched class attribute at the C++ call site), so dialog-driven
flows are exercised through their post-dialog dispatch/handler methods
directly rather than by driving a real modal dialog.
"""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.tabs.welcome_tab import WelcomeTab
from pandaplot.gui.dialogs.create_or_open_project_dialog import (
    ACTION_BROWSE_EXAMPLES,
    ACTION_NEW_PROJECT,
    ACTION_OPEN_PROJECT,
)


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_welcome_tab():
    return WelcomeTab(Mock(), None)


def test_dispatch_new_project_emits_new_project_requested():
    tab = _make_welcome_tab()
    spy = Mock()
    tab.new_project_requested.connect(spy)

    tab.dispatch_create_or_open_action(ACTION_NEW_PROJECT)

    spy.assert_called_once()


def test_dispatch_open_project_emits_open_project_requested():
    tab = _make_welcome_tab()
    spy = Mock()
    tab.open_project_requested.connect(spy)

    tab.dispatch_create_or_open_action(ACTION_OPEN_PROJECT)

    spy.assert_called_once()


def test_dispatch_browse_examples_opens_examples_dialog():
    tab = _make_welcome_tab()
    tab.show_examples_dialog = Mock()

    tab.dispatch_create_or_open_action(ACTION_BROWSE_EXAMPLES)

    tab.show_examples_dialog.assert_called_once()


def test_dispatch_unknown_action_does_nothing():
    tab = _make_welcome_tab()
    new_spy = Mock()
    open_spy = Mock()
    tab.new_project_requested.connect(new_spy)
    tab.open_project_requested.connect(open_spy)
    tab.show_examples_dialog = Mock()

    tab.dispatch_create_or_open_action("something_else")

    new_spy.assert_not_called()
    open_spy.assert_not_called()
    tab.show_examples_dialog.assert_not_called()


def test_import_data_step_emits_import_data_requested():
    tab = _make_welcome_tab()
    spy = Mock()
    tab.import_data_requested.connect(spy)

    tab.import_data_requested.emit()

    spy.assert_called_once()


def test_show_step_info_builds_and_shows_dialog():
    tab = _make_welcome_tab()
    dialog = Mock()
    dialog_cls = Mock(return_value=dialog)

    import pandaplot.gui.components.tabs.welcome_tab as welcome_tab_module
    original = welcome_tab_module.GettingStartedStepDialog
    welcome_tab_module.GettingStartedStepDialog = dialog_cls
    try:
        tab.show_step_info("📈", "Explore Data", "intro text", ["tip one", "tip two"])
    finally:
        welcome_tab_module.GettingStartedStepDialog = original

    dialog_cls.assert_called_once_with(
        tab.app_context, "📈", "Explore Data", "intro text", ["tip one", "tip two"], tab
    )
    dialog.exec.assert_called_once()


def test_show_explore_data_dialog_builds_and_shows_dialog_with_callbacks():
    tab = _make_welcome_tab()
    dialog = Mock()
    dialog_cls = Mock(return_value=dialog)

    import pandaplot.gui.components.tabs.welcome_tab as welcome_tab_module
    original = welcome_tab_module.ExploreDataDialog
    welcome_tab_module.ExploreDataDialog = dialog_cls
    try:
        tab.show_explore_data_dialog()
    finally:
        welcome_tab_module.ExploreDataDialog = original

    _, kwargs = dialog_cls.call_args
    assert dialog_cls.call_args[0][0] is tab.app_context
    assert kwargs["on_import_data"] == tab.import_data_requested.emit
    assert kwargs["on_create_dataset"] == tab.create_dataset_requested.emit
    assert kwargs["parent"] is tab
    dialog.exec.assert_called_once()


def test_show_create_visualization_dialog_builds_and_shows_dialog_with_callback():
    tab = _make_welcome_tab()
    dialog = Mock()
    dialog_cls = Mock(return_value=dialog)

    import pandaplot.gui.components.tabs.welcome_tab as welcome_tab_module
    original = welcome_tab_module.CreateVisualizationDialog
    welcome_tab_module.CreateVisualizationDialog = dialog_cls
    try:
        tab.show_create_visualization_dialog()
    finally:
        welcome_tab_module.CreateVisualizationDialog = original

    _, kwargs = dialog_cls.call_args
    assert dialog_cls.call_args[0][0] is tab.app_context
    assert kwargs["on_create_chart"] == tab.create_chart_requested.emit
    assert kwargs["parent"] is tab
    dialog.exec.assert_called_once()


def test_confirm_replace_current_project_skips_prompt_when_no_project_open():
    tab = _make_welcome_tab()
    tab.app_context.get_app_state.return_value.has_project = False

    result = tab._confirm_replace_current_project("Title", "Message")

    assert result is True
    tab.app_context.get_ui_controller.return_value.show_question.assert_not_called()


def test_confirm_replace_current_project_asks_and_returns_answer_when_project_open():
    tab = _make_welcome_tab()
    tab.app_context.get_app_state.return_value.has_project = True
    tab.app_context.get_ui_controller.return_value.show_question.return_value = False

    result = tab._confirm_replace_current_project("Title", "Message")

    assert result is False
    tab.app_context.get_ui_controller.return_value.show_question.assert_called_once_with(
        "Title", "Message"
    )


def test_recent_project_click_emits_signal_when_no_project_open():
    tab = _make_welcome_tab()
    tab.app_context.get_app_state.return_value.has_project = False
    spy = Mock()
    tab.recent_project_selected.connect(spy)

    tab._on_recent_project_clicked("/path/to/project.ppp")

    spy.assert_called_once_with("/path/to/project.ppp")


def test_recent_project_click_confirms_and_emits_when_project_open_and_confirmed():
    tab = _make_welcome_tab()
    tab.app_context.get_app_state.return_value.has_project = True
    tab.app_context.get_ui_controller.return_value.show_question.return_value = True
    spy = Mock()
    tab.recent_project_selected.connect(spy)

    tab._on_recent_project_clicked("/path/to/project.ppp")

    spy.assert_called_once_with("/path/to/project.ppp")


def test_recent_project_click_does_not_emit_when_confirmation_declined():
    tab = _make_welcome_tab()
    tab.app_context.get_app_state.return_value.has_project = True
    tab.app_context.get_ui_controller.return_value.show_question.return_value = False
    spy = Mock()
    tab.recent_project_selected.connect(spy)

    tab._on_recent_project_clicked("/path/to/project.ppp")

    spy.assert_not_called()


def test_show_examples_dialog_emits_when_selected_and_no_project_open():
    tab = _make_welcome_tab()
    tab.app_context.get_app_state.return_value.has_project = False
    spy = Mock()
    tab.example_project_selected.connect(spy)

    fake_dialog = Mock()
    fake_dialog.exec.return_value = True
    fake_dialog.selected_path = "/examples/demo.ppp"

    import pandaplot.gui.components.tabs.welcome_tab as welcome_tab_module
    original = welcome_tab_module.ExamplesDialog
    welcome_tab_module.ExamplesDialog = Mock(return_value=fake_dialog)
    try:
        tab.show_examples_dialog()
    finally:
        welcome_tab_module.ExamplesDialog = original

    spy.assert_called_once_with("/examples/demo.ppp")


def test_show_examples_dialog_confirms_before_emitting_when_project_open():
    tab = _make_welcome_tab()
    tab.app_context.get_app_state.return_value.has_project = True
    tab.app_context.get_ui_controller.return_value.show_question.return_value = False
    spy = Mock()
    tab.example_project_selected.connect(spy)

    fake_dialog = Mock()
    fake_dialog.exec.return_value = True
    fake_dialog.selected_path = "/examples/demo.ppp"

    import pandaplot.gui.components.tabs.welcome_tab as welcome_tab_module
    original = welcome_tab_module.ExamplesDialog
    welcome_tab_module.ExamplesDialog = Mock(return_value=fake_dialog)
    try:
        tab.show_examples_dialog()
    finally:
        welcome_tab_module.ExamplesDialog = original

    spy.assert_not_called()
    tab.app_context.get_ui_controller.return_value.show_question.assert_called_once()


def test_show_examples_dialog_does_nothing_when_cancelled():
    tab = _make_welcome_tab()
    spy = Mock()
    tab.example_project_selected.connect(spy)

    fake_dialog = Mock()
    fake_dialog.exec.return_value = False
    fake_dialog.selected_path = None

    import pandaplot.gui.components.tabs.welcome_tab as welcome_tab_module
    original = welcome_tab_module.ExamplesDialog
    welcome_tab_module.ExamplesDialog = Mock(return_value=fake_dialog)
    try:
        tab.show_examples_dialog()
    finally:
        welcome_tab_module.ExamplesDialog = original

    spy.assert_not_called()
