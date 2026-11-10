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
from PySide6.QtWidgets import QApplication, QLabel, QPushButton
from shiboken6 import isValid

from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.components.tabs import welcome_tab as welcome_tab_module
from pandaplot.gui.components.tabs.welcome_tab import WelcomeTab
from pandaplot.gui.dialogs.create_or_open_project_dialog import (
    ACTION_BROWSE_EXAMPLES,
    ACTION_NEW_PROJECT,
    ACTION_OPEN_PROJECT,
)
from pandaplot.gui.dialogs.getting_started_step_dialog import GettingStartedStepDialog
from pandaplot.models.state.app_context import AppContext
from tests.gui.icon_testing import ICON_TOKENS, assert_tinted, strongest_pixel

SURFACE_PALETTE = {
    "card_bg": "#FFFFFF",
    "card_hover": "#F0F0F0",
    "card_pressed": "#E0E0E0",
    "card_border": "#CCCCCC",
    "base_fg": "#111111",
    "secondary_fg": "#666666",
    "accent": "#4A56C6",
}


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_context(tokens: dict[str, str] | None = None) -> Mock:
    """A context whose theme manager serves real design tokens and a surface palette."""
    app_context = Mock(spec=AppContext)
    app_context.event_bus = Mock()
    theme_manager = app_context.get_manager.return_value
    theme_manager.get_design_tokens.return_value = dict(tokens or ICON_TOKENS)
    theme_manager.get_surface_palette.return_value = dict(SURFACE_PALETTE)
    return app_context


