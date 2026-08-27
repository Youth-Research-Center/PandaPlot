"""Renders a "bar" series -- color only."""
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.models.chart.series_style import BarSeriesStyle


def render_bar_series(axes, series_data: SeriesData, style: BarSeriesStyle,
                       label: str, alpha: float, *, visible: bool, extra: dict) -> None:
    axes.bar(series_data.x_data, series_data.y_data,
             color=style.color,
             label=label,
             alpha=alpha)
