"""The main menu's pressed state must stay readable in both themes.

Regression test: `:pressed` painted white text on `card_pressed`, which is a
near-white surface in the light theme -- the label vanished while the mouse was
held down on a menu (or menu bar) item.
"""
import re
from unittest.mock import Mock

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QWidget

from pandaplot.gui.components.main_menu.main_menu import MainMenu
from pandaplot.models.state.config import Theme
from tests.gui.theme_testing import design_tokens, surface_palette

# The menu is styled from the real get_surface_palette() and design tokens of each
# theme, with the configured default accent (DEFAULT_ACCENT): card_hover/card_pressed
# are surface_white darkened via QColor.darker(110)/darker(115) respectively (see the
# get_surface_palette() docstring for why they're derived rather than reusing
# surface_inset/surface_chrome).
THEMES = [Theme.LIGHT, Theme.DARK]
THEME_IDS = ["light", "dark"]


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _menu_with_palette(palette: dict, tokens: dict) -> tuple[MainMenu, QWidget]:
    theme_manager = Mock()
    theme_manager.get_surface_palette.return_value = palette
    theme_manager.get_design_tokens.return_value = tokens

    project = Mock()
    project.get_all_items.return_value = []
    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()
    app_context.get_manager.return_value = theme_manager
    # MainMenu queries can_undo()/can_redo() as soon as the Edit menu is
    # built, and QAction.setEnabled requires an actual bool.
    command_executor = Mock()
    command_executor.can_undo.return_value = False
    command_executor.can_redo.return_value = False
    app_context.get_command_executor.return_value = command_executor

    # The parent is returned so the caller keeps it alive; dropping it takes
    # the C++ side of the menu with it.
    parent = QWidget()
    return MainMenu(parent=parent, app_context=app_context), parent


def _relative_luminance(color: str) -> float:
    c = QColor(color)
    channels = []
    for value in (c.redF(), c.greenF(), c.blueF()):
        channels.append(value / 12.92 if value <= 0.03928
                        else ((value + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(fg: str, bg: str) -> float:
    light, dark = sorted((_relative_luminance(fg), _relative_luminance(bg)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def _rule(stylesheet: str, selector: str) -> dict:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", stylesheet)
    assert match, f"{selector} not found in stylesheet"
    return {
        key.strip(): value.strip()
        for key, value in (decl.split(":", 1)
                           for decl in match.group(1).split(";") if ":" in decl)
    }


@pytest.mark.parametrize("theme", THEMES, ids=THEME_IDS)
@pytest.mark.parametrize("selector", ["QMenuBar::item:pressed", "QMenu::item:pressed"])
def test_pressed_menu_items_are_readable(theme, selector):
    palette = surface_palette(theme)
    menu, _parent = _menu_with_palette(palette, design_tokens(theme))

    rule = _rule(menu.styleSheet(), selector)

    assert rule["color"] == palette["base_fg"]
    assert rule["background-color"] == palette["card_pressed"]
    assert _contrast_ratio(rule["color"], rule["background-color"]) >= 4.5


@pytest.mark.parametrize("theme", THEMES, ids=THEME_IDS)
def test_disabled_menu_items_are_visibly_muted_without_hovering(theme):
    """Issue #255: a disabled Undo/Redo action must look different from an
    enabled one at rest, not only once hovered/selected."""
    palette = surface_palette(theme)
    tokens = design_tokens(theme)
    menu, _parent = _menu_with_palette(palette, tokens)

    disabled_rule = _rule(menu.styleSheet(), "QMenu::item:disabled")
    enabled_rule = _rule(menu.styleSheet(), "QMenu::item")

    assert disabled_rule["color"] == tokens["text_disabled"]
    assert disabled_rule["color"] != enabled_rule.get("color", palette["base_fg"])
    assert disabled_rule["color"] != palette["base_fg"]

    # Hovering a disabled item must not light it up as if it were enabled.
    disabled_selected_rule = _rule(menu.styleSheet(), "QMenu::item:disabled:selected")
    assert disabled_selected_rule["color"] == tokens["text_disabled"]
    assert disabled_selected_rule["background-color"] == "transparent"
