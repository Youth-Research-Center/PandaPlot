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
import pandas as pd


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
) -> None:
    """Label each (x, y) point per `mode` ("x", "y", or "xy"), offset from
    the point by (offset_x, offset_y) points.

    `alpha` is the renderer's already-computed effective alpha (series.alpha,
    faded further when the series is hidden -- see chart_editor.py's
    `alpha = series.alpha if series.visible else 0.3`), applied to the label
    text/arrow/background so a faded-out or hidden series' labels fade with
    it instead of staying fully opaque.

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
    for x, y in zip(x_data, y_data, strict=True):
        if pd.isna(x) or pd.isna(y):
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
