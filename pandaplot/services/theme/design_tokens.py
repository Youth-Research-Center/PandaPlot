"""Design tokens v2 (docs/design/design-system.md §5).

Neutral and teal values come from the design handoff with the spec's contrast fixes (§4.1, §4.2). Any accent other
than teal keeps the previous derivation until DS-05, except that the selected-item text is stepped to 4.5:1 (#581).
Legacy keys alias the semantic ones so existing widgets keep working until DS-86 removes them.
"""

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from PySide6.QtGui import QColor

from pandaplot.models.state.config import AppearanceConfig, Theme
from pandaplot.services.theme.contrast import adjust_until_contrast, contrasting_text_color, mix

TEAL_ACCENT = "#0E7C86"
_TEXT_CONTRAST = 4.5

_SPACE = {"xxs": 2, "xs": 4, "sm": 6, "md": 8, "lg": 12, "xl": 16, "xxl": 24}
_RADIUS = {"control": 4, "inner": 3, "chip": 4, "card": 6}
_TYPE_RATIOS = {
    "caption": 11 / 12, "label": 1.0, "value": 1.0, "section": 10.5 / 12, "subgroup": 11.5 / 12,
    "panel_title": 13 / 12, "dialog_title": 15 / 12,
}
_DEFAULT_DENSITY = {"control_h": 26, "pad_x": 8, "button_pad_x": 12, "row_gap": 6}

_NEUTRAL = {
    Theme.LIGHT: {
        "bg_canvas": "#FBFBFC", "bg_surface": "#FFFFFF", "bg_inset": "#F4F5F8",
        "border_panel": "#E5E6EA", "border_control": "#8B8E96", "border_subtle": "#ECEEF2",
        "text_primary": "#1C1E26", "text_secondary": "#3F4350", "text_muted": "#69707E", "text_disabled": "#AEB2BC",
        "danger": "#C82333", "warning": "#9A5B00", "success": "#1E7A46", "y2_accent": "#8A4BB8", "y2_accent_bg": "#F5EEFB",
        "toggle_off": "#8B8E96", "knob": "#FFFFFF",
    },
    Theme.DARK: {
        "bg_canvas": "#1F2123", "bg_surface": "#2A2C2E", "bg_inset": "#242628",
        "border_panel": "#3A3D40", "border_control": "#72767B", "border_subtle": "#33363A",
        "text_primary": "#E2E2E2", "text_secondary": "#C7CAD1", "text_muted": "#A3A9B3", "text_disabled": "#5B6270",
        "danger": "#F07171", "warning": "#E0A94A", "success": "#5BC48A", "y2_accent": "#B788D4", "y2_accent_bg": "#3A2E45",
        "toggle_off": "#737579", "knob": "#E8E9EB",
    },
}

_TEAL = {
    Theme.LIGHT: {
        "accent": "#0E7C86", "accent_hover": "#0B6C75", "accent_pressed": "#095C63", "accent_sel_bg": "#E3F4F5",
        "accent_sel_text": "#0A5F67", "focus": "#0E7C86", "on_accent": "#FFFFFF",
    },
    Theme.DARK: {
        "accent": "#11808A", "accent_hover": "#0F7780", "accent_pressed": "#0C6E77", "accent_sel_bg": "#163A3E",
        "accent_sel_text": "#8FDDE3", "focus": "#3FB6C1", "on_accent": "#FFFFFF",
    },
}

# Selected-row background for accents other than teal, unchanged from before DS-04 until DS-05 derives it.
_OTHER_ACCENT_SEL_BG = {Theme.LIGHT: "#EEF0FB", Theme.DARK: "#2E3350"}

_SERIES_PALETTE = {
    Theme.LIGHT: ["#A01818", "#4A56C6", "#2B7A8C", "#3FA46A", "#E09A1F"],
    Theme.DARK: ["#C24141", "#6B77E8", "#3F9BB0", "#3FA46A", "#E09A1F"],
}


def _theme_key(theme: Theme) -> Theme:
    return Theme.DARK if theme == Theme.DARK else Theme.LIGHT


def _accent_tokens(theme: Theme, accent: str) -> dict[str, str]:
    """Accent states: the teal table, or today's derivation with a legible selected text for any other accent."""
    if accent.upper() == TEAL_ACCENT:
        return dict(_TEAL[theme])
    color = QColor(accent)
    if not color.isValid():
        color = QColor(AppearanceConfig().accent_color)
    sel_bg = _OTHER_ACCENT_SEL_BG[theme]
    sel_text = adjust_until_contrast(color, QColor(sel_bg), min_ratio=_TEXT_CONTRAST, lighten=theme == Theme.DARK)
    name = color.name().upper()
    return {
        "accent": name,
        "accent_hover": color.lighter(110).name().upper(),
        "accent_pressed": color.darker(115).name().upper(),
        "accent_sel_bg": sel_bg,
        "accent_sel_text": sel_text.name().upper(),
        "focus": name,
        "on_accent": contrasting_text_color(color).name().upper(),
    }


def build_design_tokens(theme: Theme, accent: str) -> dict[str, Any]:
    """Return a fresh token dict for `theme` and `accent`.

    Args:
        theme: The theme; anything other than dark uses the light values.
        accent: The configured accent colour. `TEAL_ACCENT` (any case) selects the hand-tuned teal table.

    Returns:
        Semantic tokens, the `space`, `radius`, `type` and `density` tables, and the legacy aliases.
    """
    theme = _theme_key(theme)
    tokens: dict[str, Any] = {**_NEUTRAL[theme], **_accent_tokens(theme, accent)}
    tokens["accent_disabled"] = mix(tokens["accent"], tokens["bg_surface"], 0.55)
    tokens["space"] = dict(_SPACE)
    tokens["radius"] = dict(_RADIUS)
    tokens["type"] = dict(_TYPE_RATIOS)
    tokens["density"] = dict(_DEFAULT_DENSITY)
    tokens.update({
        "surface_white": tokens["bg_surface"], "surface_chrome": tokens["bg_canvas"], "surface_inset": tokens["bg_inset"],
        "accent_active_text": tokens["accent_sel_text"], "accent_selected_bg": tokens["accent_sel_bg"],
        "accent_icon_active": tokens["accent_sel_text"], "text_on_accent": tokens["on_accent"],
        "text_on_danger": contrasting_text_color(QColor(tokens["danger"])).name().upper(), "text_hint": tokens["text_muted"],
        "status_danger": tokens["danger"], "status_success": tokens["success"],
        "status_modified_text": tokens["warning"], "status_modified_dot": tokens["warning"],
        "series_palette": list(_SERIES_PALETTE[theme]),
        "radius_swatch": _RADIUS["control"], "radius_control": _RADIUS["control"],
        "radius_card": _RADIUS["card"], "radius_chip": _RADIUS["chip"],
        "font_size_group_title": 9,
    })
    return tokens


def freeze_tokens(tokens: Mapping[str, Any]) -> Mapping[str, Any]:
    """Return a read-only view of `tokens` whose nested tables are read-only too."""
    frozen = {key: MappingProxyType(dict(value)) if isinstance(value, dict) else value for key, value in tokens.items()}
    for key, value in frozen.items():
        if isinstance(value, list):
            frozen[key] = tuple(value)
    return MappingProxyType(frozen)
