"""The chart types, independent of the series types a chart may contain.

Values match Chart.chart_type's stored strings exactly, so no
translation dict is needed between the model and the renderers.
"""
from enum import Enum


class ChartType(str, Enum):
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
    # 3-D types (rendered on a matplotlib mplot3d axes -- see
    # ChartTypeSpec.is_3d, which is what every consumer should branch on
    # rather than testing membership of this group by hand).
    SCATTER3D = "scatter3d"
    LINE3D = "line3d"
    SURFACE = "surface"
    WIREFRAME = "wireframe"
    BAR3D = "bar3d"
    TRISURF = "trisurf"
    VECTOR3D = "vector3d"
    BOX = "box"
