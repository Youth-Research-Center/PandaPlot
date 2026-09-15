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
        # bar_label() places one label per bar, above (or below, for a
        # negative height) it -- unlike line/scatter's point-by-point
        # annotate() loop (series_renderers/value_labels.py), matplotlib
        # already positions these correctly from the BarContainer itself.
        # No mode/arrow/offset here (see BarSeriesStyle) -- only text/
        # background color+alpha, forwarded straight through as bar_label()
        # kwargs (it passes **kwargs on to each per-bar Annotation).
        bbox = (
            {"boxstyle": "round,pad=0.2", "facecolor": style.value_label_bg_color,
             "edgecolor": "none", "alpha": style.value_label_bg_alpha * alpha}
            if style.value_label_bg_color else None
        )
        axes.bar_label(bars, fmt="%.3g", fontsize=8,
                        color=style.value_label_text_color or style.color,
                        bbox=bbox,
                        alpha=alpha)
