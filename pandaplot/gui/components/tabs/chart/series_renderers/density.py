"""Renders a "density" series: a Gaussian kernel density estimate (KDE) of
the series' values column (series_data.y_data -- the "values" role maps
onto y_column_id, exactly as for Hist), drawn as a smooth curve with an
optional fill down to y=0.

Returns None (not the curve) when no density can be estimated, so
chart_editor.py reports a per-series "no plottable data" message instead
of one bad series blanking the whole chart -- the same contract
render_surface_series has (see SERIES_RENDERERS_REPORTING_NO_DATA).
gaussian_kde fails on fewer than 2 finite points and on constant data
(zero variance makes its covariance matrix singular), both of which are
easy to reach just by picking a column.
"""
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.style_maps import LINESTYLE_MAP
from pandaplot.models.chart.series_style import DensitySeriesStyle

# Evaluation-grid resolution: enough for a visually smooth curve at any
# realistic chart size, cheap to evaluate even for large datasets.
_GRID_POINTS = 512
# Pad the evaluation grid past the data's min/max by this fraction of the
# data range on each side, so the curve visibly tails off toward zero
# instead of being cut off mid-slope at the outermost data points.
_GRID_PADDING_FRACTION = 0.1


def compute_density_curve(values, bandwidth: float) -> tuple[np.ndarray, np.ndarray] | None:
    """Evaluate a Gaussian KDE of `values` on an evenly spaced grid.

    Args:
        values: The raw sample; non-numeric entries and NaN/inf are dropped.
        bandwidth: Scalar bandwidth factor passed to gaussian_kde as
            `bw_method`; 0 or less means automatic (Scott's rule).

    Returns:
        (grid, density) arrays, or None when there's too little data, or too
        little variance, to estimate a density from.
    """
    sample = pd.to_numeric(pd.Series(values, dtype=object), errors="coerce").to_numpy(dtype=float)
    sample = sample[np.isfinite(sample)]
    if sample.size < 2 or np.ptp(sample) == 0:
        return None
    try:
        kde = gaussian_kde(sample, bw_method=bandwidth if bandwidth > 0 else None)
    except (np.linalg.LinAlgError, ValueError):
        return None
    low, high = float(sample.min()), float(sample.max())
    pad = (high - low) * _GRID_PADDING_FRACTION
    grid = np.linspace(low - pad, high + pad, _GRID_POINTS)
    density = kde(grid)
    if not np.all(np.isfinite(density)):
        return None
    return grid, density


def render_density_series(axes, series_data: SeriesData, style: DensitySeriesStyle,
                           label: str, alpha: float, *, visible: bool, extra: dict):
    curve = compute_density_curve(series_data.y_data, style.bandwidth)
    if curve is None:
        return None
    grid, density = curve
    (line,) = axes.plot(grid, density,
                        color=style.color,
                        linewidth=style.line_width,
                        linestyle=LINESTYLE_MAP.get(style.line_style, "-"),
                        label=label,
                        alpha=alpha)
    if style.fill_enabled:
        # Same hidden-series dimming render_area_fill applies to a Line fill.
        fill_alpha = style.fill_alpha if visible else 0.3 * style.fill_alpha
        axes.fill_between(grid, density, 0, color=style.color, alpha=fill_alpha)
    return line
