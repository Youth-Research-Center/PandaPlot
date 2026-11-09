"""The main menu shows theme-tinted bundled icons instead of emoji or bare text."""

import re
from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import QMenu, QWidget

from pandaplot.gui.components.main_menu.main_menu import MainMenu
from pandaplot.gui.resources.icon_library import build_icon
from pandaplot.services.theme.theme_manager import ThemeManager

LIGHT_TOKENS = {"text_primary": "#1C1E26", "text_muted": "#6B7280", "accent_icon_active": "#404BAC", "text_disabled": "#AEB2BC"}
DARK_TOKENS = {"text_primary": "#E2E2E2", "text_muted": "#9AA0AB", "accent_icon_active": "#8995FF", "text_disabled": "#5B6270"}
PALETTE = {"card_bg": "#FFFFFF", "base_fg": "#000000", "card_border": "#DDDDDD", "accent": "#4A90E2", "card_pressed": "#DEE2E6"}

ICON_SIZE = 16
PLACEHOLDER_TEXT = "No Recent Projects"
NON_ASCII = re.compile(r"[^\x00-\x7f]")

EXPECTED_ICONS = {
    ("File", "New"): "file-plus",
    ("File", "Open"): "folder-open",
    ("File", "Recent"): "clock-counter-clockwise",
    ("File", "Close"): "x",
    ("File", "Save"): "floppy-disk",
    ("File", "Save As..."): "floppy-disk-back",
    ("File", "Exit"): "sign-out",
    ("Edit", "Undo"): "arrow-u-up-left",
    ("Edit", "Redo"): "arrow-u-up-right",
    ("Data", "Import Data..."): "download-simple",
    ("Data", "Add Dataset"): "table",
    ("Data", "Import Images..."): "image",
    ("Data", "Add Rows / Columns..."): "rows-plus-bottom",
    ("Data", "New Note"): "note-pencil",
    ("Data", "New Sketch"): "pencil-simple-line",
    ("Chart", "Create New"): "chart-line-up",
    ("Settings", "Preferences..."): "gear",
    ("Help", "Help Topics..."): "question",
    ("Help", "Welcome"): "house",
    ("Help", "Open Example Project..."): "book-open",
    ("Help", "About"): "info",
}


@pytest.fixture
def tokens() -> dict[str, str]:
    return dict(LIGHT_TOKENS)


@pytest.fixture
def main_menu(qapp, tokens):
    theme_manager = Mock()
    theme_manager.get_surface_palette.return_value = dict(PALETTE)
    theme_manager.get_design_tokens.side_effect = lambda: dict(tokens)

    app_context = Mock()
    app_context.event_bus = Mock()
    app_context.get_app_state.return_value = Mock(has_project=False, current_project=None)
    app_context.get_manager.side_effect = lambda manager_type, *_args, **_kwargs: theme_manager if manager_type is ThemeManager else Mock()
    command_executor = Mock()
    command_executor.can_undo.return_value = False
    command_executor.can_redo.return_value = False
    command_executor.get_undo_description.return_value = None
    command_executor.get_redo_description.return_value = None
    app_context.get_command_executor.return_value = command_executor

    parent = QWidget()
    with patch("pandaplot.gui.components.main_menu.main_menu.get_recent_projects", return_value=[]):
        menu = MainMenu(parent=parent, app_context=app_context)
    yield menu
    parent.deleteLater()


def _menu_actions(menu: QMenu, top_level_title: str) -> list[tuple[str, QAction]]:
    """Every labelled action below `menu`, submenu entries included, as (top-level menu title, action)."""
    found: list[tuple[str, QAction]] = []
    for action in menu.actions():
        if action.isSeparator():
            continue
        found.append((top_level_title, action))
        if action.menu() is not None:
            found.extend(_menu_actions(action.menu(), top_level_title))
    return found


def _all_actions(main_menu: MainMenu) -> list[tuple[str, QAction]]:
    found: list[tuple[str, QAction]] = []
    for top_level in main_menu.actions():
        found.extend(_menu_actions(top_level.menu(), top_level.menu().title()))
    return [(title, action) for title, action in found if action.text() != PLACEHOLDER_TEXT]


def _strongest(action: QAction) -> QColor:
    image = action.icon().pixmap(QSize(32, 32)).toImage()
    pixels = (image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height()))
    return max(pixels, key=lambda pixel: pixel.alpha())


def test_every_menu_action_has_an_icon_and_no_emoji(main_menu):
    actions = _all_actions(main_menu)

    assert len(actions) >= len(EXPECTED_ICONS)
    for title, action in actions:
        assert not action.icon().isNull(), f"{title} > {action.text()} has no icon"
        assert NON_ASCII.search(action.text()) is None, f"{title} > {action.text()} contains emoji or non-ASCII text"


def test_every_menu_action_is_covered_by_the_expected_mapping(main_menu):
    labels = {(title, action.text()) for title, action in _all_actions(main_menu)}

    assert labels == set(EXPECTED_ICONS)


@pytest.mark.parametrize(("label", "icon_name"), list(EXPECTED_ICONS.items()), ids=[f"{t}-{n}" for (t, n) in EXPECTED_ICONS])
def test_menu_action_uses_the_intended_icon(main_menu, label, icon_name):
    action = next(action for title, action in _all_actions(main_menu) if (title, action.text()) == label)
    expected = build_icon(icon_name, LIGHT_TOKENS["text_primary"], size=ICON_SIZE, disabled_color=LIGHT_TOKENS["text_disabled"])

    assert action.icon().pixmap(QSize(ICON_SIZE, ICON_SIZE)).toImage() == expected.pixmap(QSize(ICON_SIZE, ICON_SIZE)).toImage()


def test_placeholder_recent_entry_has_no_icon(main_menu):
    placeholder = main_menu.recent_menu.actions()[0]

    assert placeholder.text() == PLACEHOLDER_TEXT
    assert placeholder.icon().isNull()


def _assert_close(actual: QColor, expected: str) -> None:
    wanted = QColor(expected)
    assert abs(actual.red() - wanted.red()) < 12
    assert abs(actual.green() - wanted.green()) < 12
    assert abs(actual.blue() - wanted.blue()) < 12


def test_icons_are_retinted_when_the_theme_changes(main_menu, tokens):
    _assert_close(_strongest(main_menu.undo_action), LIGHT_TOKENS["text_primary"])

    tokens.update(DARK_TOKENS)
    main_menu._apply_theme()

    _assert_close(_strongest(main_menu.undo_action), DARK_TOKENS["text_primary"])
