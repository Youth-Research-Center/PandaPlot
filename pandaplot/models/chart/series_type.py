"""The data-series rendering shapes, independent of chart type.

Distinct from `ChartType` (chart_type.py): a chart's type and a given
series' type are independent by design (e.g. a Bar chart may contain a
scatter-type series). The two enums currently share the same string
values, but they are not the same concept.
"""
from enum import Enum


class SeriesType(str, Enum):
    LINE = "line"
    SCATTER = "scatter"
    BAR = "bar"
    STACKED_BAR = "stacked_bar"
    HIST = "hist"
    DENSITY = "density"
    VECTOR = "vector"
    COLORMAP = "colormap"
    HEATMAP = "heatmap"
    PIE = "pie"
    SCATTER3D = "scatter3d"
    LINE3D = "line3d"
    SURFACE = "surface"
    WIREFRAME = "wireframe"
    BAR3D = "bar3d"
    TRISURF = "trisurf"
    FIT = "fit"
    VECTOR3D = "vector3d"
    BOX = "box"
