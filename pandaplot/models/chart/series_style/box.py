"""Style fields for a "box" series -- one box-and-whisker glyph per series,
drawn with ``Axes.boxplot``.

``box_width`` is in data units along X, where sibling box series sit one
unit apart (see series_renderers/box.py), so the default 0.5 leaves an
equal gap between neighbouring boxes. ``show_outliers`` maps to boxplot's
``showfliers``: the points beyond the whiskers (1.5 x IQR) are only hidden,
never excluded from the quartile/whisker computation itself."""
from dataclasses import dataclass

from pandaplot.models.chart.series_style.base import SeriesStyleBase


@dataclass
class BoxSeriesStyle(SeriesStyleBase):
    color: str = "#1f77b4"
    show_outliers: bool = True
    notch: bool = False
    box_width: float = 0.5
