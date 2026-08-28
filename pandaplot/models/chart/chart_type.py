"""The chart types, independent of the series types a chart may contain.

Distinct from chart_configuration.ChartType (which this replaces
everywhere it's used -- see chart_tab.py/style_tab.py in a later task):
that enum's HISTOGRAM = "histogram" never matched the live renderer's
"hist" string (chart_tab.py translated between them via 3 duplicated
dicts); this enum's values match Chart.chart_type's stored strings
exactly, so no translation dict is needed anywhere.
"""
from enum import Enum


class ChartType(str, Enum):
    LINE = "line"
    SCATTER = "scatter"
    BAR = "bar"
    HIST = "hist"
    VECTOR = "vector"
    COLORMAP = "colormap"
    HEATMAP = "heatmap"
    # 3-D types (rendered on a matplotlib mplot3d axes -- see
    # ChartTypeSpec.is_3d, which is what every consumer should branch on
    # rather than testing membership of this group by hand).
    SCATTER3D = "scatter3d"
    LINE3D = "line3d"
    SURFACE = "surface"
    WIREFRAME = "wireframe"
    BAR3D = "bar3d"
    TRISURF = "trisurf"
