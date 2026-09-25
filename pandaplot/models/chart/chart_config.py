"""Typed chart-level configuration for Chart.config.

Chart-level fields (title/subtitle, legend, grid globals, colormap/
colorbar, figure size/dpi/background, 3-D view angle) are declared
directly; per-axis fields live on the nested `x`/`y`/`y2`/`z: AxisConfig`
(see #146, PR1 and PR2 -- PR1 typed the chart-level fields with a
dict-style shim for the not-yet-typed axis keys; PR2 types those too).

The dict-style shim (`_legacy`, get/__getitem__/__setitem__/update/
__contains__) is kept as a deliberate, permanent convenience API --
`Chart.update_config()` and a large chunk of the test suite construct
chart config via a flat dict of keys like {"y2_tick_mode": "count"} as
fixture-setup shorthand, and there is no need to force every one of those
call sites onto `config.y2.tick_mode = "count"` just because the
underlying storage is now typed. Any flat key matching a declared
ChartConfig field, or matching the `{prefix}_field`/`show_grid_{prefix}`
shape of a real AxisConfig field, resolves to real typed storage; only a
genuinely unrecognized key falls into `_legacy` (forward-compatibility
safety net, not a home for known keys). Production GUI code (chart_tab.py,
legend_tab.py, style_tab.py, axes_tab.py, chart_editor.py) uses real
attribute access throughout -- that's what actually gets typo'd while
being written, which is what #146 is about.
"""
from dataclasses import dataclass, field, fields
from typing import Any, ClassVar

from pandaplot.models.chart.axis_config import AxisConfig

_AXIS_PREFIXES = ("x", "y", "y2", "z")


def _resolve_axis_key(key: str) -> tuple[str, str] | None:
    """Split a flat axis-prefixed key ('y2_tick_mode', 'show_grid_x') into
    (axis_prefix, AxisConfig_field_name), or None if `key` isn't one."""
    if key.startswith("show_grid_"):
        prefix = key[len("show_grid_"):]
        return (prefix, "show_grid") if prefix in _AXIS_PREFIXES else None
    for prefix in _AXIS_PREFIXES:
        candidate = prefix + "_"
        if key.startswith(candidate):
            field_name = key[len(candidate):]
            if field_name in AxisConfig.__dataclass_fields__:
                return prefix, field_name
    return None


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
    width_cm: float | None = None
    height_cm: float | None = None
    dpi: int | None = None
    view_elev: float = 30.0
    view_azim: float = -60.0
    colormap: str = "viridis"
    colorbar_show: bool = True
    colorbar_label: str | None = None
    color_scale_auto: bool = True
    color_vmin: float = 0.0
    color_vmax: float = 1.0

    x: AxisConfig = field(default_factory=AxisConfig)
    y: AxisConfig = field(default_factory=lambda: AxisConfig(side="left", label_rotation=90.0))
    y2: AxisConfig = field(default_factory=lambda: AxisConfig(side="right", label_rotation=90.0))
    z: AxisConfig = field(default_factory=AxisConfig)

    # Not-yet-typed keys with no known home (forward-compatibility safety
    # net, not a home for known keys -- see module docstring).
    _legacy: dict = field(default_factory=dict, repr=False, compare=False)

    _FIELD_NAMES: ClassVar[frozenset] = frozenset()  # populated below

    def get(self, key: str, default: Any = None) -> Any:
        if key in ChartConfig._FIELD_NAMES:
            return getattr(self, key)
        axis_key = _resolve_axis_key(key)
        if axis_key is not None:
            prefix, field_name = axis_key
            return getattr(getattr(self, prefix), field_name)
        return self._legacy.get(key, default)

    def __getitem__(self, key: str) -> Any:
        if key in ChartConfig._FIELD_NAMES:
            return getattr(self, key)
        axis_key = _resolve_axis_key(key)
        if axis_key is not None:
            prefix, field_name = axis_key
            return getattr(getattr(self, prefix), field_name)
        return self._legacy[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key in ("x", "y", "y2", "z"):
            if isinstance(value, AxisConfig):
                setattr(self, key, value)
            else:
                # A raw dict (e.g. from JSON, via Chart.from_dict()'s
                # `config.update(data.get("config", {}))`) is merged onto
                # the EXISTING AxisConfig instance field-by-field, not used
                # to construct a fresh one -- the existing instance already
                # carries this axis's correct per-instance defaults (e.g.
                # y.side="left"), and a partial dict (any saved chart that
                # never touched "side") must not reset those untouched
                # fields back to AxisConfig's own generic defaults
                # (side=None) by replacing the whole object.
                axis = getattr(self, key)
                for sub_key, sub_value in value.items():
                    setattr(axis, sub_key, sub_value)
            return
        if key in ChartConfig._FIELD_NAMES:
            setattr(self, key, value)
            return
        axis_key = _resolve_axis_key(key)
        if axis_key is not None:
            prefix, field_name = axis_key
            setattr(getattr(self, prefix), field_name, value)
            return
        self._legacy[key] = value

    def __contains__(self, key: str) -> bool:
        if key in ChartConfig._FIELD_NAMES or _resolve_axis_key(key) is not None:
            return True
        return key in self._legacy

    def update(self, mapping: dict) -> None:
        for key, value in mapping.items():
            self[key] = value

    def to_dict(self) -> dict:
        data = {
            f.name: getattr(self, f.name)
            for f in fields(self)
            if f.name not in ("_legacy", "x", "y", "y2", "z")
        }
        data["x"] = _axis_to_dict(self.x)
        data["y"] = _axis_to_dict(self.y)
        data["y2"] = _axis_to_dict(self.y2)
        data["z"] = _axis_to_dict(self.z)
        data.update(self._legacy)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ChartConfig":
        known = {
            k: v for k, v in data.items()
            if k in cls._FIELD_NAMES and k not in ("x", "y", "y2", "z")
        }
        config = cls(**known)
        # Merge each saved axis dict onto the freshly-constructed
        # AxisConfig (which already carries this axis's correct
        # per-instance defaults, e.g. y.side="left") rather than replacing
        # it outright -- a saved chart whose "y" dict never touched "side"
        # must keep that default, not fall back to AxisConfig's own
        # generic one (side=None) via `AxisConfig(**data["y"])`.
        for prefix in ("x", "y", "y2", "z"):
            axis_data = data.get(prefix)
            if isinstance(axis_data, dict):
                axis = getattr(config, prefix)
                for sub_key, sub_value in axis_data.items():
                    setattr(axis, sub_key, sub_value)
        config._legacy = {
            k: v for k, v in data.items()
            if k not in cls._FIELD_NAMES and k not in ("x", "y", "y2", "z")
        }
        return config


def _axis_to_dict(axis: AxisConfig) -> dict:
    return {f.name: getattr(axis, f.name) for f in fields(axis)}


ChartConfig._FIELD_NAMES = frozenset(f.name for f in fields(ChartConfig) if f.name != "_legacy")
