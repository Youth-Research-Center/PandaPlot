"""Typed per-axis configuration -- one AxisConfig instance per axis (x, y,
y2, z) on ChartConfig. Unlike ChartConfig/ChartStyle, this needs no
dict-style shim: every axis-prefixed config key that ever existed
(x_min, y_label_color, {prefix}_tick_mode, show_grid_{prefix}, ...) is a
declared field here from the start (see #146, PR2). `side` and
`label_rotation` have no single sensible default across all four axes --
ChartConfig's construction seeds the correct per-axis value (y.side="left",
y2.side="right", y/y2.label_rotation=90) rather than this class guessing.
"""
from dataclasses import dataclass


@dataclass
class AxisConfig:
    label: str = ""
    scale: str = "linear"
    auto_limits: bool = True
    min: float = 0.0
    max: float = 1.0
    tick_mode: str = "auto"
    tick_count: int = 5
    tick_step: float = 1.0
    tick_format: str = "auto"
    tick_format_custom: str = ""
    show_grid: bool = True
    font_size: int = 12
    side: str | None = None
    log_base: float = 10.0
    tick_direction: str = "out"
    minor_ticks: bool = False
    minor_tick_direction: str = "out"
    show_minor_grid: bool = False
    font_family: str = "DejaVu Sans"
    title_bold: bool = False
    title_italic: bool = False
    label_color: str = "#000000"
    match_x_label_color: bool = True
    label_rotation: float = 0.0
    tick_label_font_size: int = 10
    tick_label_font_family: str = "DejaVu Sans"
    tick_label_bold: bool = False
    tick_label_italic: bool = False
    tick_label_color: str = "#000000"
    tick_label_rotation: float = 0.0
    match_x_colors: bool = True
    spine_color: str = "#000000"
    major_tick_color: str = "#000000"
    minor_tick_color: str = "#000000"
