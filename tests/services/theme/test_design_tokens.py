"""Design tokens v2: the handoff tables with the spec's fixes, aliases for existing widgets, and derived accents."""

from types import MappingProxyType
from typing import Any

import pytest
from PySide6.QtGui import QColor

from pandaplot.models.state.config import AppearanceConfig, Theme
from pandaplot.services.theme.contrast import contrast_ratio
from pandaplot.services.theme.design_tokens import TEAL_ACCENT, build_design_tokens, freeze_tokens

TEAL_LIGHT = {
    "accent": "#0E7C86", "accent_hover": "#0B6C75", "accent_pressed": "#095C63", "accent_sel_bg": "#E3F4F5",
    "accent_sel_text": "#0A5F67", "focus": "#0E7C86", "on_accent": "#FFFFFF",
}
TEAL_DARK = {
    "accent": "#11808A", "accent_hover": "#0F7780", "accent_pressed": "#0C6E77", "accent_sel_bg": "#163A3E",
    "accent_sel_text": "#8FDDE3", "focus": "#3FB6C1", "on_accent": "#FFFFFF",
}
LEGACY_ALIASES = {
    "surface_white": "bg_surface", "surface_chrome": "bg_canvas", "surface_inset": "bg_inset",
    "accent_active_text": "accent_sel_text", "accent_selected_bg": "accent_sel_bg", "accent_icon_active": "accent_sel_text",
    "text_on_accent": "on_accent", "text_hint": "text_muted", "status_danger": "danger", "status_success": "success",
    "status_modified_text": "warning", "status_modified_dot": "warning",
}


@pytest.mark.parametrize(("theme", "expected"), [(Theme.LIGHT, TEAL_LIGHT), (Theme.DARK, TEAL_DARK)])
def test_teal_uses_the_hand_tuned_table(theme: Theme, expected: dict[str, str]) -> None:
    tokens = build_design_tokens(theme, TEAL_ACCENT)

    assert {key: tokens[key] for key in expected} == expected


def test_teal_is_recognised_in_any_letter_case() -> None:
    assert build_design_tokens(Theme.DARK, "#0e7c86")["accent"] == "#11808A"


@pytest.mark.parametrize("accent", ["#0E7C86", "#0e7c86", "#FF0E7C86"])
def test_teal_is_detected_on_the_parsed_colour(accent: str) -> None:
    """An eight-digit ARGB string that QColor reads as opaque teal still selects the teal table."""
    tokens = build_design_tokens(Theme.DARK, accent)

    assert {key: tokens[key] for key in TEAL_DARK} == TEAL_DARK


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
@pytest.mark.parametrize("accent", ["#0E7C86", "#4A56C6", "#4a56c6", "#0e7c86"])
def test_every_colour_is_upper_case_hex(theme: Theme, accent: str) -> None:
    tokens = build_design_tokens(theme, accent)
    colours = [value for value in tokens.values() if isinstance(value, str) and value.startswith("#")]

    assert colours
    assert all(colour == colour.upper() and len(colour) == 7 for colour in colours)


@pytest.mark.parametrize(
    ("theme", "border_control", "toggle_off", "text_muted"),
    [(Theme.LIGHT, "#8B8E96", "#8B8E96", "#69707E"), (Theme.DARK, "#72767B", "#737579", "#A3A9B3")],
)
def test_contrast_fixes_from_spec_4_1(theme: Theme, border_control: str, toggle_off: str, text_muted: str) -> None:
    tokens = build_design_tokens(theme, TEAL_ACCENT)

    assert (tokens["border_control"], tokens["toggle_off"], tokens["text_muted"]) == (border_control, toggle_off, text_muted)


@pytest.mark.parametrize(
    ("theme", "expected"),
    [
        (Theme.LIGHT, {"warning": "#9A5B00", "success": "#1E7A46", "y2_accent": "#8A4BB8", "y2_accent_bg": "#F5EEFB"}),
        (Theme.DARK, {"warning": "#E0A94A", "success": "#5BC48A", "y2_accent": "#B788D4", "y2_accent_bg": "#3A2E45"}),
    ],
)
def test_new_semantic_tokens(theme: Theme, expected: dict[str, str]) -> None:
    tokens = build_design_tokens(theme, TEAL_ACCENT)

    assert {key: tokens[key] for key in expected} == expected


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
@pytest.mark.parametrize(("legacy", "semantic"), list(LEGACY_ALIASES.items()))
def test_legacy_keys_alias_the_new_ones(theme: Theme, legacy: str, semantic: str) -> None:
    tokens = build_design_tokens(theme, AppearanceConfig().accent_color)

    assert tokens[legacy] == tokens[semantic]


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_text_on_danger_is_legible_on_the_danger_fill(theme: Theme) -> None:
    tokens = build_design_tokens(theme, TEAL_ACCENT)

    assert contrast_ratio(QColor(tokens["text_on_danger"]), QColor(tokens["danger"])) >= 4.5


