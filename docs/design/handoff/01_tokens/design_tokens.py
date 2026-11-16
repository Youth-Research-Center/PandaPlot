"""PandaPlot design tokens — Step 1 picks: 1bL/1bD (cleaned base), 1eL/1eD (teal), 1hL/1hD (4/6/4), Default density.

Drop-in for ThemeManager.get_design_tokens(): returns the new semantic keys AND the
legacy keys (mapped) so existing widgets keep working while they migrate.
"""
from __future__ import annotations

SPACE = {"xxs": 2, "xs": 4, "sm": 6, "md": 8, "lg": 12, "xl": 16, "xxl": 24}
RADIUS = {"control": 4, "inner": 3, "chip": 4, "card": 6}
DENSITY = {
    "compact":     {"control_h": 22, "pad_x": 6,  "button_pad_x": 10, "row_gap": 4, "font_px": 12},
    "default":     {"control_h": 26, "pad_x": 8,  "button_pad_x": 12, "row_gap": 6, "font_px": 12},
    "comfortable": {"control_h": 30, "pad_x": 10, "button_pad_x": 14, "row_gap": 8, "font_px": 13},
}
TYPE = {  # px
    "caption": 11, "label": 12, "value": 12, "section": 10.5, "title": 13, "dialog_title": 15,
}

NEUTRAL = {
    "light": {
        "bg_canvas": "#FBFBFC", "bg_surface": "#FFFFFF", "bg_inset": "#F4F5F8",
        "border_panel": "#E5E6EA", "border_control": "#C9CDD5", "border_subtle": "#ECEEF2",
        "text_primary": "#1C1E26", "text_secondary": "#3F4350", "text_muted": "#6B7280",
        "text_disabled": "#AEB2BC", "danger": "#C82333", "toggle_off": "#C9CDD5", "knob": "#FFFFFF",
    },
    "dark": {
        "bg_canvas": "#1F2123", "bg_surface": "#2A2C2E", "bg_inset": "#242628",
        "border_panel": "#3A3D40", "border_control": "#5A5E64", "border_subtle": "#33363A",
        "text_primary": "#E2E2E2", "text_secondary": "#C7CAD1", "text_muted": "#A3A9B3",
        "text_disabled": "#5B6270", "danger": "#F07171", "toggle_off": "#4A4D52", "knob": "#E8E9EB",
    },
}

ACCENT_TEAL = {
    "light": {"accent": "#0E7C86", "accent_hover": "#0B6C75", "accent_pressed": "#095C63",
              "accent_sel_bg": "#E3F4F5", "accent_sel_text": "#0A5F67", "focus": "#0E7C86",
              "on_accent": "#FFFFFF"},
    "dark":  {"accent": "#11808A", "accent_hover": "#14909B", "accent_pressed": "#0C6E77",
              "accent_sel_bg": "#163A3E", "accent_sel_text": "#8FDDE3", "focus": "#3FB6C1",
              "on_accent": "#FFFFFF"},
}


def _mix(a: str, b: str, t: float) -> str:
    pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(pa, pb))


def get_design_tokens(theme: str = "light", density: str = "default") -> dict:
    theme = "dark" if theme == "dark" else "light"
    n, a = NEUTRAL[theme], ACCENT_TEAL[theme]
    t: dict = {**n, **a, **DENSITY[density]}
    t["accent_disabled"] = _mix(a["accent"], n["bg_surface"], 0.55)
    t["radius"] = RADIUS
    t["space"] = SPACE
    t["type"] = TYPE
    # legacy keys -> semantic (remove once all widgets migrate)
    t.update({
        "surface_white": n["bg_surface"], "surface_panel": n["bg_canvas"], "surface_inset": n["bg_inset"],
        "accent_active": a["accent"], "accent_active_text": a["accent_sel_text"],
        "accent_selected_bg": a["accent_sel_bg"], "text_hint": n["text_muted"],
        "radius_control": RADIUS["control"], "radius_card": RADIUS["card"],
        "radius_chip": RADIUS["chip"], "radius_swatch": RADIUS["control"],
    })
    return t


def build_stylesheet(t: dict) -> str:
    r, h, px = t["radius"], t["control_h"], t["pad_x"]
    return f"""
QPushButton[primary="true"] {{ background:{t['accent']}; color:{t['on_accent']}; border:1px solid {t['accent']};
  border-radius:{r['control']}px; min-height:{h - 2}px; padding:0 {t['button_pad_x']}px; font-weight:600; }}
QPushButton[primary="true"]:hover {{ background:{t['accent_hover']}; border-color:{t['accent_hover']}; }}
QPushButton[primary="true"]:pressed {{ background:{t['accent_pressed']}; }}
QPushButton[primary="true"]:disabled {{ background:{t['accent_disabled']}; border-color:{t['accent_disabled']}; }}
QPushButton {{ background:{t['bg_surface']}; color:{t['text_primary']}; border:1px solid {t['border_control']};
  border-radius:{r['control']}px; min-height:{h - 2}px; padding:0 {t['button_pad_x']}px; }}
QPushButton:hover {{ background:{t['bg_inset']}; }}
QPushButton:disabled {{ color:{t['text_disabled']}; border-color:{t['border_subtle']}; }}
QPushButton:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QLineEdit:focus {{
  border:1px solid {t['focus']}; }}
QComboBox, QDoubleSpinBox, QSpinBox, QLineEdit {{ background:{t['bg_surface']}; color:{t['text_primary']};
  border:1px solid {t['border_control']}; border-radius:{r['control']}px; min-height:{h - 2}px; padding:0 {px}px; }}
QFrame[card="true"] {{ background:{t['bg_surface']}; border:1px solid {t['border_panel']}; border-radius:{r['card']}px; }}
QPushButton[chip="true"] {{ border-radius:{r['chip']}px; min-height:{h - 4}px; padding:0 10px; }}
QPushButton[chip="true"]:checked {{ background:{t['accent']}; color:{t['on_accent']}; border-color:{t['accent']}; }}
QPushButton[segment="true"] {{ border:none; border-radius:{r['inner']}px; color:{t['text_muted']}; }}
QPushButton[segment="true"]:checked {{ background:{t['accent_sel_bg']}; color:{t['accent_sel_text']}; font-weight:600; }}
"""