def _make_welcome_tab():
    return WelcomeTab(_make_context(), None)


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
        tab.show_step_info("chart-line", "Explore Data", "intro text", ["tip one", "tip two"])
    finally:
        welcome_tab_module.GettingStartedStepDialog = original

    dialog_cls.assert_called_once_with(
        tab.app_context, "chart-line", "Explore Data", "intro text", ["tip one", "tip two"], tab
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


def test_recent_project_click_emits_signal_when_no_project_open():
    tab = _make_welcome_tab()
    tab.app_context.get_app_state.return_value.has_project = False
    spy = Mock()
    tab.recent_project_selected.connect(spy)

    tab._on_recent_project_clicked("/path/to/project.ppp")

    spy.assert_called_once_with("/path/to/project.ppp")


def test_recent_project_click_emits_without_its_own_prompt_when_project_open():
    """LoadProjectCommand owns the unsaved-changes prompt."""
    tab = _make_welcome_tab()
    tab.app_context.get_app_state.return_value.has_project = True
    spy = Mock()
    tab.recent_project_selected.connect(spy)

    tab._on_recent_project_clicked("/path/to/project.ppp")

    spy.assert_called_once_with("/path/to/project.ppp")
    tab.app_context.get_ui_controller.return_value.show_question.assert_not_called()


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


CARDS = [
    ("New Project", "plus-circle"),
    ("Open Project", "folder-open"),
    ("Import Data", "download-simple"),
    ("Examples", "books"),
]


def _cards(tab: WelcomeTab) -> list[QPushButton]:
    return tab.findChildren(QPushButton, "WelcomeCardButton")


def _icons(button: QPushButton) -> list[IconLabel]:
    return button.findChildren(IconLabel)


def _recent_item(tab: WelcomeTab, name="Demo", path="/projects/demo.ppp", last_opened="2026-01-01 10:00") -> QPushButton:
    item = tab.create_recent_project_item(name, path, last_opened)
    tab.recent_projects_layout.addWidget(item)
    return item


def test_action_cards_have_plain_titles_and_a_themed_icon():
    tab = _make_welcome_tab()

    cards = _cards(tab)

    assert len(cards) == len(CARDS)
    for card, (title, icon_name) in zip(cards, CARDS, strict=True):
        texts = [label.text() for label in card.findChildren(QLabel) if not isinstance(label, IconLabel)]
        assert title in texts
        (icon,) = _icons(card)
        assert icon.icon_name == icon_name
        assert icon.width() == 24
        assert_tinted(strongest_pixel(icon.pixmap().toImage()), ICON_TOKENS["accent_icon_active"])


def test_welcome_tab_no_longer_shows_emoji_in_action_cards():
    tab = _make_welcome_tab()

    for card in _cards(tab):
        for label in card.findChildren(QLabel):
            assert all(ord(char) < 0x2000 for char in label.text()), label.text()


def test_recent_project_item_icon_is_a_folder_icon_label_kept_last_in_its_layout():
    tab = _make_welcome_tab()
    item = _recent_item(tab)

    layout = item.layout()
    last_widget = layout.itemAt(layout.count() - 1).widget()
    assert isinstance(last_widget, IconLabel)
    assert last_widget.icon_name == "folder-simple"
    assert [label.text() for label in item.findChildren(QLabel) if not isinstance(label, IconLabel)][:2] == [
        "Demo",
        "/projects/demo.ppp",
    ]


def test_update_recent_projects_still_finds_the_path_label(monkeypatch):
    tab = _make_welcome_tab()
    entry = {"name": "Demo", "path": "/projects/demo.ppp", "last_opened": "2026-01-01 10:00"}
    monkeypatch.setattr(welcome_tab_module, "get_recent_projects", lambda _ctx: [entry])
    tab.update_recent_projects()
    (first_item,) = [tab.recent_projects_layout.itemAt(i).widget() for i in range(tab.recent_projects_layout.count())]

    tab.update_recent_projects()

    (item,) = [tab.recent_projects_layout.itemAt(i).widget() for i in range(tab.recent_projects_layout.count())]
    assert item is first_item, "an unchanged list must not be rebuilt"
    assert item.findChild(QLabel, "recentProjectPath").text() == "/projects/demo.ppp"


def test_update_recent_projects_rebuilds_when_the_list_changes(monkeypatch):
    tab = _make_welcome_tab()
    entries = [{"name": "A", "path": "/a.ppp", "last_opened": "x"}]
    monkeypatch.setattr(welcome_tab_module, "get_recent_projects", lambda _ctx: entries)
    tab.update_recent_projects()

    entries.append({"name": "B", "path": "/b.ppp", "last_opened": "y"})
    tab.update_recent_projects()

    paths = [tab.recent_projects_layout.itemAt(i).widget().findChild(QLabel, "recentProjectPath").text() for i in range(2)]
    assert paths == ["/a.ppp", "/b.ppp"]


def test_card_and_recent_icons_retint_after_a_theme_change():
    app_context = _make_context()
    tab = WelcomeTab(app_context, None)
    _recent_item(tab)
    recent_icon = _icons(tab.recent_projects_layout.itemAt(0).widget())[0]
    card_icon = _icons(_cards(tab)[0])[0]
    assert_tinted(strongest_pixel(card_icon.pixmap().toImage()), ICON_TOKENS["accent_icon_active"])

    dark = {**ICON_TOKENS, "accent_icon_active": "#8995FF"}
    app_context.get_manager.return_value.get_design_tokens.return_value = dark
    tab._apply_theme()

    assert_tinted(strongest_pixel(card_icon.pixmap().toImage()), "#8995FF")
    assert_tinted(strongest_pixel(recent_icon.pixmap().toImage()), "#8995FF")


def test_theme_change_skips_icons_of_removed_recent_items(monkeypatch):
    tab = _make_welcome_tab()
    entries = [{"name": "A", "path": "/a.ppp", "last_opened": "x"}]
    monkeypatch.setattr(welcome_tab_module, "get_recent_projects", lambda _ctx: entries)
    tab.update_recent_projects()
    entries[0] = {"name": "B", "path": "/b.ppp", "last_opened": "y"}
    tab.update_recent_projects()

    tab._apply_theme()

    assert all(isValid(label) for label in tab._icon_labels)
    assert len(tab._icon_labels) == len(CARDS) + 1


def test_rebuilding_the_recent_list_does_not_grow_the_tracked_icons(monkeypatch):
    tab = _make_welcome_tab()
    entries = [{"name": "A", "path": "/a.ppp", "last_opened": "x"}]
    monkeypatch.setattr(welcome_tab_module, "get_recent_projects", lambda _ctx: entries)
    tab.update_recent_projects()
    tracked_after_first_build = len(tab._icon_labels)

    for index in range(10):
        entries[0] = {"name": f"P{index}", "path": f"/p{index}.ppp", "last_opened": "y"}
        tab.update_recent_projects()

    assert len(tab._icon_labels) <= tracked_after_first_build + 1
    assert len([label for label in tab._icon_labels if isValid(label)]) == len(CARDS) + 1


def test_accent_icon_rule_is_gone_from_the_stylesheet():
    tab = _make_welcome_tab()

    assert "accentIcon" not in tab.styleSheet()
    assert tab.styleSheet() != ""


def test_getting_started_step_dialog_shows_an_icon_label():
    dialog = GettingStartedStepDialog(_make_context(), "palette", "Customize and Export", "intro", ["tip"], None)

    assert isinstance(dialog.icon_label, IconLabel)
    assert dialog.icon_label.icon_name == "palette"
    assert dialog.title_label.text() == "Customize and Export"


def test_action_cards_expose_an_accessible_name_and_description():
    tab = _make_welcome_tab()
    descriptions = {
        "New Project": "Create a new data visualization project",
        "Open Project": "Open an existing project file",
        "Import Data": "Import CSV or Excel data files",
        "Examples": "Browse sample projects and tutorials",
    }

    cards = {card.accessibleName(): card.accessibleDescription() for card in _cards(tab)}

    assert cards == descriptions


def test_getting_started_steps_expose_an_accessible_name_and_description():
    tab = _make_welcome_tab()

    steps = tab.findChildren(QPushButton, "WelcomeListButton")

    assert steps
    for step in steps:
        labels = [label.text() for label in step.findChildren(QLabel)]
        assert step.accessibleName() == labels[0]
        assert step.accessibleDescription() == labels[1]


def test_recent_project_items_expose_the_project_name_and_path():
    tab = _make_welcome_tab()

    item = _recent_item(tab, name="Demo", path="/projects/demo.ppp")

    assert item.accessibleName() == "Demo"
    assert item.accessibleDescription() == "/projects/demo.ppp"
