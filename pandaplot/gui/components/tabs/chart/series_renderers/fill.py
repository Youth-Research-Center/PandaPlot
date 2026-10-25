"""Area fill under/between a series, shared by the line and scatter renderers."""
import numpy as np

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.models.chart.series_style.fill import FillStyleFields


def fill_range_mask(style: FillStyleFields, point_count: int) -> np.ndarray:
    """Build a boolean mask covering the union of the configured point ranges.

    The ranges use inclusive, zero-based point indexes. Out-of-bounds indexes
    are clamped to the available points, reversed ranges are ignored, and
    touching or overlapping ranges are coalesced. An empty section list means
    the whole series.

    Args:
        style: Fill style with the configured point sections.
        point_count: Number of data points in the series.

    Returns:
        Boolean array with one entry per point, true for points in a section.
    """
    mask = np.zeros(point_count, dtype=bool)
    if not style.fill_sections:
        mask[:] = True
        return mask

    last = max(point_count - 1, 0)
    sections = sorted(
        (min(max(int(start), 0), last), last if int(end) < 0 else min(int(end), last))
        for start, end in style.fill_sections
    )
    merged: list[tuple[int, int]] = []
    for start, end in sections:
        if end < start:
            continue
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    for start, end in merged:
        mask[start:end + 1] = True
    return mask


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

    where = fill_range_mask(style, len(x)) if style.fill_range_enabled else None

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
