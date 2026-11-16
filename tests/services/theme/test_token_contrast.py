"""Contrast pairs from spec §5.2 for the teal tables. Custom accents get the full §5.2 set in DS-05."""

import pytest
from PySide6.QtGui import QColor

from pandaplot.models.state.config import Theme
from pandaplot.services.theme.contrast import contrast_ratio
from pandaplot.services.theme.design_tokens import TEAL_ACCENT, build_design_tokens
from tests.gui.theme_testing import DEFAULT_ACCENT, theme_manager_for

THEMES = [Theme.LIGHT, Theme.DARK]
TEXT_TOKENS = ["text_primary", "text_secondary", "text_muted", "danger", "warning", "success", "y2_accent"]
TEXT_BACKGROUNDS = ["bg_surface", "bg_inset", "bg_canvas"]
NON_TEXT_TOKENS = ["border_control", "toggle_off", "focus"]
NON_TEXT_BACKGROUNDS = ["bg_surface", "bg_inset"]
TEXT_PAIRS = [
    ("y2_accent", "y2_accent_bg"),
    ("accent_sel_text", "accent_sel_bg"),
    ("on_accent", "accent"),
    ("on_accent", "accent_hover"),
    ("on_accent", "accent_pressed"),
]
ACCENTS_581 = [TEAL_ACCENT, DEFAULT_ACCENT]


def _ratio(tokens: dict, foreground: str, background: str) -> float:
    return contrast_ratio(QColor(tokens[foreground]), QColor(tokens[background]))


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("foreground", TEXT_TOKENS)
@pytest.mark.parametrize("background", TEXT_BACKGROUNDS)
def test_text_tokens_reach_4_5_on_every_background(theme: Theme, foreground: str, background: str) -> None:
    assert _ratio(build_design_tokens(theme, TEAL_ACCENT), foreground, background) >= 4.5


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize(("foreground", "background"), TEXT_PAIRS)
def test_text_pairs_reach_4_5(theme: Theme, foreground: str, background: str) -> None:
    assert _ratio(build_design_tokens(theme, TEAL_ACCENT), foreground, background) >= 4.5


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("foreground", NON_TEXT_TOKENS)
@pytest.mark.parametrize("background", NON_TEXT_BACKGROUNDS)
def test_non_text_tokens_reach_3_on_surfaces(theme: Theme, foreground: str, background: str) -> None:
    assert _ratio(build_design_tokens(theme, TEAL_ACCENT), foreground, background) >= 3.0


@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("accent", ACCENTS_581)
def test_selected_segment_text_is_legible(theme: Theme, accent: str) -> None:
    """#581: `QPushButton[segment][selected]` draws `accent_active_text` on `accent_selected_bg`."""
    manager = theme_manager_for(theme, accent=accent)
    assert manager._current is not None
    tokens = manager.get_design_tokens()
    qss = manager.build_stylesheet(manager._current)
    rule = qss.split('QPushButton[segment="true"][selected="true"] {', 1)[1].split("}", 1)[0]

    assert f"color: {tokens['accent_active_text']};" in rule
    assert f"background-color: {tokens['accent_selected_bg']};" in rule
    assert _ratio(tokens, "accent_active_text", "accent_selected_bg") >= 4.5
