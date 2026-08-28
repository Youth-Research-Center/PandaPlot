"""One place that builds a series' typed ``style`` object from the pieces
a UI collects: a color and whatever column ids the type needs.

Every entry point that creates a series -- the Data tab's "+Add series",
its bootstrap path in ``apply_to``, the chart wizard's Finish, and the
wizard's live preview -- used to carry its own if/elif over concrete style
classes ("if VECTOR: ... elif COLORMAP/HEATMAP: ... else: ..."). Four
copies of the same knowledge, each of which had to be found and updated
whenever a series type was added, and each of which silently dropped the
fields it forgot (the wizard's Colormap branch, for instance, built its
style with a z_column_id and no color at all).

This drives the whole thing off SERIES_TYPE_SPECS instead, so a new series
type is picked up by all four call sites the moment it's registered there.
"""
from typing import Optional

from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_style import SeriesStyleBase
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS


def build_series_style(
    series_type: "str | SeriesType",
    color: str = "",
    error_bars: Optional[ErrorBarConfig] = None,
    u_column_id: str = "",
    v_column_id: str = "",
    magnitude_column_id: str = "",
    z_column_id: str = "",
) -> SeriesStyleBase:
    """Build the style object `series_type` requires, populated with only
    the arguments that type actually declares a field for.

    Every argument is optional and quietly ignored by a type that has no
    use for it -- callers pass whatever their UI has to hand (a Data tab
    combo holds a stale U column while a Line series is selected, say)
    without having to know which of them this type will keep. That's the
    point: the caller collects values, this decides what they mean.

    `color` lands on ``vector_color`` for a Vector series and on ``color``
    for every type that has one; the color-scaled types (Colormap,
    Heatmap, Surface, Trisurf) declare neither and take their color from
    the chart-level color map instead, so it's dropped for them. An empty
    `color` never overwrites the style class's own default.
    """
    spec = SERIES_TYPE_SPECS[SeriesType(series_type)]
    style = spec.style_cls()

    if color:
        if hasattr(style, "vector_color"):
            style.vector_color = color
        elif hasattr(style, "color"):
            style.color = color

    if error_bars is not None and spec.supports_error_bars:
        style.error_bars = error_bars

    if spec.needs_secondary_columns:
        style.u_column_id = u_column_id
        style.v_column_id = v_column_id
        style.magnitude_column_id = magnitude_column_id

    if spec.needs_z_column:
        style.z_column_id = z_column_id

    return style
