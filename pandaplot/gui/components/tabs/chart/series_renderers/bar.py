"""Renders a "bar" series -- color only."""
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.models.chart.series_style import BarSeriesStyle


def render_bar_series(axes, series_data: SeriesData, style: BarSeriesStyle,
                       label: str, alpha: float, *, visible: bool, extra: dict) -> None:
    bars = axes.bar(series_data.x_data, series_data.y_data,
                     color=style.color,
                     label=label,
                     alpha=alpha)
    if style.show_value_labels:
        label_bars(axes, bars, style, alpha, label_type="edge")


def label_bars(axes, bars, style: BarSeriesStyle, alpha: float, *, label_type: str) -> None:
    """Annotate each bar in `bars` (a BarContainer) with its value.

    bar_label() places one label per bar -- unlike line/scatter's
    point-by-point annotate() loop (series_renderers/value_labels.py),
    matplotlib already positions these correctly from the BarContainer
    itself. No mode/arrow/offset here (see BarSeriesStyle) -- only text/
    background color+alpha, forwarded straight through as bar_label() kwargs
    (it passes **kwargs on to each per-bar Annotation).

    Args:
        axes: The axes `bars` was drawn on.
        bars: The BarContainer returned by `axes.bar()`.
        style: The series' style, for the label colors.
        alpha: The series' effective opacity.
        label_type: bar_label()'s placement -- "edge" (above a bar, or
            below a negative one) for a plain bar, "center" for a stacked
            segment, where "edge" would label the running stack total
            instead of the segment's own value.
    """
    bbox = (
        {"boxstyle": "round,pad=0.2", "facecolor": style.value_label_bg_color,
         "edgecolor": "none", "alpha": style.value_label_bg_alpha * alpha}
        if style.value_label_bg_color else None
    )
    axes.bar_label(bars, fmt="%.3g", fontsize=8,
                    label_type=label_type,
                    color=style.value_label_text_color or style.color,
                    bbox=bbox,
                    alpha=alpha)
