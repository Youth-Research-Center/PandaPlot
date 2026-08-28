"""Geometry helpers for the 3-D chart types (surface, wireframe, bar3d).

Kept separate from the renderers (and from the chart editor widget) so the
numeric geometry can be unit-tested with no Qt and no matplotlib axes at
all -- mirrors chart_error_bars.py and chart_heatmap.py.
"""

import numpy as np

from pandaplot.gui.components.tabs.chart.chart_heatmap import build_heatmap_grid


def build_surface_mesh(x_data, y_data, z_data, mode: str, resolution: int):
    """Turn scattered ``(x, y, z)`` into the ``(X, Y, Z)`` 2-D mesh triple
    ``Axes3D.plot_surface``/``plot_wireframe`` expect.

    Gridding is delegated wholesale to
    :func:`~pandaplot.gui.components.tabs.chart.chart_heatmap.build_heatmap_grid`
    -- "surface" is the same lattice problem a heatmap solves, viewed from
    the side, so the same three modes apply verbatim ("grid" pivots an
    exact lattice, "binned"/"interpolated" handle arbitrary scattered
    data). The only difference is shape: pcolormesh takes the 1-D
    centers, while the 3-D calls take a full meshgrid, so this broadcasts
    them.

    Cells no sample covers stay ``NaN``, which both 3-D calls render as a
    hole in the surface -- the same "nothing was measured here" outcome
    the heatmap draws as a transparent cell.

    Raises:
        ValueError: when there's no data to grid (propagated from
        ``build_heatmap_grid``), so callers can report a per-series error
        instead of drawing empty axes.
    """
    xs, ys, grid = build_heatmap_grid(x_data, y_data, z_data, mode, resolution)
    mesh_x, mesh_y = np.meshgrid(np.asarray(xs, dtype=float), np.asarray(ys, dtype=float))
    return mesh_x, mesh_y, np.asarray(grid, dtype=float)


def resolve_bar_footprint(values, fraction: float) -> float:
    """Absolute width (in data units) of one ``bar3d`` box along one axis.

    ``fraction`` is a fraction of the *median gap* between the axis's
    distinct values, not an absolute size: 0.8 means "each bar fills 80%
    of the spacing to its neighbour", which is the only definition that
    survives a dataset whose x values are 0.001 apart and one whose x
    values are 10 000 apart. (An absolute default would draw invisible
    slivers on the first and one solid overlapping slab on the second.)

    Falls back to ``fraction`` itself when the spacing can't be measured
    -- fewer than two distinct finite values on this axis, i.e. every bar
    sits at the same coordinate and there is no neighbour to be a
    fraction of. Never returns 0 (a zero-width box renders as nothing);
    a non-positive ``fraction`` clamps to a small positive width.
    """
    array = np.asarray(values, dtype=float)
    array = np.unique(array[np.isfinite(array)])
    spacing = float(np.median(np.diff(array))) if array.size >= 2 else 1.0
    width = abs(spacing) * fraction
    return width if width > 0 else 1e-9
