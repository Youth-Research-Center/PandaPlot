"""Helpers for the color-mapped chart types ("colormap" scatter and gridded
"heatmap"): resolving the color scale limits and pivoting scattered (x, y, z)
triples into the regular 2-D grid ``Axes.pcolormesh()`` expects.

Kept separate from the chart editor widget so the numeric geometry can be
unit-tested without any Qt/matplotlib widget setup (mirrors chart_error_bars).
"""

from typing import Optional

import numpy as np


def resolve_color_limits(
    z_data, auto: bool, vmin: float, vmax: float
) -> tuple[Optional[float], Optional[float]]:
    """Resolve the (vmin, vmax) passed to a colormap normalization.

    When ``auto`` the colormap spans the data's own finite min..max, returned
    so callers can label the colorbar consistently (matplotlib would do the
    same autoscaling internally, but returning it here keeps the value
    available). ``(None, None)`` is returned instead when the data has no
    finite values to autoscale from, letting matplotlib fall back to its own
    default. When not ``auto`` the explicit ``vmin``/``vmax`` are used as-is;
    an inverted or degenerate pair (vmin >= vmax) is nudged so the two limits
    never coincide, which would otherwise collapse the whole map to one color.
    """
    if auto:
        values = np.asarray(z_data, dtype=float)
        values = values[np.isfinite(values)]
        if values.size == 0:
            return None, None
        return float(values.min()), float(values.max())
    if vmin >= vmax:
        return vmin, vmin + 1.0
    return vmin, vmax


def pivot_to_grid(x_data, y_data, z_data):
    """Pivot scattered ``(x, y, z)`` triples into a dense grid for pcolormesh.

    Returns ``(xs, ys, grid)`` where ``xs``/``ys`` are the sorted unique x/y
    coordinates and ``grid[j, i]`` is the z value at ``(xs[i], ys[j])``;
    unmatched cells are ``NaN`` (transparent), so this handles both a
    fully-populated grid and a sparse/ragged one. Duplicate (x, y) pairs
    resolve to the last occurrence. Raises ``ValueError`` when there are no
    points to grid.

    Rows with a non-finite X/Y are dropped before gridding, since
    ``pcolormesh`` rejects non-finite coordinates outright and that error
    would surface after this function returns, past the ``ValueError``
    guard. A non-finite Z is left in place -- it just renders as the
    already-supported transparent (NaN) cell.
    """
    x = np.asarray(x_data, dtype=float)
    y = np.asarray(y_data, dtype=float)
    z = np.asarray(z_data, dtype=float)
    if x.size == 0 or y.size == 0 or z.size == 0:
        raise ValueError("no data to grid")

    finite_xy = np.isfinite(x) & np.isfinite(y)
    x, y, z = x[finite_xy], y[finite_xy], z[finite_xy]
    if x.size == 0:
        raise ValueError("no data to grid")

    xs = np.unique(x)
    ys = np.unique(y)
    # Map each coordinate to its index in the sorted-unique axis via searchsorted
    # (exact matches, since xs/ys came from the data itself).
    xi = np.searchsorted(xs, x)
    yi = np.searchsorted(ys, y)
    grid = np.full((ys.size, xs.size), np.nan)
    grid[yi, xi] = z
    return xs, ys, grid


