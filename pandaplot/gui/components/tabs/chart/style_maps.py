"""Model-string-to-matplotlib-parameter lookup tables, shared by the
series_renderers/ package and chart_editor.py's fit-plotting code."""
from pandaplot.models.chart.value_label_arrow import ValueLabelArrowStyle

MARKER_MAP = {
    "circle": "o", "square": "s", "triangle": "^", "diamond": "D",
    "star": "*", "plus": "+", "cross": "x", "none": "",
}

LINESTYLE_MAP = {
    "solid": "-", "dashed": "--", "dotted": ":", "dashdot": "-.", "none": "none",
}

# Value-label leader lines (#504). ValueLabelArrowLineStyle is a StrEnum, so its
# members index LINESTYLE_MAP directly.
ARROWSTYLE_MAP = {
    ValueLabelArrowStyle.LINE: "-",
    ValueLabelArrowStyle.ARROW: "->",
    ValueLabelArrowStyle.FILLED_ARROW: "-|>",
}
