"""The shared theme helpers hand tests the real ThemeManager tokens, so test mocks cannot drift from production."""

import pytest

from pandaplot.models.state.config import AppearanceConfig, Theme
from pandaplot.services.theme.theme_manager import ThemeContext, ThemeManager
from tests.gui.icon_testing import ICON_TOKENS
from tests.gui.theme_testing import DEFAULT_ACCENT, design_tokens, surface_palette, theme_manager_for


def _production_manager(theme: Theme, accent: str) -> ThemeManager:
    manager = ThemeManager.__new__(ThemeManager)
    manager._current = ThemeContext(theme=theme, accent=accent, interface_font_size=10)
    return manager


def test_default_accent_is_the_configured_default() -> None:
    assert DEFAULT_ACCENT == AppearanceConfig().accent_color


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_design_tokens_are_the_real_tokens_for_the_theme(theme: Theme) -> None:
    assert design_tokens(theme) == _production_manager(theme, DEFAULT_ACCENT).get_design_tokens()


def test_design_tokens_follow_a_custom_accent() -> None:
    tokens = design_tokens(Theme.DARK, accent="#D03A8C")

    assert tokens == _production_manager(Theme.DARK, "#D03A8C").get_design_tokens()
    assert tokens["accent"] == "#D03A8C"


def test_design_tokens_default_to_the_light_theme() -> None:
    assert design_tokens() == design_tokens(Theme.LIGHT)


def test_design_tokens_apply_overrides_and_return_a_fresh_copy() -> None:
    tokens = design_tokens(font_size_group_title=11)
    tokens["accent"] = "#000000"

    assert tokens["font_size_group_title"] == 11
    assert design_tokens()["accent"] == DEFAULT_ACCENT


def test_design_tokens_reject_an_unknown_override() -> None:
    with pytest.raises(KeyError, match="not_a_token"):
        design_tokens(not_a_token="#000000")


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_surface_palette_is_the_real_palette(theme: Theme) -> None:
    assert surface_palette(theme) == _production_manager(theme, DEFAULT_ACCENT).get_surface_palette()


def test_theme_manager_for_carries_the_theme_and_accent() -> None:
    manager = theme_manager_for(Theme.DARK, accent="#D03A8C", interface_font_size=14)

    assert manager._current == ThemeContext(theme=Theme.DARK, accent="#D03A8C", interface_font_size=14)
    assert manager.get_design_tokens() == design_tokens(Theme.DARK, accent="#D03A8C")


def test_icon_tokens_are_a_subset_of_the_light_tokens() -> None:
    tokens = design_tokens(Theme.LIGHT)

    assert {key: tokens[key] for key in ICON_TOKENS} == dict(ICON_TOKENS)
