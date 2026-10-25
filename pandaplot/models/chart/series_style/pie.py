"""Style fields for a "pie" series -- one wedge per row of its values
column, drawn with ``Axes.pie``. render_pie_series()
(series_renderers/pie.py) reads exactly these plus the series' values
(``y_column_id``, via the shared "values" role Hist also uses) and,
optionally, a wedge-labels column.

Deliberately no flat ``color`` field: a pie series is many wedges, not one
mark, so a single series color has nothing to apply to -- wedges take
matplotlib's default color cycle instead, the same way Colormap/Heatmap
take their color from somewhere other than the series' own style.
"""
from dataclasses import dataclass

from pandaplot.models.chart.series_style.base import SeriesStyleBase


@dataclass
class PieSeriesStyle(SeriesStyleBase):
    # matplotlib's `startangle`, in degrees counter-clockwise from the
    # positive X direction. 90 puts the first wedge's edge at 12 o'clock,
    # which is how most people expect a pie to be read.
    start_angle: float = 90.0
    # Whether each wedge is annotated with its share of the total
    # (matplotlib's `autopct`). Pie's stand-in for the generic value-labels
    # system, which assumes one (x, y) point per value -- see
    # SeriesTypeSpec.supports_value_labels.
    show_percentages: bool = True
    # Fraction of the radius cut out of the middle, 0 (a solid pie) to <1
    # (an ever-thinner ring). Stored as the hole's size rather than
    # matplotlib's wedge `width` (the ring's thickness) because "how big is
    # the hole" is the question the Style tab's slider asks.
    donut_width: float = 0.0
    # Optional column of per-wedge text labels (category names). Blank
    # means unlabeled wedges -- the chart still renders, it just has no
    # wedge text and no legend entries (see render_pie_series).
    label_column_id: str = ""
    label_column: str = ""

    @property
    def swatch_color(self) -> str:
        # No single color represents a multi-colored pie -- same "" answer
        # Heatmap/Colormap give for the same reason.
        return ""
