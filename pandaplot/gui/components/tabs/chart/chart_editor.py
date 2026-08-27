from typing import Optional, override

import numpy as np
from matplotlib.ticker import (
    AutoLocator,
    AutoMinorLocator,
    FuncFormatter,
    MaxNLocator,
    MultipleLocator,
    NullLocator,
    ScalarFormatter,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from pandaplot.gui.components.tabs.chart.chart_canvas import (
    ChartCanvas,
    cm_to_inches,
    fit_size_cm,
    run_with_mathtext_fallback,
)
from pandaplot.gui.components.tabs.chart.chart_error_bars import build_error_array
from pandaplot.gui.components.tabs.chart.chart_heatmap import resolve_color_limits
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.series_renderers import SERIES_RENDERERS
from pandaplot.gui.components.tabs.chart.series_renderers.line import render_line_series
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style import LineSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.events.event_types import ConfigEvents
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.config import (
    MAX_CHART_HEIGHT_CM,
    MAX_CHART_WIDTH_CM,
    MIN_CHART_HEIGHT_CM,
    MIN_CHART_WIDTH_CM,
)
from pandaplot.services.config.config_manager import ConfigManager
from pandaplot.services.theme.theme_manager import ThemeManager


def apply_chart_title(
    axes,
    title: str,
    subtitle: str,
    title_font_size: float,
    subtitle_font_size: float,
    title_padding: float = 6.0,
    main_title_padding: float = 10.0,
    fig_height_inches: float | None = None,
    *,
    title_bold: bool = True,
    title_italic: bool = False,
    subtitle_bold: bool = False,
    subtitle_italic: bool = False,
    title_color: str = "#000000",
    subtitle_color: str = "#000000",
    title_font_family: str = "DejaVu Sans",
    subtitle_font_family: str = "DejaVu Sans",
) -> None:
    """Render the title (figure-level) and subtitle (axes-level) as two
    independent Matplotlib Text artists so each can have its own font size
    -- a single set_title() call cannot mix font sizes within one string.

    `title_padding` mirrors Axes.set_title's `pad` (points, rcParam
    `axes.titlepad` default 6.0). `main_title_padding` is also in points,
    but Figure.suptitle() has no `pad` -- it is positioned via `y` (a 0-1
    fraction of figure height), so the value is converted using
    `fig_height_inches`, which should be the figure's TARGET height (the
    one about to be applied via ChartCanvas.set_size()), not its current
    height, since resizing afterward with a different height would make
    the conversion wrong. Defaults to the figure's current height.

    An empty `title`/`subtitle` clears that artist's text instead of
    repositioning it, avoiding a stale reserved-looking gap."""
    fig = axes.figure

    if title:
        height = fig_height_inches if fig_height_inches is not None else fig.get_figheight()
        y = 1.0 - (main_title_padding / 72.0) / height if height else 0.98
        fig.suptitle(
            title, fontsize=title_font_size, y=y,
            fontweight="bold" if title_bold else "normal",
            fontstyle="italic" if title_italic else "normal",
            color=title_color,
            fontfamily=title_font_family,
        )
    elif fig._suptitle is not None:
        fig._suptitle.set_text("")

    axes.set_title(
        subtitle, fontsize=subtitle_font_size, pad=title_padding,
        fontweight="bold" if subtitle_bold else "normal",
        fontstyle="italic" if subtitle_italic else "normal",
        color=subtitle_color,
        fontfamily=subtitle_font_family,
    )


def resolve_chart_size(
    chart_width_cm, chart_height_cm, chart_dpi,
    default_width_cm: float, default_height_cm: float, default_dpi: int,
) -> tuple[float, float, int]:
    """Resolve effective (width_cm, height_cm, dpi), preferring per-chart
    overrides and falling back to the app-wide Settings defaults for any
    value left as None."""
    width = chart_width_cm if chart_width_cm is not None else default_width_cm
    height = chart_height_cm if chart_height_cm is not None else default_height_cm
    dpi = chart_dpi if chart_dpi is not None else default_dpi
    return width, height, dpi


def apply_axis_ticks(
    axis, mode, count, step, fmt, custom_fmt,
    direction="out", *, minor_enabled=False, minor_direction=None,
    major_color="#000000", minor_color="#000000", labelcolor="#000000",
):
    """Apply tick placement, label formatting, direction, and minor ticks to
    a matplotlib Axis.

    mode/count/step control major tick placement ("auto"/"count"/"step");
    fmt/custom_fmt control the label format, with custom_fmt a Python
    format spec (e.g. "{:.2f}") used only when fmt == "custom".

    minor_direction independently controls which way minor ticks point;
    when not given it defaults to `direction` (the major-tick setting).
    """
    if mode == "count":
        axis.set_major_locator(MaxNLocator(nbins=count))
    elif mode == "step":
        axis.set_major_locator(MultipleLocator(step))
    else:
        axis.set_major_locator(AutoLocator())

    if fmt == "integer":
        axis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}"))
    elif fmt == "1decimal":
        axis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.1f}"))
    elif fmt == "2decimal":
        axis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.2f}"))
    elif fmt == "scientific":
        axis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.2e}"))
    elif fmt == "custom" and custom_fmt:
        def _safe_custom(v, _, _fmt=custom_fmt):
            try:
                return _fmt.format(v)
            except Exception:
                return str(v)
        axis.set_major_formatter(FuncFormatter(_safe_custom))
    else:
        axis.set_major_formatter(ScalarFormatter())

    axis.set_minor_locator(AutoMinorLocator() if minor_enabled else NullLocator())
    axis.set_tick_params(which="major", direction=direction, color=major_color, labelcolor=labelcolor)
    axis.set_tick_params(
        which="minor",
        direction=minor_direction if minor_direction is not None else direction,
        color=minor_color, labelcolor=labelcolor,
    )


def apply_tick_label_font(axis, font_size, font_family, *, bold=False, italic=False, rotation=0):
    """Set font size/family/weight/style/rotation on every major and minor
    tick-value label of a matplotlib Axis. `Axis.set_tick_params` (used by
    `apply_axis_ticks` for color/direction) has no font-family/weight/style
    knobs of its own, so those three (plus rotation) must be set directly on
    each tick label's Text artist instead."""
    fontweight = "bold" if bold else "normal"
    fontstyle = "italic" if italic else "normal"
    for label in axis.get_ticklabels() + axis.get_ticklabels(minor=True):
        label.set_fontsize(font_size)
        label.set_fontfamily(font_family)
        label.set_fontweight(fontweight)
        label.set_fontstyle(fontstyle)
        label.set_rotation(rotation)


def resolve_axis_color(prefix, own_color, match_enabled, x_color):
    """Resolve the effective color for a Y/Y2 axis element (label, tick
    marks, tick values, or spine): X's color when this axis is matching X
    (`match_enabled` True, the default), otherwise the axis's own saved
    color. Mirrors the `{prefix}_match_x_label_color`/`{prefix}_match_x_colors`
    config flags read by AxesTab.

    `prefix` isn't used by the logic itself -- it's accepted purely so call
    sites (e.g. `resolve_axis_color("y2", ...)`) stay self-documenting about
    which axis is being resolved, since `own_color`/`x_color` alone don't
    make that obvious at a glance.
    """
    return x_color if match_enabled else own_color


