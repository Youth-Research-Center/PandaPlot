"""Shared helper for annotating each rendered point with its numeric value
(#125), used by the line/scatter renderers -- BarSeriesStyle's own
render_bar_series() uses matplotlib's bar_label() on the BarContainer
axes.bar() returns instead, since that already places one label per bar
correctly positioned above/below it.

Gated by SeriesStyleBase.show_value_labels (declared on LineSeriesStyle/
ScatterSeriesStyle/BarSeriesStyle only) and SeriesTypeSpec.supports_value_labels.

Line/Scatter also support the mode/arrow/offset/color fields below (a value
picker, an optional leader line, an offset, and text/background styling) --
Bar does not, since bar_label() has only a single scalar height per bar and
already positions the label without any offset/arrow concept.
"""
import numpy as np
import pandas as pd
from numpy.typing import ArrayLike
from pandas.api.types import is_datetime64_any_dtype, is_numeric_dtype

from pandaplot.models.chart.value_label_subset import ValueLabelSubset


def _format_number(value) -> str:
    try:
        return f"{value:.3g}"
    except (TypeError, ValueError):
        return str(value)


def _format_label(x: float, y: float, mode: str) -> str:
    if mode == "x":
        return _format_number(x)
    if mode == "xy":
        return f"{_format_number(x)}, {_format_number(y)}"
    return _format_number(y)


def _drawable_mask(x_data: ArrayLike, y: pd.Series) -> np.ndarray:
    """Which points can be drawn: neither x nor y is missing (NaN/NaT)."""
    return pd.notna(np.asarray(x_data)) & y.notna().to_numpy()


def _as_series(y_data: ArrayLike) -> pd.Series:
    """Y data as a Series, keeping datetime dtypes (tz-aware included) intact; anything else non-numeric is coerced."""
    y = pd.Series(y_data).reset_index(drop=True)
    if not (is_numeric_dtype(y) or is_datetime64_any_dtype(y)):
        y = pd.to_numeric(y, errors="coerce")
    return y


def resolve_label_indices(x_data: ArrayLike, y_data: ArrayLike, *, subset_mode: str = ValueLabelSubset.ALL) -> set[int]:
    """Decide which points of a series should get a value label.

    Minimum and maximum are by Y value, over the whole series. Only points
    that can actually be drawn are considered: a point whose x or y is
    missing (NaN/NaT), or whose y is infinite, is never chosen. If several
    points tie, the first one is used.

    Args:
        x_data: X values of the series, one per point.
        y_data: Y values of the series, one per point.
        subset_mode: A ValueLabelSubset or its string value. An unknown
            value is treated as ALL.

    Returns:
        The set of 0-based point positions that should be labeled.
    """
    mode = ValueLabelSubset.coerce(subset_mode)
    y = _as_series(y_data)
    if mode is ValueLabelSubset.ALL:
        return set(np.flatnonzero(_drawable_mask(x_data, y)).tolist())

    drawable = _drawable_mask(x_data, y)
    if is_numeric_dtype(y):
        drawable &= np.isfinite(y.to_numpy(dtype=float, na_value=np.nan))
    candidates = y[drawable]
    if candidates.empty:
        return set()

    indices = set()
    if mode in (ValueLabelSubset.EXTREMES, ValueLabelSubset.MIN):
        indices.add(int(candidates.idxmin()))
    if mode in (ValueLabelSubset.EXTREMES, ValueLabelSubset.MAX):
        indices.add(int(candidates.idxmax()))
    return indices


def annotate_point_labels(
    axes, x_data, y_data, *,
    fontsize: float = 8.0,
    mode: str = "y",
    show_arrow: bool = False,
    offset_x: float = 0.0,
    offset_y: float = 6.0,
    text_color: str = "",
    bg_color: str = "",
    bg_alpha: float = 1.0,
    alpha: float = 1.0,
    subset_mode: str = ValueLabelSubset.ALL,
) -> None:
    """Label each (x, y) point per `mode` ("x", "y", or "xy"), offset from
    the point by (offset_x, offset_y) points.

    `alpha` is the renderer's already-computed effective alpha (series.alpha,
    faded further when the series is hidden -- see chart_editor.py's
    `alpha = series.alpha if series.visible else 0.3`), applied to the label
    text/arrow/background so a faded-out or hidden series' labels fade with
    it instead of staying fully opaque.

    `subset_mode` chooses which points are labeled; see
    resolve_label_indices(). The default labels every drawable point.

    Intended for the small datasets the issue this implements (#125) calls
    out (lab reports, a handful of points) -- no cap on point count, since a
    series with too many points to usefully label this way is one a user
    wouldn't turn this on for in the first place.
    """
    arrowprops = {"arrowstyle": "-", "alpha": alpha} if show_arrow else None
    bbox = (
        {"boxstyle": "round,pad=0.2", "facecolor": bg_color, "edgecolor": "none", "alpha": bg_alpha * alpha}
        if bg_color else None
    )
    label_indices = resolve_label_indices(x_data, y_data, subset_mode=subset_mode)
    for index, (x, y) in enumerate(zip(x_data, y_data, strict=True)):
        if index not in label_indices:
            continue
        axes.annotate(
            _format_label(x, y, mode),
            (x, y),
            textcoords="offset points",
            xytext=(offset_x, offset_y),
            ha="center",
            fontsize=fontsize,
            color=text_color or None,
            arrowprops=arrowprops,
            bbox=bbox,
            alpha=alpha,
        )
