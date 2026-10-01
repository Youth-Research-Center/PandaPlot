"""Renders a "box" series -- one box-and-whisker glyph summarizing the
series' single "values" column (resolved into series_data.y_data, as for a
histogram).

A box chart compares several distributions side by side, one box per
series, but no single renderer call sees its siblings. They coordinate
through extra["box_positions"]: a list the caller creates once per render
pass and hands to every series in it. Each box takes the next free X slot
(1, 2, 3... -- boxplot's own default numbering), appends its
(position, tick label) and re-applies the whole accumulated tick list, so
the axis is correct after whichever box happens to render last without
the render loop needing a "this is the last one" hook. A caller that
passes no list (a one-off render) simply gets a single box at position 1.

Returns the dict of artists boxplot() creates, or None when there's
nothing to draw (see SERIES_RENDERERS_REPORTING_NO_DATA): no values left
once non-numeric/NaN entries are dropped. A box with no data claims no
slot, so its siblings don't leave a gap for it. boxplot() artists have no
legend handler, so like Surface/Bar3D, a box series has no legend entry --
its tick label names it instead.
"""
import numpy as np
import pandas as pd

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.models.chart.series_style import BoxSeriesStyle

BOX_POSITIONS_KEY = "box_positions"


def apply_box_ticks(axes, entries: list[tuple[int, str]]) -> None:
    """Label the X axis with one tick per rendered box.

    Also called by chart_editor.py after it applies the chart-level X tick
    settings, which would otherwise replace these fixed, named ticks with
    numeric auto-placed ones.

    Args:
        axes: The matplotlib Axes the boxes were drawn on.
        entries: (position, label) pairs, one per box, in render order.
    """
    axes.set_xticks([position for position, _ in entries], labels=[label for _, label in entries])


def render_box_series(axes, series_data: SeriesData, style: BoxSeriesStyle,
                      label: str, alpha: float, *, visible: bool, extra: dict) -> dict | None:
    # to_numeric(errors="coerce") rather than astype(float): a stray text
    # cell in an otherwise numeric column should drop that one value, not
    # the whole box -- the same leniency as the NaNs dropped next to it.
    values = pd.to_numeric(pd.Series(series_data.y_data), errors="coerce").to_numpy(dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return None

    entries = extra.get(BOX_POSITIONS_KEY)
    if entries is None:
        entries = []
    position = len(entries) + 1

    artists = axes.boxplot(
        [values],
        positions=[position],
        widths=style.box_width,
        notch=style.notch,
        showfliers=style.show_outliers,
        patch_artist=True,
        # Median/whisker lines keep matplotlib's dark defaults (they need to
        # contrast with the filled box), but the outlier markers take the
        # series color so they read as belonging to their own box.
        flierprops={"markerfacecolor": style.color, "markeredgecolor": style.color, "alpha": alpha},
        medianprops={"color": "black"},
    )
    for box in artists["boxes"]:
        box.set_facecolor(style.color)
        box.set_alpha(alpha)

    entries.append((position, label or f"Series {position}"))
    apply_box_ticks(axes, entries)
    return artists
