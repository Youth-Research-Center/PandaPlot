from pathlib import Path

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
        "accent", "accent_active_text", "accent_selected_bg", "accent_disabled",
        "status_modified_dot", "status_modified_text", "status_success",
        "y2_accent", "y2_accent_bg", "series_palette",
        "radius_swatch", "radius_control", "radius_card", "radius_chip",
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
