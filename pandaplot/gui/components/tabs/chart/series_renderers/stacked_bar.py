"""Renders a "stacked_bar" series -- a Bar series whose bars start where
the previous stacked series' bars at the same X ended.

Every other renderer draws its series in isolation; this one needs the
running stack height the earlier stacked series in the same render pass
left behind. The caller owns that state: one `BarStack` dict per axes,
created fresh for each full chart render and handed to every series
through `extra["stack_bottoms"]`, which this renderer reads and then
advances in place for whichever stacked series renders next.
"""
from collections.abc import Hashable, Iterable

import numpy as np

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.series_renderers.bar import label_bars
from pandaplot.models.chart.series_style import BarSeriesStyle

# Running stack height so far, keyed by (x value, whether the value is
# negative). Negative values stack downward from zero on their own stack
# rather than eating into the positive one -- otherwise a negative segment
# would be drawn overlapping the positive segments beneath it (the same
# convention pandas' DataFrame.plot.bar(stacked=True) uses).
#
# The x value is used as-is, never converted to float, so two bars meant
# to share a category produce the exact same key: strings and dates stack
# just like numbers, and a numpy scalar hashes equal to its Python twin.
type BarStack = dict[tuple[Hashable, bool], float]


def place_on_stack(x_data: Iterable, y_data: Iterable, stack: BarStack) -> np.ndarray:
    """Return each bar's bottom and advance `stack` past it.

    Bars are placed one at a time, so two rows sharing an X within the same
    series stack on each other too rather than being drawn overlapping.
    A NaN height (a blank cell) draws nothing and leaves the stack as is.

    Args:
        x_data: The bars' X positions.
        y_data: The bars' heights.
        stack: The running stack for the axes these bars are drawn on;
            mutated in place. Pass a copy to compute bottoms without
            committing to them.

    Returns:
        The bottom of each bar, in input order.
    """
    heights = np.asarray(y_data, dtype=float)
    bottoms = np.zeros(len(heights))
    for i, (x, height) in enumerate(zip(x_data, heights, strict=True)):
        key = (x, bool(height < 0))
        bottoms[i] = stack.get(key, 0.0)
        if np.isfinite(height):
            stack[key] = bottoms[i] + height
    return bottoms


def render_stacked_bar_series(axes, series_data: SeriesData, style: BarSeriesStyle,
                               label: str, alpha: float, *, visible: bool, extra: dict) -> None:
    # No stack in `extra` means this series is rendered on its own (e.g. a
    # caller that never stacks), so it simply starts from zero like a Bar.
    stack: BarStack = extra.get("stack_bottoms", {})
    bottoms = place_on_stack(series_data.x_data, series_data.y_data, stack)
    bars = axes.bar(series_data.x_data, series_data.y_data,
                     bottom=bottoms,
                     color=style.color,
                     label=label,
                     alpha=alpha)
    if style.show_value_labels:
        label_bars(axes, bars, style, alpha, label_type="center")
