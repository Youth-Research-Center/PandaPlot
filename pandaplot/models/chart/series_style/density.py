"""Style fields for a "density" series -- a kernel density estimate (KDE)
curve of one numeric column, drawn by render_density_series()
(pandaplot/gui/components/tabs/chart/series_renderers/density.py).

Deliberately NOT built on FillStyleFields: a density curve only ever fills
down to y=0 underneath itself, so the shared fill's orientation/baseline/
fill-to-another-series/partial-range fields have nothing to mean here.
Just an on/off switch and an opacity, with the fill always drawn in the
line's own color.
"""
import math
from dataclasses import dataclass

from pandaplot.models.chart.series_style.base import SeriesStyleBase

MAX_BANDWIDTH = 5.0
# The style tab's bandwidth spin box shows 2 decimals, so anything that rounds
# to 0.00 would display as "Auto" while still being used as a real bandwidth.
_MIN_BANDWIDTH = 0.005


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

    def __post_init__(self) -> None:
        """Clamp `bandwidth` to what the style tab's spin box can show.

        A hand-edited or imported project could carry a NaN, negative,
        sub-resolution or out-of-range value; it is normalized here so the
        editor and the renderer always agree on the bandwidth in use.
        """
        if math.isnan(self.bandwidth) or self.bandwidth < _MIN_BANDWIDTH:
            self.bandwidth = 0.0
        else:
            self.bandwidth = min(self.bandwidth, MAX_BANDWIDTH)
