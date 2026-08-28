"""Style fields for a "line3d" series -- a polyline through (x, y, z)
drawn with ``Axes3D.plot``. The 3-D counterpart of LineSeriesStyle, minus
the area-fill fields (``fill_between`` has no mplot3d equivalent) and the
error-bar fields (mplot3d has no errorbar at all -- see
SeriesTypeSpec.supports_error_bars, False for every 3-D type)."""
from dataclasses import dataclass, field

from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style.base import SeriesStyleBase


@dataclass
class Line3DSeriesStyle(SeriesStyleBase):
    color: str = "#1f77b4"
    line_style: str = "solid"
    line_width: float = 2.0
    z_column_id: str = ""
    z_column: str = ""
    marker: MarkerStyle = field(default_factory=MarkerStyle)
