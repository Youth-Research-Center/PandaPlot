"""The categories chart types are grouped into wherever they are listed.

Each ChartTypeSpec names its category; CHART_TYPE_CATEGORIES (in
chart_type_spec.py) is derived from the specs rather than kept as a second
list. The values are the display labels, and the member order is the order
the groups are shown in.
"""
from enum import Enum


class ChartCategory(str, Enum):
    LINE_SCATTER = "Line & Scatter"
    BAR_PIE = "Bar & Pie"
    DISTRIBUTION = "Distribution"
    FIELD_GRID = "Fields & Grids"
    THREE_D = "3-D"
