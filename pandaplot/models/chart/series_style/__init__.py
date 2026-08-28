"""Typed per-series-type style dataclasses.

One class per SeriesType (pandaplot.models.chart.series_type), each
holding exactly the fields that type's chart_editor.py rendering branch
reads today. See base.py for why SeriesStyleBase itself is empty.
"""
from pandaplot.models.chart.series_style.bar import BarSeriesStyle
from pandaplot.models.chart.series_style.bar3d import Bar3DSeriesStyle
from pandaplot.models.chart.series_style.base import SeriesStyleBase
from pandaplot.models.chart.series_style.colormap import ColormapSeriesStyle
from pandaplot.models.chart.series_style.heatmap import HeatmapSeriesStyle
from pandaplot.models.chart.series_style.hist import HistSeriesStyle
from pandaplot.models.chart.series_style.line import LineSeriesStyle
from pandaplot.models.chart.series_style.line3d import Line3DSeriesStyle
from pandaplot.models.chart.series_style.scatter import ScatterSeriesStyle
from pandaplot.models.chart.series_style.scatter3d import Scatter3DSeriesStyle
from pandaplot.models.chart.series_style.surface import SurfaceSeriesStyle
from pandaplot.models.chart.series_style.trisurf import TrisurfSeriesStyle
from pandaplot.models.chart.series_style.vector import VectorSeriesStyle
from pandaplot.models.chart.series_style.wireframe import WireframeSeriesStyle

__all__ = [
    "SeriesStyleBase",
    "LineSeriesStyle",
    "ScatterSeriesStyle",
    "BarSeriesStyle",
    "HistSeriesStyle",
    "VectorSeriesStyle",
    "ColormapSeriesStyle",
    "HeatmapSeriesStyle",
    "Scatter3DSeriesStyle",
    "Line3DSeriesStyle",
    "SurfaceSeriesStyle",
    "WireframeSeriesStyle",
    "Bar3DSeriesStyle",
    "TrisurfSeriesStyle",
]
