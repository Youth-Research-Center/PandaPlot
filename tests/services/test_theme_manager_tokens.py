from pathlib import Path

import pytest

from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.state.config import ApplicationConfig, Theme
from pandaplot.services.config import ConfigManager
from pandaplot.services.theme.theme_manager import ThemeManager


def _make_manager(tmp_path: Path, theme: Theme = Theme.LIGHT, accent: str = "#4A56C6") -> ThemeManager:
    bus = EventBus()
    cm = ConfigManager(bus, config_path=tmp_path / "cfg.json", auto_save=False)
    tm = ThemeManager(bus, cm)
    cfg = ApplicationConfig.default()
    cfg.appearance.theme = theme
    cfg.appearance.accent_color = accent
    tm.apply_from_config(cfg)
    return tm


def test_design_tokens_has_all_required_keys(tmp_path):
    tm = _make_manager(tmp_path)
    tokens = tm.get_design_tokens()
    required = [
        "text_primary", "text_secondary", "text_muted", "text_hint", "text_disabled",
        "border_panel", "border_control", "border_subtle",
        "surface_white", "surface_chrome", "surface_inset",
        "accent", "accent_active_text", "accent_icon_active", "accent_selected_bg", "accent_disabled", "text_on_accent",
        "status_modified_dot", "status_modified_text", "status_success",
        "y2_accent", "y2_accent_bg", "series_palette",
        "radius_swatch", "radius_control", "radius_card", "radius_chip",
        "font_size_group_title",
    ]
    for key in required:
        assert key in tokens, f"missing token: {key}"


def test_design_tokens_accent_reflects_configured_accent(tmp_path):
    tm = _make_manager(tmp_path, accent="#FF0000")
    tokens = tm.get_design_tokens()
    assert tokens["accent"] == "#FF0000"


def test_design_tokens_light_and_dark_have_different_surfaces(tmp_path):
    light = _make_manager(tmp_path, theme=Theme.LIGHT).get_design_tokens()
    dark = _make_manager(tmp_path, theme=Theme.DARK).get_design_tokens()
    assert light["surface_white"] != dark["surface_white"]
    assert light["text_primary"] != dark["text_primary"]


def test_design_tokens_text_disabled_is_distinct_from_text_muted(tmp_path):
    light = _make_manager(tmp_path, theme=Theme.LIGHT).get_design_tokens()
    dark = _make_manager(tmp_path, theme=Theme.DARK).get_design_tokens()
    assert light["text_disabled"] != light["text_muted"]
    assert dark["text_disabled"] != dark["text_muted"]


def test_design_tokens_series_palette_is_five_colors(tmp_path):
    tm = _make_manager(tmp_path)
    tokens = tm.get_design_tokens()
    assert len(tokens["series_palette"]) == 5


def test_design_tokens_without_current_context_returns_light_defaults(tmp_path):
    bus = EventBus()
    cm = ConfigManager(bus, config_path=tmp_path / "cfg2.json", auto_save=False)
    tm = ThemeManager(bus, cm)  # apply_from_config never called
    tokens = tm.get_design_tokens()
    assert tokens["accent"] == "#4A56C6"


def test_default_accent_color_is_handoff_indigo():
    cfg = ApplicationConfig.default()
    assert cfg.appearance.accent_color == "#4A56C6"


def test_build_stylesheet_includes_shared_widget_rules(tmp_path):
    tm = _make_manager(tmp_path)
    qss = tm.build_stylesheet(tm._current)
    assert 'QFrame[card="true"]' in qss
    assert 'QPushButton[segment="true"]' in qss
    assert 'QPushButton[chip="true"]' in qss


def _contrast_ratio(foreground: str, background: str) -> float:
    """WCAG 2.x contrast ratio between two #rrggbb colours (computed independently of ThemeManager)."""
    def luminance(color: str) -> float:
        channels = []
        for start in (1, 3, 5):
            value = int(color[start:start + 2], 16) / 255
            channels.append(value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4)
        return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]

    lighter, darker = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
@pytest.mark.parametrize("accent", ["#4A56C6", "#1F2A8C", "#FF0000", "#00AA55", "#FFFFFF", "#000000"])
def test_accent_icon_active_has_non_text_contrast_on_the_selected_background(tmp_path, theme, accent):
    tokens = _make_manager(tmp_path, theme=theme, accent=accent).get_design_tokens()

    assert _contrast_ratio(tokens["accent_icon_active"], tokens["accent_selected_bg"]) >= 3.0


def test_accent_icon_active_is_lighter_than_the_accent_in_the_dark_theme(tmp_path):
    tokens = _make_manager(tmp_path, theme=Theme.DARK).get_design_tokens()

    assert tokens["accent_icon_active"] != tokens["accent_active_text"]
    assert _contrast_ratio(tokens["accent_active_text"], tokens["accent_selected_bg"]) < 3.0
    assert _contrast_ratio(tokens["accent_icon_active"], tokens["accent_selected_bg"]) >= 3.0


def test_accent_icon_active_matches_active_text_in_the_light_theme(tmp_path):
    tokens = _make_manager(tmp_path, theme=Theme.LIGHT).get_design_tokens()

    assert tokens["accent_icon_active"] == tokens["accent_active_text"]


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
@pytest.mark.parametrize("accent", ["#4A56C6", "#1F2A8C", "#FF0000", "#00AA55", "#FFD400", "#FFFFFF", "#000000"])
def test_text_on_accent_is_legible_on_the_accent(tmp_path, theme, accent):
    tokens = _make_manager(tmp_path, theme=theme, accent=accent).get_design_tokens()

    assert _contrast_ratio(tokens["text_on_accent"], tokens["accent"]) >= 4.5


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_text_on_accent_is_white_for_the_default_accent(tmp_path, theme):
    tokens = _make_manager(tmp_path, theme=theme).get_design_tokens()

    assert tokens["text_on_accent"].upper() == "#FFFFFF"