def bin_to_grid(x_data, y_data, z_data, bins: int):
    """Aggregate scattered ``(x, y, z)`` points into a regular ``bins x bins``
    grid via 2-D-histogram, each cell holding the **mean** z of points that
    fall in it (unlike :func:`pivot_to_grid`, which needs an exact x/y
    lattice). Empty cells are ``NaN``. Returns ``(x_centers, y_centers,
    grid)`` shaped for pcolormesh with ``shading="nearest"``. Raises
    ``ValueError`` when there are no points to bin.

    A non-finite X, Y, or Z drops the whole triple first: a non-finite X/Y
    would break ``histogram2d``'s auto-detected range, and a non-finite Z
    would contaminate the weighted sum of an otherwise-valid bin.
    """
    x = np.asarray(x_data, dtype=float)
    y = np.asarray(y_data, dtype=float)
    z = np.asarray(z_data, dtype=float)
    if x.size == 0 or y.size == 0 or z.size == 0:
        raise ValueError("no data to bin")

    finite = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    x, y, z = x[finite], y[finite], z[finite]
    if x.size == 0:
        raise ValueError("no data to bin")
    bins = max(1, int(bins))

    sums, xedges, yedges = np.histogram2d(x, y, bins=bins, weights=z)
    counts, _, _ = np.histogram2d(x, y, bins=bins)
    with np.errstate(invalid="ignore", divide="ignore"):
        means = sums / counts
    means[counts == 0] = np.nan
    x_centers = 0.5 * (xedges[:-1] + xedges[1:])
    y_centers = 0.5 * (yedges[:-1] + yedges[1:])
    # histogram2d indexes [xi, yi]; pcolormesh wants (ny, nx), so transpose.
    return x_centers, y_centers, means.T


def interpolate_to_grid(x_data, y_data, z_data, resolution: int, method: str = "linear"):
    """Interpolate scattered ``(x, y, z)`` points onto a regular
    ``resolution x resolution`` grid via ``scipy.interpolate.griddata``, for a
    smooth heatmap (vs. :func:`bin_to_grid`'s blocky per-cell means).

    ``method`` is "linear"/"cubic"/"nearest"; "linear"/"cubic" leave points
    outside the convex hull as ``NaN``. Inputs ``griddata`` can't triangulate
    (too few points, all collinear) fall back to "nearest", which always
    fills the field. Returns ``(x_centers, y_centers, grid)`` shaped for
    pcolormesh, or raises ``ValueError`` when there's nothing to interpolate.

    A non-finite X, Y, or Z drops the whole triple first: a non-finite X/Y
    would make ``x.min()``/``y.min()`` non-finite, breaking both the
    interpolation and the "nearest" fallback for all points.
    """
    from scipy.interpolate import griddata

    x = np.asarray(x_data, dtype=float)
    y = np.asarray(y_data, dtype=float)
    z = np.asarray(z_data, dtype=float)
    if x.size == 0 or y.size == 0 or z.size == 0:
        raise ValueError("no data to interpolate")

    finite = np.isfinite(x) & np.isfinite(y) & np.isfinite(z)
    x, y, z = x[finite], y[finite], z[finite]
    if x.size == 0:
        raise ValueError("no data to interpolate")
    resolution = max(2, int(resolution))

    xs = np.linspace(float(x.min()), float(x.max()), resolution)
    ys = np.linspace(float(y.min()), float(y.max()), resolution)
    grid_x, grid_y = np.meshgrid(xs, ys)
    points = np.column_stack([x, y])
    try:
        grid = griddata(points, z, (grid_x, grid_y), method=method)
    except Exception:
        grid = None
    # "nearest" always yields a full field; fall back to it when a
    # triangulation-based method failed or produced an all-NaN result.
    if grid is None or not np.any(np.isfinite(grid)):
        grid = griddata(points, z, (grid_x, grid_y), method="nearest")
    return xs, ys, grid


def build_heatmap_grid(x_data, y_data, z_data, mode: str, resolution: int):
    """Turn ``(x, y, z)`` into a regular grid for a heatmap, choosing how by
    ``mode``: "binned" (2-D-histogram means) and "interpolated" (griddata) both
    handle arbitrary **scattered** data; anything else ("grid", the default)
    uses the exact :func:`pivot_to_grid` for data already on a lattice.
    ``resolution`` is the per-axis bin/grid-point count for the scattered modes
    (ignored by "grid"). Returns ``(xs, ys, grid)``; raises ``ValueError`` when
    there's no data."""
    if mode == "binned":
        return bin_to_grid(x_data, y_data, z_data, resolution)
    if mode == "interpolated":
        return interpolate_to_grid(x_data, y_data, z_data, resolution)
    return pivot_to_grid(x_data, y_data, z_data)
