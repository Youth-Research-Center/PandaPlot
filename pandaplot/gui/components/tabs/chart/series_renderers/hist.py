"""Renders a "hist" series -- color only, bin count comes from the
chart-level config (not per-series), passed via extra["bins"].

extra["hist_density"] (ChartTypeSpec.hist_density, absent == False)
normalizes the bars to unit area so they share a Y scale with a KDE curve
on a Density chart."""
from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.models.chart.series_style import HistSeriesStyle


def render_hist_series(axes, series_data: SeriesData, style: HistSeriesStyle,
                        label: str, alpha: float, *, visible: bool, extra: dict) -> None:
    axes.hist(series_data.y_data,
              bins=extra["bins"],
              density=extra.get("hist_density", False),
              color=style.color,
              label=label,
              alpha=alpha)
