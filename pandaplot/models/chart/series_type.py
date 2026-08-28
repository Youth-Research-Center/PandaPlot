"""The data-series rendering shapes, independent of chart type.

Distinct from `ChartType` (chart_type.py): a chart's type and a given
series' type are independent by design (e.g. a Bar chart may contain a
scatter-type series, once Phase 4 allows mixed series types) -- the two
enums happen to share the same 5 string values today only because no
chart currently mixes series types, not because they're the same concept.
"""
from enum import Enum


class SeriesType(str, Enum):
    LINE = "line"
    SCATTER = "scatter"
    BAR = "bar"
    HIST = "hist"
    VECTOR = "vector"
    COLORMAP = "colormap"
    HEATMAP = "heatmap"
    SCATTER3D = "scatter3d"
    LINE3D = "line3d"
    SURFACE = "surface"
    WIREFRAME = "wireframe"
    BAR3D = "bar3d"
    TRISURF = "trisurf"
