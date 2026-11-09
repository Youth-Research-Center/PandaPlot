"""The project tree context menu shows theme-tinted bundled icons next to its text labels."""

import re
from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QTreeWidgetItem, QWidget

from pandaplot.gui.components.sidebar.project.project_context_manager import ProjectViewPanelContextManager
from pandaplot.gui.resources.icon_library import build_icon
from pandaplot.services.theme.theme_manager import ThemeManager

LIGHT_TOKENS = {"text_primary": "#1C1E26", "text_muted": "#6B7280", "accent_icon_active": "#404BAC", "text_disabled": "#AEB2BC"}
DARK_TOKENS = {"text_primary": "#E2E2E2", "text_muted": "#9AA0AB", "accent_icon_active": "#8995FF", "text_disabled": "#5B6270"}
ICON_SIZE = 16
NON_ASCII = re.compile(r"[^\x00-\x7f]")

EXPECTED_ICONS = {
    "Open": "folder-open",
    "Rename": "textbox",
    "Add Folder": "folder-simple-plus",
    "Add Note": "note-pencil",
    "Add Sketch": "pencil-simple-line",
    "Add Image Gallery": "images",
    "Import Data...": "download-simple",
    "Create Empty Dataset": "table",
    "Create Chart": "chart-line-up",
    "Analyze Measurements...": "ruler",
    "Import Images...": "image",
    "Delete": "trash",
}


@pytest.fixture
def tokens() -> dict[str, str]:
    return dict(LIGHT_TOKENS)


@pytest.fixture
def menu(qapp, tokens):
    theme_manager = Mock(spec=ThemeManager)
    theme_manager.build_context_menu_stylesheet.return_value = ""
    theme_manager.get_design_tokens.side_effect = lambda: dict(tokens)
    app_context = Mock()
    app_context.get_manager.return_value = theme_manager
    app_context.get_app_state.return_value = Mock(has_project=True)

    parent = QWidget()
    item = QTreeWidgetItem()
    item.setData(0, Qt.ItemDataRole.UserRole, {"type": "dataset"})
    menu = ProjectViewPanelContextManager(parent, app_context, Mock(), lambda _position: item, lambda position: position)
    yield menu
    parent.deleteLater()


def _pixels(icon):
    return icon.pixmap(QSize(ICON_SIZE, ICON_SIZE)).toImage()


def _expected(name: str, palette: dict[str, str]):
    return _pixels(build_icon(name, palette["text_primary"], size=ICON_SIZE, disabled_color=palette["text_disabled"]))


def test_every_action_has_the_intended_icon_and_no_emoji(menu):
    actions = [action for action in menu.actions() if not action.isSeparator()]

    assert {action.text() for action in actions} == set(EXPECTED_ICONS)
    for action in actions:
        assert NON_ASCII.search(action.text()) is None, f"{action.text()} contains emoji or non-ASCII text"
        assert _pixels(action.icon()) == _expected(EXPECTED_ICONS[action.text()], LIGHT_TOKENS), f"{action.text()} uses the wrong icon"


def test_icons_are_retinted_when_the_menu_is_shown_after_a_theme_change(menu, tokens):
    tokens.update(DARK_TOKENS)

    with patch.object(menu, "exec"):
        menu.show_context_menu(None)

    for action in menu.actions():
        if not action.isSeparator():
            assert _pixels(action.icon()) == _expected(EXPECTED_ICONS[action.text()], DARK_TOKENS), f"{action.text()} was not re-tinted"


def _strongest(icon: QIcon, mode: QIcon.Mode) -> QColor:
    image = icon.pixmap(QSize(32, 32), mode).toImage()
    pixels = (image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height()))
    return max(pixels, key=lambda pixel: pixel.alpha())


def test_hovered_icons_use_the_on_accent_colour_while_normal_icons_keep_the_text_colour(menu, tokens):
    tokens["text_on_accent"] = "#FFFFFF"

    with patch.object(menu, "exec"):
        menu.show_context_menu(None)

    actions = [action for action in menu.actions() if not action.isSeparator()]
    assert actions
    for action in actions:
        active = _strongest(action.icon(), QIcon.Mode.Active)
        normal = _strongest(action.icon(), QIcon.Mode.Normal)
        assert (active.red(), active.green(), active.blue()) == (255, 255, 255), action.text()
        assert abs(normal.red() - 0x1C) < 12 and abs(normal.blue() - 0x26) < 12, action.text()