def resolve_scale_kwargs(scale: str, log_base: float) -> dict:
    """Build the extra kwargs for Axes.set_xscale/set_yscale: a log axis
    needs an explicit `base` (matplotlib requires base > 0 and base != 1,
    which also covers custom bases between 0 and 1); a linear axis's scale
    class doesn't accept a `base` kwarg at all, so it must be omitted
    entirely rather than passed as None/default.

    Validated defensively here (not just in the GUI's write path) because
    `log_base` may come from a hand-edited or corrupted project file: an
    invalid value (<= 0 or exactly 1.0) would otherwise reach
    Axes.set_xscale/set_yscale unfiltered and raise an unhandled
    ValueError, crashing rendering. Falls back to base 10 instead."""
    if scale != "log":
        return {}
    if log_base <= 0 or log_base == 1.0:
        log_base = 10.0
    return {"base": log_base}


def apply_spine_colors(axes, axes2, x_color, y_color, y2_color):
    """Color the axis box lines ('spines'). Bottom/top belong to x, left
    belongs to y. Right belongs to y2 when a secondary y axis is active,
    otherwise to y. When axes2 exists (twinx()), it draws its own full
    spine box on top of axes, so its bottom/top/left must be kept in sync
    with axes's x/y colors or they'd visually override them with black.
    axes's own right spine is always kept on y_color too; when axes2 is
    present it is visually covered by axes2's right spine (set to
    y2_color), but keeping it in sync avoids a stray black edge showing
    through and keeps axes internally consistent."""
    axes.spines["bottom"].set_color(x_color)
    axes.spines["top"].set_color(x_color)
    axes.spines["left"].set_color(y_color)
    axes.spines["right"].set_color(y_color)
    if axes2 is not None:
        axes2.spines["bottom"].set_color(x_color)
        axes2.spines["top"].set_color(x_color)
        axes2.spines["left"].set_color(y_color)
        axes2.spines["right"].set_color(y2_color)


_OUTSIDE_LEGEND_PLACEMENTS = {
    "outside_right": ("center left", (1.02, 0.5)),
    "outside_top": ("lower center", (0.5, 1.02)),
    "outside_bottom": ("upper center", (0.5, -0.08)),
}


def resolve_legend_placement(position: str, custom_x: float, custom_y: float, custom_anchor: str) -> dict:
    """Map a `legend_position` config value to matplotlib Legend kwargs.
    Existing inside positions (matplotlib `loc` strings, e.g. "upper
    right") pass through as `loc` only, unchanged. The three outside
    presets use a fixed `loc`/`bbox_to_anchor` pair. "custom" uses the
    user-supplied anchor corner and x/y (both 0-1, relative to the axes)."""
    if position in _OUTSIDE_LEGEND_PLACEMENTS:
        loc, bbox_to_anchor = _OUTSIDE_LEGEND_PLACEMENTS[position]
        return {"loc": loc, "bbox_to_anchor": bbox_to_anchor}
    if position == "custom":
        return {"loc": custom_anchor, "bbox_to_anchor": (custom_x, custom_y)}
    return {"loc": position}


def build_legend(
    axes, handles, labels,
    font_family: str, font_size,
    bg_color: str, *, show_frame: bool, columns: int, bg_alpha: float,
    placement_kwargs: dict,
):
    """Add a legend to `axes`, merging `font_size` into `prop` alongside
    `font_family`. Matplotlib silently ignores a `fontsize=` kwarg whenever
    `prop=` is also passed -- the legend text falls back to
    rcParams["legend.fontsize"] regardless of what's configured, unless the
    size is merged into `prop` itself, as done here."""
    return axes.legend(
        handles, labels,
        facecolor=bg_color,
        frameon=show_frame,
        ncol=columns,
        framealpha=bg_alpha,
        prop={"family": font_family, "size": font_size},
        **placement_kwargs,
    )


def apply_layout_with_legend(fig, tight_layout_kwargs: dict, *, legend_placed_outside: bool) -> None:
    """Run Figure.tight_layout(), re-running it once more when the legend was
    placed outside the axes (`bbox_to_anchor` set). The first pass runs
    before Matplotlib can account for an out-of-axes legend's extent, so
    without the second pass the legend gets clipped by the figure boundary.

    tight_layout() is also where Matplotlib's mathtext parser runs while
    measuring text extents, so invalid mathtext (e.g. unbalanced `$...$`)
    raises here instead of when the text was set. Mathtext is re-enabled
    before each attempt (so a fixed label renders as math again) and only
    disabled -- falling back to literal text -- if that attempt still
    fails, so a bad label cannot leave the chart preview stuck mid-update."""
    run_with_mathtext_fallback(fig, lambda: fig.tight_layout(**tight_layout_kwargs))
    if legend_placed_outside:
        fig.tight_layout(**tight_layout_kwargs)


def _resolve_error_column(df, column_name):
    """Best-effort lookup of an optional error column.

    Returns None (never an error) when the column isn't configured or no
    longer exists, so a stale error-column reference just silently drops
    the error bars instead of hiding the whole series.
    """
    if not column_name or column_name not in df.columns:
        return None
    return df[column_name].to_numpy()


