"""The tab header context menu shows theme-tinted bundled icons next to its text labels."""

import re
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QWidget

from pandaplot.gui.components.tabs.tab_bar import TabHeaderContextMenu
from pandaplot.gui.resources.icon_library import build_icon
from pandaplot.services.theme.theme_manager import ThemeManager

TOKENS = {"text_primary": "#1C1E26", "text_muted": "#6B7280", "accent_icon_active": "#404BAC", "text_disabled": "#AEB2BC"}
ICON_SIZE = 16
NON_ASCII = re.compile(r"[^\x00-\x7f]")

EXPECTED_ICONS = {
    "Open in New Window": "arrow-square-out",
    "Split Right": "square-split-horizontal",
    "Move to Other Pane": "arrows-left-right",
    "Close Split": "arrows-in-line-horizontal",
    "Close Tab": "x",
    "Close Others": "x-circle",
    "Close All": "x-square",
}


def _app_context() -> Mock:
    theme_manager = Mock(spec=ThemeManager)
    theme_manager.get_design_tokens.return_value = dict(TOKENS)
    app_context = Mock()
    app_context.get_manager.return_value = theme_manager
    return app_context


@pytest.fixture
def menu(qapp):
    parent = QWidget()
    menu = TabHeaderContextMenu(
        parent,
        1,
        3,
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        Mock(),
        can_split=True,
        can_merge=True,
        app_context=_app_context(),
    )
    yield menu
    parent.deleteLater()


def _pixels(icon):
    return icon.pixmap(QSize(ICON_SIZE, ICON_SIZE)).toImage()


def test_menu_offers_every_expected_action(menu):
    assert {action.text() for action in menu.actions()} == set(EXPECTED_ICONS)


def test_no_action_text_contains_emoji(menu):
    for action in menu.actions():
        assert NON_ASCII.search(action.text()) is None, f"{action.text()} contains emoji or non-ASCII text"


@pytest.mark.parametrize(("label", "icon_name"), list(EXPECTED_ICONS.items()), ids=list(EXPECTED_ICONS))
def test_action_uses_the_intended_icon(menu, label, icon_name):
    action = next(action for action in menu.actions() if action.text() == label)
    expected = build_icon(icon_name, TOKENS["text_primary"], size=ICON_SIZE, disabled_color=TOKENS["text_disabled"])

    assert _pixels(action.icon()) == _pixels(expected)
