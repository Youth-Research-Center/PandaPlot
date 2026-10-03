"""Renders a "hist" series -- color only, bin count comes from the
chart-level config (not per-series), passed via extra["bins"].

extra["hist_density"] (ChartTypeSpec.hist_density, absent == False)
normalizes the bars to unit area so they share a Y scale with a KDE curve
on a Density chart."""
import numpy as np
import pandas as pd

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.models.chart.series_style import HistSeriesStyle


def finite_numeric_values(values) -> np.ndarray:
    """`values` as a float array with non-numeric and non-finite cells dropped."""
    numeric = pd.to_numeric(pd.Series(values, dtype=object), errors="coerce").to_numpy(dtype=float)
    return numeric[np.isfinite(numeric)]


def render_hist_series(axes, series_data: SeriesData, style: HistSeriesStyle,
                        label: str, alpha: float, *, visible: bool, extra: dict):
    """Draw the histogram and return its bar container, or None when no
    finite numeric values remain (HIST is in SERIES_RENDERERS_REPORTING_NO_DATA)."""
    values = finite_numeric_values(series_data.y_data)
    if values.size == 0:
        return None
    _counts, _edges, patches = axes.hist(values,
                                         bins=extra["bins"],
                                         density=extra.get("hist_density", False),
                                         color=style.color,
                                         label=label,
                                         alpha=alpha)
    return patches
