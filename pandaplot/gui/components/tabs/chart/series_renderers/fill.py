"""Area fill under/between a series, shared by the line and scatter renderers."""
import numpy as np

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.models.chart.series_style.fill import FillStyleFields


def fill_range_bounds(style: FillStyleFields, point_count: int) -> tuple[int, int]:
    """Resolve a style's data-point range to inclusive, clamped 0-based (start, end).

    Args:
        style: A style carrying the shared fill fields.
        point_count: Number of points in the series.

    Returns:
        The first and last point index to fill. fill_range_end == -1 means the
        last point; a bound past the data is clamped to it.
    """
    last = max(point_count - 1, 0)
    start = min(max(style.fill_range_start, 0), last)
    end = last if style.fill_range_end < 0 else min(style.fill_range_end, last)
    return start, end


def render_area_fill(axes, series_data: SeriesData, style: FillStyleFields, *, color: str, visible: bool, extra: dict,
                     sort_by_independent: bool = False) -> None:
    """Fill between a series and its baseline (or another series).

    Args:
        axes: Matplotlib axes to draw on.
        series_data: The series' resolved x/y data.
        style: A style carrying the shared fill fields; must have fill_enabled.
        color: Fill color (already resolved from the "match line" default).
        visible: Whether the series is visible; a hidden series gets a fainter fill.
        extra: Renderer extras; must carry ``resolve_fill_baseline``.
        sort_by_independent: Sort by the swept axis before filling. ``fill_between``
            joins points in the order given, so an unordered series (scatter)
            would otherwise draw a zig-zag polygon.
    """
    horizontal = style.fill_orientation == "horizontal"
    x = np.asarray(series_data.x_data)
    y = np.asarray(series_data.y_data)
    independent = y if horizontal else x

    where = None
    if style.fill_range_enabled:
        start, end = fill_range_bounds(style, len(x))
        rows = np.arange(len(x))
        where = (rows >= start) & (rows <= end)

    baseline = extra["resolve_fill_baseline"](independent, horizontal=horizontal)
    if sort_by_independent:
        baseline = np.broadcast_to(np.asarray(baseline), independent.shape)
        order = np.argsort(independent, kind="stable")
        x, y, baseline = x[order], y[order], baseline[order]
        if where is not None:
            where = where[order]

    alpha = style.fill_alpha if visible else 0.3 * style.fill_alpha
    if horizontal:
        axes.fill_betweenx(y, x, baseline, where=where, color=color, alpha=alpha)
    else:
        axes.fill_between(x, y, baseline, where=where, color=color, alpha=alpha)