def resolve_series_data(project, series, chart_type=None) -> SeriesData:
    """Resolve a DataSeries against the project's datasets.

    Returns (x_data, y_data, x_err, y_err, x_err_minus, y_err_minus, None) on
    success, or all-None with a message when the dataset or a required
    column cannot be found. An empty x_column means "plot against the
    DataFrame index" (SERIES_TYPE_SPECS[...].needs_x_column) -- keyed by
    `chart_type` when passed explicitly (wizard_preview.py's throwaway
    DataSeries lack a reliable series_type), otherwise by the series' own
    series_type. Histograms never use x_column, so x_data is always None
    for a hist series.

    Error columns are resolved leniently since optional (see
    _resolve_error_column); x_err_minus/y_err_minus only matter when
    error_bars.error_symmetric is False. Secondary columns (u_data/v_data
    required, magnitude_data optional) and the Colormap/Heatmap Z column
    are resolved the same way, but required ones error out the whole
    series when unresolvable.
    """
    from pandaplot.models.project.items.chart import resolve_series_column
    from pandaplot.models.project.items.dataset import Dataset

    if project is None:
        return SeriesData(None, None, None, None, None, None, "no project loaded")

    dataset = project.find_item(series.dataset_id)
    if not isinstance(dataset, Dataset) or dataset.data is None:
        return SeriesData(None, None, None, None, None, None, f"dataset '{series.dataset_id}' not found")

    df = dataset.data
    # Resolve column references by stable id (name is only a fallback), so a
    # renamed column keeps binding without the series being touched.
    y_column = resolve_series_column(dataset, series.y_column_id, series.y_column)
    if not y_column:
        return SeriesData(None, None, None, None, None, None, "no Y column configured")

    needs_x_column = SERIES_TYPE_SPECS[SeriesType(chart_type) if chart_type else series.series_type].needs_x_column
    x_column = resolve_series_column(dataset, series.x_column_id, series.x_column) if needs_x_column else None

    missing = [c for c in (x_column, y_column)
               if c and c not in df.columns]
    if missing:
        cols = ", ".join(f"'{c}'" for c in missing)
        return SeriesData(None, None, None, None, None, None, f"column {cols} not found in '{dataset.name}'")

    x_data = (df[x_column] if x_column else df.index) if needs_x_column else None
    error_bars = getattr(series.style, "error_bars", None) or ErrorBarConfig()
    x_err = _resolve_error_column(df, resolve_series_column(dataset, error_bars.x_error_column_id, error_bars.x_error_column))
    y_err = _resolve_error_column(df, resolve_series_column(dataset, error_bars.y_error_column_id, error_bars.y_error_column))
    x_err_minus = _resolve_error_column(df, resolve_series_column(dataset, error_bars.x_error_minus_column_id, error_bars.x_error_minus_column))
    y_err_minus = _resolve_error_column(df, resolve_series_column(dataset, error_bars.y_error_minus_column_id, error_bars.y_error_minus_column))

    u_data = v_data = magnitude_data = None
    if SERIES_TYPE_SPECS[SeriesType(chart_type) if chart_type else series.series_type].needs_secondary_columns:
        u_column = resolve_series_column(dataset, series.style.u_column_id, series.style.u_column)
        v_column = resolve_series_column(dataset, series.style.v_column_id, series.style.v_column)
        if not u_column or not v_column:
            return SeriesData(None, None, None, None, None, None, "no U/V column configured")
        missing_uv = [c for c in (u_column, v_column) if c not in df.columns]
        if missing_uv:
            cols = ", ".join(f"'{c}'" for c in missing_uv)
            return SeriesData(None, None, None, None, None, None, f"column {cols} not found in '{dataset.name}'")
        u_data = df[u_column]
        v_data = df[v_column]
        magnitude_column = resolve_series_column(dataset, series.style.magnitude_column_id, series.style.magnitude_column)
        if magnitude_column and magnitude_column in df.columns:
            magnitude_data = df[magnitude_column]

    z_data = None
    if SERIES_TYPE_SPECS[SeriesType(chart_type) if chart_type else series.series_type].needs_z_column:
        z_column = resolve_series_column(dataset, series.style.z_column_id, series.style.z_column)
        if not z_column:
            return SeriesData(None, None, None, None, None, None, "no Z column configured")
        if z_column not in df.columns:
            return SeriesData(None, None, None, None, None, None, f"Z column '{z_column}' not found")
        z_data = df[z_column]

    return SeriesData(x_data, df[y_column], x_err, y_err, x_err_minus, y_err_minus, None,
                      u_data=u_data, v_data=v_data, magnitude_data=magnitude_data, z_data=z_data)


def compute_axis_data_range(project, data_series, prefix: str, *, positive_only: bool = False) -> Optional[tuple[float, float]]:
    """Compute (min, max) across every series plotted against the given
    axis (`prefix` in "x", "y", "y2"). "x" includes all series; "y"/"y2"
    are filtered by `series.y_axis`. Returns None when no series have
    resolvable data for this axis, so callers can fall back to a default
    range.

    Each series' own `series_type` (not a chart-wide type) governs whether
    it needs an x-column, so mixed-type charts do not apply one series'
    column requirements to another.

    `positive_only` should be True for a Log-scaled axis: matplotlib's
    autoscale silently ignores non-positive values on a log axis, and this
    matches that behavior instead of letting them leak into the Range card
    or set_xlim/set_ylim."""
    from pandaplot.models.project.items.chart import YAxis

    ranges: list[tuple[float, float]] = []
    for series in data_series:
        if prefix in ("y", "y2"):
            wants_secondary = prefix == "y2"
            if (series.y_axis == YAxis.SECONDARY) != wants_secondary:
                continue
        data = resolve_series_data(project, series)
        if data.error:
            continue
        arr = data.x_data if prefix == "x" else data.y_data
        if arr is None:
            continue
        values = np.asarray(arr, dtype=float)
        values = values[np.isfinite(values)]
        if positive_only:
            values = values[values > 0]
        if values.size:
            ranges.append((float(values.min()), float(values.max())))

    if not ranges:
        return None
    return (min(r[0] for r in ranges), max(r[1] for r in ranges))


