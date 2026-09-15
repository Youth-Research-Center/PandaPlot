"""Typed chart-level configuration for Chart.config.

Chart-level fields only (title/subtitle, legend, grid globals, colormap/
colorbar, figure size/dpi/background, 3-D view angle) -- see issue #146.
Axis-prefixed fields (x_min, y_label_color, {prefix}_tick_mode, ...) are
intentionally NOT typed here yet (tracked as a follow-up PR); they are
read/written through the ``_legacy`` dict via the dict-style shim methods
below so `axes_tab.py` and the axis-appearance loops in `style_tab.py`/
`chart_editor.py` keep working completely unmodified until that follow-up
gives them their own typed (nested AxisConfig) home. Remove `_legacy` and
these shim methods once that follow-up lands and nothing calls them anymore.
"""
from dataclasses import dataclass, field, fields
from typing import Any, ClassVar, Optional


@dataclass
class ChartConfig:
    title: str = ""
    subtitle: str = ""
    show_legend: bool = True
    legend_position: str = "upper right"
    legend_show_frame: bool = True
    legend_font_size: int = 10
    legend_font_family: str = "DejaVu Sans"
    legend_bg_color: str = "#ffffff"
    legend_columns: int = 1
    legend_bg_alpha: float = 1.0
    legend_custom_x: float = 1.02
    legend_custom_y: float = 0.5
    legend_custom_anchor: str = "center left"
    grid_style: str = "solid"
    grid_alpha: float = 0.3
    minor_grid_alpha: float = 0.15
    hist_bins: int = 20
    title_font_size: int = 14
    subtitle_font_size: int = 12
    title_font_family: str = "DejaVu Sans"
    subtitle_font_family: str = "DejaVu Sans"
    chart_padding: float = 2.0
    chart_padding_w: float = 2.0
    chart_padding_h: float = 2.0
    title_padding: float = 6.0
    main_title_padding: float = 10.0
    top_margin: float = 1.0
    title_bold: bool = True
    title_italic: bool = False
    subtitle_bold: bool = False
    subtitle_italic: bool = False
    title_color: str = "#000000"
    subtitle_color: str = "#000000"
    subtitle_match_title_color: bool = True
    width_cm: Optional[float] = None
    height_cm: Optional[float] = None
    dpi: Optional[int] = None
    view_elev: float = 30.0
    view_azim: float = -60.0
    colormap: str = "viridis"
    colorbar_show: bool = True
    colorbar_label: Optional[str] = None
    color_scale_auto: bool = True
    color_vmin: float = 0.0
    color_vmax: float = 1.0

    # Not-yet-typed axis-prefixed keys (PR2 scope). Excluded from
    # dataclasses.fields() iteration side effects by convention (never
    # read via getattr(self, "_legacy") through _FIELD_NAMES).
    _legacy: dict = field(default_factory=dict, repr=False, compare=False)

    _FIELD_NAMES: ClassVar[frozenset] = frozenset()  # populated below

    def get(self, key: str, default: Any = None) -> Any:
        if key in ChartConfig._FIELD_NAMES:
            return getattr(self, key)
        return self._legacy.get(key, default)

    def __getitem__(self, key: str) -> Any:
        if key in ChartConfig._FIELD_NAMES:
            return getattr(self, key)
        return self._legacy[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key in ChartConfig._FIELD_NAMES:
            setattr(self, key, value)
        else:
            self._legacy[key] = value

    def __contains__(self, key: str) -> bool:
        return key in ChartConfig._FIELD_NAMES or key in self._legacy

    def update(self, mapping: dict) -> None:
        for key, value in mapping.items():
            self[key] = value

    def to_dict(self) -> dict:
        data = {f.name: getattr(self, f.name) for f in fields(self) if f.name != "_legacy"}
        data.update(self._legacy)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ChartConfig":
        known = {k: v for k, v in data.items() if k in cls._FIELD_NAMES}
        legacy = {k: v for k, v in data.items() if k not in cls._FIELD_NAMES}
        config = cls(**known)
        config._legacy = legacy
        return config


ChartConfig._FIELD_NAMES = frozenset(f.name for f in fields(ChartConfig) if f.name != "_legacy")
