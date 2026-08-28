"""Style fields for a "scatter3d" series -- a 3-D point cloud drawn with
``Axes3D.scatter(x, y, z)``. Marker fields only (marker_mode is
"required", like the 2-D scatter it mirrors); render_scatter3d_series()
(series_renderers/scatter3d.py) reads nothing else.

The Z column reference lives here rather than on ``DataSeries`` for the
same reason Colormap/Heatmap keep theirs on their own style class: only a
type whose spec says ``needs_z_column`` ever has one.

Unlike Colormap/Heatmap, Z here is a genuine third *spatial* axis, not a
color channel -- so this type takes no part in the chart-level shared
color scale (SeriesTypeSpec.uses_color_scale is False) and keeps a flat
``color`` for its points."""
from dataclasses import dataclass, field

from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style.base import SeriesStyleBase


@dataclass
class Scatter3DSeriesStyle(SeriesStyleBase):
    color: str = "#1f77b4"
    z_column_id: str = ""
    z_column: str = ""
    marker: MarkerStyle = field(default_factory=MarkerStyle)