def test_layout_tables() -> None:
    tokens = build_design_tokens(Theme.LIGHT, TEAL_ACCENT)

    assert tokens["space"] == {"xxs": 2, "xs": 4, "sm": 6, "md": 8, "lg": 12, "xl": 16, "xxl": 24}
    assert tokens["radius"] == {"control": 4, "inner": 3, "chip": 4, "card": 6}
    assert tokens["type"]["section"] == pytest.approx(10.5 / 12)
    assert tokens["type"]["dialog_title"] == pytest.approx(15 / 12)
    assert tokens["density"] == {"control_h": 26, "pad_x": 8, "button_pad_x": 12, "row_gap": 6}
    assert (tokens["radius_control"], tokens["radius_card"], tokens["radius_chip"], tokens["radius_swatch"]) == (4, 6, 4, 4)


def test_accent_disabled_mixes_the_accent_into_the_surface() -> None:
    assert build_design_tokens(Theme.LIGHT, TEAL_ACCENT)["accent_disabled"] == "#93C4C9"


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
@pytest.mark.parametrize("accent", ["#4A56C6", "#FFD400"])
def test_custom_accent_keeps_the_chosen_colour(theme: Theme, accent: str) -> None:
    assert build_design_tokens(theme, accent)["accent"] == accent


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
@pytest.mark.parametrize("accent", ["#4A56C6", "#FFD400"])
def test_hover_and_pressed_step_away_from_the_on_accent_text(theme: Theme, accent: str) -> None:
    tokens = build_design_tokens(theme, accent)
    on, base = QColor(tokens["on_accent"]), QColor(tokens["accent"])

    assert contrast_ratio(on, QColor(tokens["accent_hover"])) > contrast_ratio(on, base)
    assert contrast_ratio(on, QColor(tokens["accent_pressed"])) > contrast_ratio(on, QColor(tokens["accent_hover"]))


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
@pytest.mark.parametrize("accent", ["#4A56C6", "#FF0000", "#2E9E44"])
def test_selected_background_is_a_tint_of_the_surface(theme: Theme, accent: str) -> None:
    tokens = build_design_tokens(theme, accent)
    sel_bg, surface, accent_color = QColor(tokens["accent_sel_bg"]), QColor(tokens["bg_surface"]), QColor(tokens["accent"])

    assert sel_bg != surface
    assert 1.05 < contrast_ratio(sel_bg, surface) < 2.0
    assert contrast_ratio(sel_bg, surface) < contrast_ratio(sel_bg, accent_color)


def test_dark_focus_is_lighter_than_the_accent_when_needed() -> None:
    tokens = build_design_tokens(Theme.DARK, "#4A56C6")

    assert tokens["focus"] != tokens["accent"]
    assert QColor(tokens["focus"]).lightness() > QColor(tokens["accent"]).lightness()


def test_an_invalid_accent_falls_back_to_the_default() -> None:
    assert build_design_tokens(Theme.LIGHT, "not-a-colour")["accent"] == AppearanceConfig().accent_color


def test_each_call_returns_an_independent_dict() -> None:
    first = build_design_tokens(Theme.LIGHT, TEAL_ACCENT)
    first["accent"] = "#000000"
    first["space"]["md"] = 99

    second = build_design_tokens(Theme.LIGHT, TEAL_ACCENT)
    assert second["accent"] == "#0E7C86"
    assert second["space"]["md"] == 8


def test_frozen_tokens_are_read_only_including_tables() -> None:
    frozen = freeze_tokens(build_design_tokens(Theme.LIGHT, TEAL_ACCENT))

    assert isinstance(frozen, MappingProxyType)
    writable: Any = frozen  # the type says read-only; this checks the runtime refuses writes too
    with pytest.raises(TypeError):
        writable["accent"] = "#000000"
    with pytest.raises(TypeError):
        writable["space"]["md"] = 1
