"""Style fields for a "density" series -- a kernel density estimate (KDE)
curve of one numeric column, drawn by render_density_series()
(pandaplot/gui/components/tabs/chart/series_renderers/density.py).

Deliberately NOT built on FillStyleFields: a density curve only ever fills
down to y=0 underneath itself, so the shared fill's orientation/baseline/
fill-to-another-series/partial-range fields have nothing to mean here.
Just an on/off switch and an opacity, with the fill always drawn in the
line's own color.
"""
from dataclasses import dataclass

from pandaplot.models.chart.series_style.base import SeriesStyleBase


@dataclass
class DensitySeriesStyle(SeriesStyleBase):
    color: str = "#1f77b4"
    # Same string values as LineSeriesStyle.line_style (see style_maps.LINESTYLE_MAP).
    line_style: str = "solid"
    line_width: float = 2.0
    fill_enabled: bool = False
    fill_alpha: float = 0.3
    # scipy.stats.gaussian_kde's `bw_method` as a scalar factor (the kernel's
    # std-dev is this times the data's std-dev). 0.0 is the "automatic"
    # sentinel -- bw_method=None, i.e. Scott's rule -- since a literal zero
    # bandwidth is meaningless (a sum of Dirac spikes).
    bandwidth: float = 0.0
