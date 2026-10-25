"""Renders a "pie" series: one wedge per row of the values column
(``series_data.y_data``), optionally labeled from ``series_data.label_data``.

Rows whose value isn't a finite number (blank cells, text) are skipped, and
so are zero-valued rows -- a zero wedge has no area, only a label that would
collide with its neighbor's. A *negative* value is different: a pie has no
way to show one, and silently dropping it would make every other wedge's
share wrong, so any negative value fails the whole series instead (returns
None -- PIE is in SERIES_RENDERERS_REPORTING_NO_DATA, so the caller reports
it rather than drawing an empty axes). Same for a series with nothing left
to draw.

Unlike every (x, y) renderer, the series' own `label` isn't used: a pie is
many wedges, not one mark, so there is no single legend entry to give it.
When a label column is set, each wedge carries its own category label
instead, which is also what the chart's legend then lists -- matplotlib's
pie() gives each wedge patch the label it's drawn with.
"""
import numpy as np
import pandas as pd

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.models.chart.series_style import PieSeriesStyle

# Slider upper bound for donut_width (see the Style tab's Pie card). Kept
# below 1 here too, so a hand-edited project file can't ask for a ring of
# zero thickness, which matplotlib would draw as nothing at all.
_MAX_DONUT_HOLE = 0.9


def render_pie_series(axes, series_data: SeriesData, style: PieSeriesStyle,
                      label: str, alpha: float, *, visible: bool, extra: dict) -> list | None:
    values = pd.to_numeric(pd.Series(np.asarray(series_data.y_data, dtype=object)), errors="coerce").to_numpy(dtype=float)
    keep = np.isfinite(values) & (values != 0)
    if np.any(values[keep] < 0) or not np.any(keep):
        return None

    labels = None
    if series_data.label_data is not None:
        all_labels = ["" if pd.isna(text) else str(text) for text in series_data.label_data]
        labels = [text for text, kept in zip(all_labels, keep, strict=True) if kept]

    wedgeprops: dict = {"alpha": alpha}
    hole = min(max(style.donut_width, 0.0), _MAX_DONUT_HOLE)
    if hole > 0:
        # matplotlib's wedge `width` is the ring's thickness as a fraction
        # of the radius -- the complement of the hole size the style stores.
        wedgeprops["width"] = 1.0 - hole

    wedges, *_texts = axes.pie(
        values[keep],
        labels=labels,
        autopct="%1.1f%%" if style.show_percentages else None,
        # A donut's percentages sit at the default 0.6 radius, i.e. in the
        # hole once it's bigger than 0.4 -- center them on the ring instead.
        pctdistance=1.0 - (1.0 - hole) / 2 if hole > 0 else 0.6,
        startangle=style.start_angle,
        wedgeprops=wedgeprops,
    )
    return wedges
