"""Style fields for a "bar3d" series -- one 3-D box per (x, y) sample,
rising from z=0 to that sample's z, drawn with ``Axes3D.bar3d``.

``bar_width``/``bar_depth`` are *fractions* of the median spacing between
the data's distinct x (resp. y) values, not absolute data units -- an
absolute default can't work across datasets whose x values are seconds
apart in one file and thousands apart in another. See
chart_3d.resolve_bar_footprint, which converts them."""
from dataclasses import dataclass

from pandaplot.models.chart.series_style.base import SeriesStyleBase


@dataclass
class Bar3DSeriesStyle(SeriesStyleBase):
    color: str = "#1f77b4"
    z_column_id: str = ""
    z_column: str = ""
    bar_width: float = 0.8
    bar_depth: float = 0.8
    shade: bool = True