class ChartEditorWidget(PWidget):
    """
    A chart editor widget with configuration options and live preview.
    """

    def __init__(self, app_context: AppContext, chart: Chart, parent: QWidget):
        super().__init__(app_context=app_context, parent=parent)
        self.chart = chart

        # Colorbar drawn for the current colormap/heatmap render, if any. It
        # lives on its own figure axes (not the main axes cleared each
        # render), so update_chart must explicitly remove the previous one
        # before drawing again, or stale colorbars would accumulate.
        self._colorbar = None

        self._initialize()
        self.load_chart_config()
        self.update_chart()

        # Apply theme after UI is fully constructed
        QTimer.singleShot(100, self._apply_theme)

        # Fit the chart to the preview panel once the layout has settled and
        # the panel's real viewport size is known (a new chart has no saved
        # size yet, so start it filling the visible preview area).
        QTimer.singleShot(100, self._apply_initial_fit_size)

    @override
    def _apply_theme(self):
        """Apply theme-specific styling to all components."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        
        # Get theme-appropriate colors
        card_bg = palette.get("card_bg", "#f8f9fa")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#000000")
        secondary_fg = palette.get("secondary_fg", "#555555")
        
        # Apply styling to preview frame
        self.preview_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 6px;
            }}
        """)
        
        # Apply styling to status frame
        self.status_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 6px;
                padding: 1px;
            }}
        """)
        
        # Apply styling to dataset label
        self.dataset_label.setStyleSheet(f"color: {secondary_fg}; font-size: 12px;")
        
        # Apply styling to status label (preserve color logic based on current text)
        self._update_status_label_style()
        
        # Apply theme to toolbar if it exists
        self._apply_toolbar_theme()

        # Apply theme to chart canvas navigation if it exists
        self.chart_canvas.apply_navigation_theme(base_fg, card_bg, card_border)

    def _apply_toolbar_theme(self):
        """Apply theme-aware styling to the preview toolbar."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        base_fg = palette.get("base_fg", "#000000")
        card_bg = palette.get("card_bg", "#f8f9fa")
        card_border = palette.get("card_border", "#dee2e6")
        
        self.preview_toolbar.setStyleSheet(f"""
            QToolBar {{
                background-color: {card_bg};
                border-bottom: 1px solid {card_border};
                padding: 4px;
                color: {base_fg};
            }}
            QToolBar QToolButton {{
                color: {base_fg};
                background-color: transparent;
                border: none;
                padding: 6px 10px;
                margin: 1px;
                border-radius: 3px;
                font-weight: 500;
            }}
            QToolBar QToolButton:hover {{
                background-color: {card_border};
                color: {base_fg};
            }}
            QToolBar QToolButton:pressed {{
                background-color: {card_border};
                color: {base_fg};
            }}
        """)

    def _update_status_label_style(self):
        """Update status label styling based on current status and theme."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        secondary_fg = palette.get("secondary_fg", "#555555")
        
        status_text = self.status_label.text()
        
        # Determine color based on status
        if "Modified" in status_text:
            color = "#ffc107"  # Warning yellow
        elif "Saved" in status_text:
            color = "#28a745"  # Success green
        elif "Error" in status_text:
            color = "#dc3545"  # Error red
        else:
            color = secondary_fg  # Default theme color
            
        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")

    @override
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(4)

        # Main content area with splitter
        self.create_content_section(layout)

        # Status bar
        self.create_status_section(layout)

    def setup_event_subscriptions(self):
        """Set up event subscriptions for the chart editor."""
        # Subscribe to config updates to adjust display settings like DPI
        self.subscribe_to_event(ConfigEvents.CONFIG_UPDATED, self._on_config_updated)

    def _on_config_updated(self, data):
        """Handle config.updated events to apply display changes (e.g., DPI)."""
        try:
            cfg = data.get("config") if isinstance(data, dict) else None
            if not cfg:
                return
            dpi = getattr(getattr(cfg, "chart_display", None), "dpi", None)
            if dpi and isValid(self.chart_canvas):
                self.chart_canvas.set_dpi(
                    dpi,
                    pad=self.chart.config.get("chart_padding", 2.0),
                    w_pad=self.chart.config.get("chart_padding_w", 2.0),
                    h_pad=self.chart.config.get("chart_padding_h", 2.0),
                    top_margin=self.chart.config.get("top_margin", 1.0),
                )
        except Exception:
            self.logger.exception("Failed applying updated DPI setting")

    def create_content_section(self, layout):
        """Create the main content section with chart preview only."""
        # Chart preview section (full width, no configuration panel)
        self.create_chart_preview_section(layout)

    def create_chart_preview_section(self, layout):
        """Create the chart preview section."""
        self.preview_frame = QFrame()
        # Set size policy to expand and take all available space
        self.preview_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        preview_layout = QVBoxLayout(self.preview_frame)
        preview_layout.setContentsMargins(10, 10, 10, 10)

        # Preview toolbar with chart actions and size controls
        self.preview_toolbar = QToolBar()
        self.preview_toolbar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Add chart actions
        self.create_chart_toolbar_actions(self.preview_toolbar)

        # Fetch preferred DPI and default chart size from config manager
        dpi = 100
        default_width_cm = 20
        default_height_cm = 15
        try:
            cfg_manager = self.app_context.get_manager(ConfigManager)
            cfg = getattr(cfg_manager, "config", None)
            chart_display = getattr(cfg, "chart_display", None) if cfg else None
            if chart_display:
                dpi = getattr(chart_display, "dpi", dpi) or dpi
                default_width_cm = getattr(chart_display, "default_width_cm", default_width_cm) or default_width_cm
                default_height_cm = getattr(chart_display, "default_height_cm", default_height_cm) or default_height_cm
        except Exception:
            pass

        # Resolve the initial canvas size/DPI, preferring per-chart overrides
        # (chart.config) over the app-wide Settings defaults fetched above.
        width_cm, height_cm, dpi = resolve_chart_size(
            self.chart.config.get("width_cm"), self.chart.config.get("height_cm"),
            self.chart.config.get("dpi"), default_width_cm, default_height_cm, dpi,
        )

        # Chart canvas
        self.chart_canvas = ChartCanvas(
            width=cm_to_inches(width_cm), height=cm_to_inches(height_cm), dpi=dpi)
        self.chart_canvas.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Combine our chart-action toolbar and matplotlib's pan/zoom/save
        # toolbar into a single row instead of stacking them, to save space.
        toolbar_row = QHBoxLayout()
        toolbar_row.setContentsMargins(0, 0, 0, 0)
        toolbar_row.setSpacing(4)
        toolbar_row.addWidget(self.preview_toolbar)
        if hasattr(self.chart_canvas, "navigation_toolbar"):
            nav_toolbar = self.chart_canvas.navigation_toolbar
            nav_toolbar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
            toolbar_row.addWidget(nav_toolbar)
        toolbar_row.addStretch()
        preview_layout.addLayout(toolbar_row)

        # Wrap chart canvas in scroll area for large charts
        canvas_scroll = QScrollArea()
        canvas_scroll.setWidgetResizable(False)
        canvas_scroll.setWidget(self.chart_canvas)
        canvas_scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        canvas_scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        canvas_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        canvas_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self.canvas_scroll = canvas_scroll
        preview_layout.addWidget(canvas_scroll)

        layout.addWidget(self.preview_frame)

    def create_status_section(self, layout):
        """Create the status section."""
        self.status_frame = QFrame()
        # Set fixed height to prevent expansion
        self.status_frame.setFixedHeight(30)
        self.status_frame.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(8, 1, 8, 1)
        status_layout.setSpacing(4)

        datasets = self.chart.get_all_datasets()
        dataset_text = f"Datasets: {', '.join(datasets)}" if datasets else "Sample Data"
        self.dataset_label = QLabel(dataset_text)
        status_layout.addWidget(self.dataset_label)

        status_layout.addStretch()

        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)

        layout.addWidget(self.status_frame)

    def create_chart_toolbar_actions(self, toolbar):
        """Create toolbar actions for chart operations."""
        # Refresh action: re-read the current dataset values and redraw. The
        # chart already refreshes automatically on dataset changes, but this
        # lets the user force a redraw on demand.
        refresh_action = QAction("♻️ Refresh", self)
        refresh_action.setToolTip("Reload data from the datasets and redraw the chart")
        refresh_action.triggered.connect(self._on_refresh)
        toolbar.addAction(refresh_action)

        # Reset action
        reset_action = QAction("🔄 Reset", self)
        reset_action.triggered.connect(self.reset_chart)
        toolbar.addAction(reset_action)

        # Reset zoom button (the nav toolbar's own Home/Back/Forward are
        # removed since they rely on a view stack that goes stale whenever
        # the chart re-renders; this uses the chart's own tracked limits)
        reset_zoom_action = QAction("🔍 Reset Zoom", self)
        reset_zoom_action.setToolTip("Reset chart zoom to fit all data")
        reset_zoom_action.triggered.connect(self._on_reset_zoom)
        toolbar.addAction(reset_zoom_action)

    def load_chart_config(self):
        """Load chart configuration into UI controls."""
        # No configuration UI to load since it's now in the side panel
        pass

    def _resolve_fill_baseline(self, project, series_index, fill_base, fill_to_index, query, *, horizontal=False):
        """Resolve the second bound for a series' area fill: either the
        constant ``fill_base``, or -- when ``fill_to_index`` points at another
        series -- that series' curve interpolated onto this series' sampling
        grid, so the region *between* the two curves is filled.

        ``query`` is this series' independent-axis samples (x for a vertical
        fill, y for a horizontal one). Interpolation makes ``fill_between``/
        ``fill_betweenx`` well-defined even when the two series do not share
        a sampling grid; falls back to ``fill_base`` if the referenced
        series is missing or fails to resolve.
        """
        if fill_to_index is None or fill_to_index < 0 or fill_to_index == series_index or fill_to_index >= len(self.chart.data_series):
            return fill_base
        other = self.chart.data_series[fill_to_index]
        other_data = resolve_series_data(project, other)
        if other_data.error or other_data.x_data is None or len(other_data.x_data) == 0:
            return fill_base
        # Interpolate the other curve over its own independent axis (x when
        # vertical, y when horizontal). np.interp needs that axis increasing.
        if horizontal:
            xp = np.asarray(other_data.y_data, dtype=float)
            fp = np.asarray(other_data.x_data, dtype=float)
        else:
            xp = np.asarray(other_data.x_data, dtype=float)
            fp = np.asarray(other_data.y_data, dtype=float)
        order = np.argsort(xp)
        return np.interp(np.asarray(query, dtype=float), xp[order], fp[order])

    def _resolve_z_label(self, project, series) -> str:
        """Current display name of a series' Z (color) column, for the
        default colorbar label. Empty when it can't be resolved (missing
        dataset/column) so the colorbar just goes unlabeled rather than
        erroring."""
        from pandaplot.models.project.items.chart import resolve_series_column
        dataset = project.find_item(series.dataset_id) if project else None
        return resolve_series_column(dataset, series.style.z_column_id, series.style.z_column) or ""

    def update_chart(self):
        """Update the chart preview."""
        # Guard: Check if widget still exists
        if not isValid(self.chart_canvas):
            self.logger.debug("Chart canvas already deleted, skipping update")
            return

        try:
            # Remove the previous colorbar (a colormap/heatmap render adds
            # one on its own figure axes, which axes.clear() below doesn't
            # touch). This must happen BEFORE axes.clear(): clearing the
            # main axes detaches the mappable the colorbar refers to, which
            # makes Colorbar.remove() raise (its mappable's axes becomes
            # None) instead of cleanly removing the colorbar axes.
            if self._colorbar is not None:
                try:
                    self._colorbar.remove()
                except Exception:
                    self.logger.debug("Failed to remove stale colorbar", exc_info=True)
                self._colorbar = None

            # Clear the current plot
            self.chart_canvas.axes.clear()

            # Reset the main axes to a fresh full-figure 1x1 gridspec. A colorbar's
            # default use_gridspec=True *subdivides* the gridspec, and that
            # subdivision survives colorbar.remove() -- without this reset, each
            # re-render of a colormap/heatmap chart would shrink the axes further.
            #
            # axes2 (twinx(), sharing the same gridspec cell) must get the SAME
            # fresh spec unconditionally, even when no colorbar is drawn below --
            # otherwise it stays on its old subdivided spec while axes gets the
            # fresh one, and tight_layout() misaligns the two.
            from matplotlib.gridspec import GridSpec
            subplotspec = self.chart_canvas.axes.get_subplotspec()
            if subplotspec is not None:
                fresh_subplotspec = GridSpec(1, 1, figure=self.chart_canvas.fig)[0]
                self.chart_canvas.axes.set_subplotspec(fresh_subplotspec)
                if self.chart_canvas.axes2 is not None:
                    self.chart_canvas.axes2.set_subplotspec(fresh_subplotspec)

            fig_bg = self.chart.style.get("figure_background_color", "#ffffff")
            axes_bg = self.chart.style.get("axes_background_color", "#ffffff")
            self.chart_canvas.fig.set_facecolor(fig_bg if fig_bg is not None else "none")
            self.chart_canvas.axes.set_facecolor(axes_bg if axes_bg is not None else "none")

            # Set up (or tear down) the secondary Y axis depending on whether
            # any series is currently routed to it.
            needs_secondary = any(series.y_axis == "secondary" for series in self.chart.data_series)
            if needs_secondary:
                if self.chart_canvas.axes2 is None:
                    self.chart_canvas.axes2 = self.chart_canvas.axes.twinx()
                else:
                    self.chart_canvas.axes2.clear()
            elif self.chart_canvas.axes2 is not None:
                self.chart_canvas.axes2.remove()
                self.chart_canvas.axes2 = None
                self.chart_canvas.original_ylim2 = None

            series_errors = []
            colorbar_mappable = None
            colorbar_label = ""
            if not self.chart.data_series:
                self.dataset_label.setText("No Data Loaded")
            else:
                project = self.app_context.get_app_state().current_project

                # Resolve every series' data once, up front: a shared color
                # scale for Colormap/Heatmap series must be computed from
                # ALL of their z-data before any of them render, not just
                # whichever one happens to render first (see
                # docs/superpowers/specs/2026-08-21-shared-chart-level-color-map-design.md).
                resolved_data = [resolve_series_data(project, series) for series in self.chart.data_series]
                color_scale_auto = self.chart.config.get("color_scale_auto", True)
                # Only gather z-data when the scale is auto-computed: a
                # manual scale never reads it (see resolve_color_limits),
                # so skip the work entirely in that case. Each array is
                # built individually inside its own try/except so a single
                # series with non-numeric (e.g. text) Z data can't blow up
                # this up-front pre-pass and blank the whole chart -- that
                # series is simply left out of the combined scale here and
                # still gets its own per-series error below, when its
                # renderer runs in the main loop.
                z_arrays: list[np.ndarray] = []
                if color_scale_auto:
                    for series, data in zip(self.chart.data_series, resolved_data, strict=True):
                        if not SERIES_TYPE_SPECS[series.series_type].needs_z_column or data.error is not None:
                            continue
                        try:
                            z_arrays.append(np.asarray(data.z_data, dtype=float))
                        except (ValueError, TypeError):
                            continue
                combined_z = np.concatenate(z_arrays) if z_arrays else np.array([])
                color_limits = resolve_color_limits(
                    combined_z,
                    auto=color_scale_auto,
                    vmin=self.chart.config.get("color_vmin", 0.0),
                    vmax=self.chart.config.get("color_vmax", 1.0),
                )

                for i, (series, series_data) in enumerate(zip(self.chart.data_series, resolved_data, strict=True)):
                    # Route this series to its configured Y axis
                    target_axes = (self.chart_canvas.axes2
                                   if series.y_axis == "secondary" and self.chart_canvas.axes2 is not None
                                   else self.chart_canvas.axes)

                    x_data = series_data.x_data
                    y_data = series_data.y_data
                    x_err = series_data.x_err
                    y_err = series_data.y_err
                    x_err_minus = series_data.x_err_minus
                    y_err_minus = series_data.y_err_minus
                    error = series_data.error
                    if error:
                        series_errors.append(
                            f"{series.label or f'Series {i + 1}'}: {error}")
                        continue

                    alpha = series.alpha if series.visible else 0.3
                    series_type = series.series_type
                    style = series.style

                    # Draw error bars BEFORE the series/marker renderer:
                    # matplotlib draws artists in the order they're added
                    # to the axes when zorder is tied (neither call here
                    # sets one), so error bars drawn first land underneath
                    # the markers/line/bars instead of obscuring them.
                    error_bars = getattr(style, "error_bars", None)
                    if error_bars is not None:
                        xerr = build_error_array(x_err, x_err_minus, error_bars.error_direction, error_bars.error_symmetric)
                        yerr = build_error_array(y_err, y_err_minus, error_bars.error_direction, error_bars.error_symmetric)
                        if xerr is not None or yerr is not None:
                            err_color = error_bars.error_color or getattr(style, "color", "#1f77b4")
                            target_axes.errorbar(
                                x_data, y_data,
                                xerr=xerr,
                                yerr=yerr,
                                fmt="none",
                                ecolor=err_color,
                                elinewidth=getattr(style, "line_width", 2.0),
                                capsize=error_bars.error_cap_size,
                                alpha=alpha)

                    renderer = SERIES_RENDERERS[series_type]
                    mappable = renderer(
                        target_axes, series_data, style, series.label, alpha,
                        visible=series.visible,
                        extra={
                            "bins": self.chart.config.get("hist_bins", 20),
                            "resolve_fill_baseline": (
                                lambda query, *, horizontal, _i=i, _style=style: self._resolve_fill_baseline(
                                    project, _i, _style.fill_base, _style.fill_to_index, query,
                                    horizontal=horizontal)
                            ),
                            "colormap": self.chart.config.get("colormap", "viridis"),
                            "color_limits": color_limits,
                        },
                    )
                    if mappable is None and series_type in (SeriesType.COLORMAP, SeriesType.HEATMAP):
                        series_errors.append(f"{series.label or f'Series {i + 1}'}: no data to grid")
                        continue
                    if (mappable is not None and colorbar_mappable is None
                            and SERIES_TYPE_SPECS[series_type].needs_z_column
                            and self.chart.config.get("colorbar_show", True)):
                        colorbar_mappable = mappable
                        # None means "not customized" -- fall back to the Z
                        # column's name. Any other value (including "") is
                        # the user's explicit choice and is used as-is, so a
                        # deliberately cleared label renders with no label
                        # rather than reverting to the column name.
                        custom_label = self.chart.config.get("colorbar_label")
                        colorbar_label = (
                            custom_label if custom_label is not None
                            else self._resolve_z_label(project, series)
                        )

                if colorbar_mappable is not None:
                    self._colorbar = self.chart_canvas.fig.colorbar(
                        colorbar_mappable, ax=self.chart_canvas.axes)
                    if self.chart_canvas.axes2 is not None:
                        # fig.colorbar(..., ax=axes) subdivides *only* the
                        # primary axes' gridspec cell to make room -- axes2
                        # (a twinx() sharing that same cell) keeps its old,
                        # full-width subplotspec. Passing both axes to
                        # colorbar() doesn't help either: with two axes
                        # sharing a cell, tight_layout() flags the figure as
                        # "not compatible" and re-expands both back to full
                        # width, drawing the colorbar on top of the data.
                        # Explicitly handing axes2 the *same*, now-subdivided
                        # subplotspec keeps both axes shrunk together and
                        # keeps tight_layout happy across repeated
                        # resizes/re-renders.
                        self.chart_canvas.axes2.set_subplotspec(
                            self.chart_canvas.axes.get_subplotspec())
                    if colorbar_label:
                        self._colorbar.set_label(colorbar_label)

                # Plot fit data from chart.fit_data, routed to the same axis as
                # the data series it was fitted from (if that series uses the
                # secondary Y axis).
                for fit in self.chart.fit_data:
                    if fit.visible:
                        fit_axes = self.chart_canvas.axes
                        if self.chart_canvas.axes2 is not None:
                            for series in self.chart.data_series:
                                # Match series to the fit it came from: prefer
                                # stable column ids, fall back to names (both
                                # sides carry ids once assigned; renames keep
                                # the ids equal without touching either).
                                def _col_match(s_id, s_name, f_id, f_name):
                                    if s_id and f_id:
                                        return s_id == f_id
                                    return s_name == f_name
                                if (series.y_axis == "secondary"
                                        and series.dataset_id == fit.source_dataset_id
                                        and _col_match(series.x_column_id, series.x_column,
                                                       fit.source_x_column_id, fit.source_x_column)
                                        and _col_match(series.y_column_id, series.y_column,
                                                       fit.source_y_column_id, fit.source_y_column)):
                                    fit_axes = self.chart_canvas.axes2
                                    break

                        # Plot the fit line
                        style = fit.style
                        line_style_adapter = LineSeriesStyle(
                            color=style.color,
                            line_style=style.line_style,
                            line_width=style.line_width,
                            marker=MarkerStyle(marker_style="none"),
                            fill_enabled=False,
                        )
                        fit_series_data = SeriesData(
                            x_data=fit.x_data, y_data=fit.y_data,
                            x_err=None, y_err=None, x_err_minus=None, y_err_minus=None, error=None,
                        )
                        render_line_series(fit_axes, fit_series_data, line_style_adapter,
                                            fit.label, style.alpha, visible=fit.visible, extra={})

                        if (style.band_fill_enabled
                                and fit.confidence_lower is not None
                                and fit.confidence_upper is not None):
                            band_color = style.band_color or style.color
                            fit_axes.fill_between(
                                fit.x_data,
                                fit.confidence_lower,
                                fit.confidence_upper,
                                color=band_color,
                                alpha=style.band_fill_alpha)

            # Apply chart configuration
            config = self.chart.config

            # Resolve the target figure size *before* applying the title:
            # main_title_padding's points-to-fraction conversion needs the
            # height the figure is about to be set to, not whatever height
            # it happened to have from the previous render.
            cfg_manager = self.app_context.get_manager(ConfigManager)
            display_cfg = getattr(getattr(cfg_manager, "config", None), "chart_display", None)
            default_width = getattr(display_cfg, "default_width_cm", 20.0) if display_cfg else 20.0
            default_height = getattr(display_cfg, "default_height_cm", 15.0) if display_cfg else 15.0
            default_dpi = getattr(display_cfg, "dpi", 100) if display_cfg else 100
            width_cm, height_cm, dpi = resolve_chart_size(
                config.get("width_cm"), config.get("height_cm"), config.get("dpi"),
                default_width, default_height, default_dpi,
            )

            apply_chart_title(
                self.chart_canvas.axes,
                title=config.get("title", self.chart.name),
                subtitle=config.get("subtitle", ""),
                title_font_size=config.get("title_font_size", 14),
                subtitle_font_size=config.get("subtitle_font_size", 12),
                title_padding=config.get("title_padding", 6.0),
                main_title_padding=config.get("main_title_padding", 10.0),
                fig_height_inches=cm_to_inches(height_cm),
                title_bold=config.get("title_bold", True),
                title_italic=config.get("title_italic", False),
                subtitle_bold=config.get("subtitle_bold", False),
                subtitle_italic=config.get("subtitle_italic", False),
                title_color=config.get("title_color", "#000000"),
                subtitle_color=(
                    config.get("title_color", "#000000")
                    if config.get("subtitle_match_title_color", True)
                    else config.get("subtitle_color", "#000000")
                ),
                title_font_family=config.get("title_font_family", "DejaVu Sans"),
                subtitle_font_family=config.get("subtitle_font_family", "DejaVu Sans"),
            )

            chart_padding = config.get("chart_padding", 2.0)
            chart_padding_w = config.get("chart_padding_w", 2.0)
            chart_padding_h = config.get("chart_padding_h", 2.0)
            top_margin = config.get("top_margin", 1.0)
            self.chart_canvas.set_size(
                cm_to_inches(width_cm), cm_to_inches(height_cm),
                pad=chart_padding, w_pad=chart_padding_w, h_pad=chart_padding_h, top_margin=top_margin,
            )
            self.chart_canvas.set_dpi(
                dpi, pad=chart_padding, w_pad=chart_padding_w, h_pad=chart_padding_h, top_margin=top_margin,
            )

            x_label_color = config.get("x_label_color", "#000000")
            y_match_label = config.get("y_match_x_label_color", True)
            y_label_color = resolve_axis_color(
                "y", config.get("y_label_color", "#000000"), y_match_label, x_label_color)
            self.chart_canvas.axes.set_xlabel(
                config.get("x_label", ""), color=x_label_color,
                fontfamily=config.get("x_font_family", "DejaVu Sans"),
                fontweight="bold" if config.get("x_title_bold", False) else "normal",
                fontstyle="italic" if config.get("x_title_italic", False) else "normal",
                rotation=config.get("x_label_rotation", 0),
            )
            self.chart_canvas.axes.set_ylabel(
                config.get("y_label", ""), color=y_label_color,
                fontfamily=config.get("y_font_family", "DejaVu Sans"),
                fontweight="bold" if config.get("y_title_bold", False) else "normal",
                fontstyle="italic" if config.get("y_title_italic", False) else "normal",
                rotation=config.get("y_label_rotation", 90),
            )
            x_scale = config.get("x_scale", "linear")
            y_scale = config.get("y_scale", "linear")
            self.chart_canvas.axes.set_xscale(x_scale, **resolve_scale_kwargs(x_scale, config.get("x_log_base", 10.0)))
            self.chart_canvas.axes.set_yscale(y_scale, **resolve_scale_kwargs(y_scale, config.get("y_log_base", 10.0)))
            self.chart_canvas.axes.xaxis.label.set_size(config.get("x_font_size", 12))
            self.chart_canvas.axes.yaxis.label.set_size(config.get("y_font_size", 12))
            if config.get("y_side", "left") == "right":
                self.chart_canvas.axes.yaxis.tick_right()
                self.chart_canvas.axes.yaxis.set_label_position("right")
            else:
                self.chart_canvas.axes.yaxis.tick_left()
                self.chart_canvas.axes.yaxis.set_label_position("left")

            if self.chart_canvas.axes2 is not None:
                y2_match_label = config.get("y2_match_x_label_color", True)
                y2_label_color = resolve_axis_color(
                    "y2", config.get("y2_label_color", "#000000"), y2_match_label, x_label_color)
                self.chart_canvas.axes2.set_ylabel(
                    config.get("y2_label", ""), color=y2_label_color,
                    fontfamily=config.get("y2_font_family", "DejaVu Sans"),
                    fontweight="bold" if config.get("y2_title_bold", False) else "normal",
                    fontstyle="italic" if config.get("y2_title_italic", False) else "normal",
                    rotation=config.get("y2_label_rotation", 90),
                )
                y2_scale = config.get("y2_scale", "linear")
                self.chart_canvas.axes2.set_yscale(
                    y2_scale, **resolve_scale_kwargs(y2_scale, config.get("y2_log_base", 10.0)))
                self.chart_canvas.axes2.yaxis.label.set_size(config.get("y2_font_size", 12))
                if config.get("y2_side", "right") == "left":
                    self.chart_canvas.axes2.yaxis.tick_left()
                    self.chart_canvas.axes2.yaxis.set_label_position("left")
                else:
                    self.chart_canvas.axes2.yaxis.tick_right()
                    self.chart_canvas.axes2.yaxis.set_label_position("right")

                if not config.get("y2_auto_limits", True):
                    self.chart_canvas.axes2.set_ylim(
                        config.get("y2_min", 0.0), config.get("y2_max", 1.0))

                apply_axis_ticks(
                    self.chart_canvas.axes2.yaxis,
                    config.get("y2_tick_mode", "auto"), config.get("y2_tick_count", 5),
                    config.get("y2_tick_step", 1.0), config.get("y2_tick_format", "auto"),
                    config.get("y2_tick_format_custom", ""),
                    direction=config.get("y2_tick_direction", "out"),
                    minor_enabled=config.get("y2_minor_ticks", False),
                    minor_direction=config.get("y2_minor_tick_direction", "out"),
                    major_color=resolve_axis_color(
                        "y2", config.get("y2_major_tick_color", "#000000"),
                        config.get("y2_match_x_colors", True),
                        config.get("x_major_tick_color", "#000000")),
                    minor_color=resolve_axis_color(
                        "y2", config.get("y2_minor_tick_color", "#000000"),
                        config.get("y2_match_x_colors", True),
                        config.get("x_minor_tick_color", "#000000")),
                    labelcolor=resolve_axis_color(
                        "y2", config.get("y2_tick_label_color", "#000000"),
                        config.get("y2_match_x_colors", True),
                        config.get("x_tick_label_color", "#000000")))

                apply_tick_label_font(
                    self.chart_canvas.axes2.yaxis,
                    config.get("y2_tick_label_font_size", 10),
                    config.get("y2_tick_label_font_family", "DejaVu Sans"),
                    bold=config.get("y2_tick_label_bold", False),
                    italic=config.get("y2_tick_label_italic", False),
                    rotation=config.get("y2_tick_label_rotation", 0),
                )

                if config.get("show_grid_y2", True):
                    self.chart_canvas.axes2.grid(visible=True, axis="y", alpha=config.get("grid_alpha", 0.3))
                else:
                    self.chart_canvas.axes2.grid(visible=False, axis="y")
                if config.get("y2_show_minor_grid", False):
                    self.chart_canvas.axes2.grid(
                        visible=True, axis="y", which="minor", alpha=config.get("minor_grid_alpha", 0.15))
                else:
                    self.chart_canvas.axes2.grid(visible=False, axis="y", which="minor")

            if not config.get("x_auto_limits", True):
                self.chart_canvas.axes.set_xlim(config.get("x_min", 0.0), config.get("x_max", 1.0))
            if not config.get("y_auto_limits", True):
                self.chart_canvas.axes.set_ylim(config.get("y_min", 0.0), config.get("y_max", 1.0))

            apply_axis_ticks(
                self.chart_canvas.axes.xaxis,
                config.get("x_tick_mode", "auto"), config.get("x_tick_count", 5),
                config.get("x_tick_step", 1.0), config.get("x_tick_format", "auto"),
                config.get("x_tick_format_custom", ""),
                direction=config.get("x_tick_direction", "out"),
                minor_enabled=config.get("x_minor_ticks", False),
                minor_direction=config.get("x_minor_tick_direction", "out"),
                major_color=config.get("x_major_tick_color", "#000000"),
                minor_color=config.get("x_minor_tick_color", "#000000"),
                labelcolor=config.get("x_tick_label_color", "#000000"))
            apply_tick_label_font(
                self.chart_canvas.axes.xaxis,
                config.get("x_tick_label_font_size", 10),
                config.get("x_tick_label_font_family", "DejaVu Sans"),
                bold=config.get("x_tick_label_bold", False),
                italic=config.get("x_tick_label_italic", False),
                rotation=config.get("x_tick_label_rotation", 0),
            )
            apply_axis_ticks(
                self.chart_canvas.axes.yaxis,
                config.get("y_tick_mode", "auto"), config.get("y_tick_count", 5),
                config.get("y_tick_step", 1.0), config.get("y_tick_format", "auto"),
                config.get("y_tick_format_custom", ""),
                direction=config.get("y_tick_direction", "out"),
                minor_enabled=config.get("y_minor_ticks", False),
                minor_direction=config.get("y_minor_tick_direction", "out"),
                major_color=resolve_axis_color(
                    "y", config.get("y_major_tick_color", "#000000"),
                    config.get("y_match_x_colors", True),
                    config.get("x_major_tick_color", "#000000")),
                minor_color=resolve_axis_color(
                    "y", config.get("y_minor_tick_color", "#000000"),
                    config.get("y_match_x_colors", True),
                    config.get("x_minor_tick_color", "#000000")),
                labelcolor=resolve_axis_color(
                    "y", config.get("y_tick_label_color", "#000000"),
                    config.get("y_match_x_colors", True),
                    config.get("x_tick_label_color", "#000000")))
            apply_tick_label_font(
                self.chart_canvas.axes.yaxis,
                config.get("y_tick_label_font_size", 10),
                config.get("y_tick_label_font_family", "DejaVu Sans"),
                bold=config.get("y_tick_label_bold", False),
                italic=config.get("y_tick_label_italic", False),
                rotation=config.get("y_tick_label_rotation", 0),
            )

            apply_spine_colors(
                self.chart_canvas.axes, self.chart_canvas.axes2,
                config.get("x_spine_color", "#000000"),
                resolve_axis_color(
                    "y", config.get("y_spine_color", "#000000"),
                    config.get("y_match_x_colors", True),
                    config.get("x_spine_color", "#000000")),
                resolve_axis_color(
                    "y2", config.get("y2_spine_color", "#000000"),
                    config.get("y2_match_x_colors", True),
                    config.get("x_spine_color", "#000000")))

            grid_alpha = config.get("grid_alpha", 0.3)
            minor_grid_alpha = config.get("minor_grid_alpha", 0.15)
            if config.get("show_grid_x", True):
                self.chart_canvas.axes.grid(visible=True, axis="x", alpha=grid_alpha)
            else:
                self.chart_canvas.axes.grid(visible=False, axis="x")
            if config.get("x_show_minor_grid", False):
                self.chart_canvas.axes.grid(visible=True, axis="x", which="minor", alpha=minor_grid_alpha)
            else:
                self.chart_canvas.axes.grid(visible=False, axis="x", which="minor")
            if config.get("show_grid_y", True):
                self.chart_canvas.axes.grid(visible=True, axis="y", alpha=grid_alpha)
            else:
                self.chart_canvas.axes.grid(visible=False, axis="y")
            if config.get("y_show_minor_grid", False):
                self.chart_canvas.axes.grid(visible=True, axis="y", which="minor", alpha=minor_grid_alpha)
            else:
                self.chart_canvas.axes.grid(visible=False, axis="y", which="minor")

            legend = None
            placement_kwargs = {}
            if config.get("show_legend", True) and (self.chart.data_series or self.chart.fit_data):
                # Combine handles/labels from both axes since twinx() legends
                # are independent by default.
                handles, labels = self.chart_canvas.axes.get_legend_handles_labels()
                if self.chart_canvas.axes2 is not None:
                    handles2, labels2 = self.chart_canvas.axes2.get_legend_handles_labels()
                    handles += handles2
                    labels += labels2
                # Skip drawing the legend when there are no handles to show
                # (e.g. a chart with only an unlabeled Heatmap series, or any
                # chart where nothing has a label) -- matplotlib would
                # otherwise draw an empty framed legend box over the plot.
                if handles:
                    placement_kwargs = resolve_legend_placement(
                        config.get("legend_position", "upper right"),
                        config.get("legend_custom_x", 1.02),
                        config.get("legend_custom_y", 0.5),
                        config.get("legend_custom_anchor", "center left"),
                    )
                    legend = build_legend(
                        self.chart_canvas.axes, handles, labels,
                        config.get("legend_font_family", "DejaVu Sans"),
                        config.get("legend_font_size", 10),
                        config.get("legend_bg_color", "#ffffff"),
                        show_frame=config.get("legend_show_frame", True),
                        columns=config.get("legend_columns", 1),
                        bg_alpha=config.get("legend_bg_alpha", 1.0),
                        placement_kwargs=placement_kwargs,
                    )

            tight_layout_kwargs = dict(
                pad=config.get("chart_padding", 2.0),
                w_pad=config.get("chart_padding_w", 2.0),
                h_pad=config.get("chart_padding_h", 2.0),
                rect=(0, 0, 1, config.get("top_margin", 1.0)),
            )
            # Reserve room for the secondary axis label/ticks so they aren't
            # clipped at the right edge of the figure.
            apply_layout_with_legend(
                self.chart_canvas.fig, tight_layout_kwargs,
                legend_placed_outside=(
                    legend is not None and placement_kwargs.get("bbox_to_anchor") is not None
                ),
            )

            # Store original limits for zoom reset functionality
            self.chart_canvas.store_original_limits()

            # Refresh canvas
            self.chart_canvas.draw()

            if series_errors:
                self.update_status("Skipped: " + "; ".join(series_errors))
            else:
                self.update_status("Ready")

        except Exception as e:
            self.logger.exception("Error updating chart")
            self.update_status(f"Chart error: {str(e)}")

    def reset_chart(self):
        """Reset chart to default configuration."""
        self.chart._init_default_config()
        self.update_chart()
        self.update_status("Reset to defaults ✓")

        # Reset status after 2 seconds
        QTimer.singleShot(2000, lambda: self.update_status("Ready"))

    def update_status(self, status: str):
        """Update the status label."""
        # Guard: Check if widget still exists
        if not isValid(self.status_label):
            return

        self.status_label.setText(status)
        self._update_status_label_style()

    def _apply_initial_fit_size(self):
        """Size a freshly opened chart to fill the visible preview panel.

        Runs once, shortly after construction, once the scroll area has a
        real viewport size to measure. Has no effect if the widget was
        already closed or the panel hasn't been laid out yet, or if this
        chart already has a per-chart width/height saved in its config
        (in which case that saved size takes precedence and must not be
        overwritten by the fit-to-panel heuristic).
        """
        if not isValid(self.canvas_scroll) or not isValid(self.chart_canvas):
            return

        if self.chart.config.get("width_cm") is not None or self.chart.config.get("height_cm") is not None:
            return

        viewport = self.canvas_scroll.viewport()
        width_px = viewport.width()
        height_px = viewport.height()
        if width_px <= 0 or height_px <= 0:
            return

        width_cm, height_cm = fit_size_cm(
            width_px, height_px, self.chart_canvas.fig.dpi,
            min_width_cm=MIN_CHART_WIDTH_CM, max_width_cm=MAX_CHART_WIDTH_CM,
            min_height_cm=MIN_CHART_HEIGHT_CM, max_height_cm=MAX_CHART_HEIGHT_CM)

        self.chart.config["width_cm"] = width_cm
        self.chart.config["height_cm"] = height_cm
        self.update_chart()

    def _on_refresh(self):
        """Reload data from the datasets and redraw the chart on demand."""
        self.refresh_chart()
        self.update_status("Refreshed ✓")

        # Reset status after 2 seconds
        QTimer.singleShot(2000, lambda: self.update_status("Ready"))

    def _on_reset_zoom(self):
        """Handle reset zoom action."""
        if hasattr(self, "chart_canvas"):
            try:
                self.chart_canvas.reset_zoom()
                self.update_status("Zoom reset")
            except Exception as e:
                self.update_status(f"Zoom reset error: {str(e)}")

            # Reset status after 2 seconds
            QTimer.singleShot(2000, lambda: self.update_status("Ready"))

    def get_chart(self) -> Chart:
        """Get the current chart object."""
        return self.chart

    def refresh_chart(self):
        """Refresh the chart preview when configuration changes from external sources."""
        # Guard: Check if widget still exists
        if not isValid(self.chart_canvas):
            return

        self.update_chart()

        # Update dataset label in status
        datasets = self.chart.get_all_datasets()
        dataset_text = f"Datasets: {', '.join(datasets)}" if datasets else "Sample Data"
        self.dataset_label.setText(dataset_text)
