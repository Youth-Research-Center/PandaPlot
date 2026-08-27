"""Pure-numpy tests for the colormap/heatmap geometry helpers, independent of
Qt/matplotlib (mirrors test_chart_editor_background_rendering.py's approach)."""
import numpy as np
import pytest

from pandaplot.gui.components.tabs.chart.chart_heatmap import (
    bin_to_grid,
    build_heatmap_grid,
    filter_finite_xyz,
    interpolate_to_grid,
    pivot_to_grid,
    resolve_color_limits,
)


def test_resolve_color_limits_auto_uses_data_range():
    assert resolve_color_limits([3.0, 1.0, 2.0], auto=True, vmin=0.0, vmax=0.0) == (1.0, 3.0)


def test_resolve_color_limits_auto_ignores_non_finite():
    vmin, vmax = resolve_color_limits([1.0, np.nan, 5.0, np.inf], auto=True, vmin=0.0, vmax=0.0)
    assert (vmin, vmax) == (1.0, 5.0)


def test_resolve_color_limits_auto_all_non_finite_returns_none():
    assert resolve_color_limits([np.nan, np.inf], auto=True, vmin=0.0, vmax=0.0) == (None, None)


def test_resolve_color_limits_manual_passthrough():
    assert resolve_color_limits([0.0, 100.0], auto=False, vmin=10.0, vmax=20.0) == (10.0, 20.0)


def test_resolve_color_limits_manual_degenerate_pair_is_nudged():
    # vmin >= vmax would collapse the map to one color; the pair is separated.
    vmin, vmax = resolve_color_limits([0.0], auto=False, vmin=5.0, vmax=5.0)
    assert vmin == 5.0 and vmax > vmin


def test_pivot_to_grid_regular_grid():
    # A full 2x2 grid: (x, y) -> z.
    xs, ys, grid = pivot_to_grid([0, 1, 0, 1], [0, 0, 1, 1], [10, 20, 30, 40])
    assert list(xs) == [0.0, 1.0]
    assert list(ys) == [0.0, 1.0]
    # grid[j, i] is z at (xs[i], ys[j]).
    np.testing.assert_array_equal(grid, [[10.0, 20.0], [30.0, 40.0]])


def test_pivot_to_grid_missing_cell_is_nan():
    # (1, 1) is absent -> that cell stays NaN.
    xs, ys, grid = pivot_to_grid([0, 1, 0], [0, 0, 1], [10, 20, 30])
    assert np.isnan(grid[1, 1])
    assert grid[0, 0] == 10.0
    assert grid[0, 1] == 20.0
    assert grid[1, 0] == 30.0


def test_pivot_to_grid_duplicate_last_wins():
    xs, ys, grid = pivot_to_grid([0, 0], [0, 0], [1, 99])
    assert grid.shape == (1, 1)
    assert grid[0, 0] == 99.0


def test_pivot_to_grid_empty_raises():
    with pytest.raises(ValueError):
        pivot_to_grid([], [], [])


def test_pivot_to_grid_drops_non_finite_coordinates_without_raising():
    """pcolormesh rejects non-finite coordinate arrays -- a single NaN/Inf
    X or Y would otherwise reach it (after this helper returns, outside
    the renderer's ValueError guard) and blank the whole chart. The row
    with the bad coordinate is dropped; the rest of the data still grids.
    Flagged in PR #190 review."""
    xs, ys, grid = pivot_to_grid([0, np.nan, 1], [0, 0, 1], [10, 999, 40])
    assert list(xs) == [0.0, 1.0]
    assert list(ys) == [0.0, 1.0]
    assert grid[0, 0] == 10.0
    assert grid[1, 1] == 40.0
    assert np.isnan(grid[0, 1])  # (1, 0) was never sampled -- unaffected
    assert np.isnan(grid[1, 0])  # (0, 1) was never sampled -- unaffected


def test_pivot_to_grid_keeps_non_finite_z_as_a_transparent_cell():
    """Unlike a non-finite X/Y coordinate, a non-finite Z at an otherwise
    valid (x, y) is meaningful data ("no value recorded here") and must
    stay in the grid as NaN -- not be dropped -- so it renders as a
    transparent cell rather than a hole with no rendered marker at all."""
    xs, ys, grid = pivot_to_grid([0, 1], [0, 0], [10.0, np.nan])
    assert grid[0, 0] == 10.0
    assert np.isnan(grid[0, 1])


def test_pivot_to_grid_all_coordinates_non_finite_raises():
    with pytest.raises(ValueError):
        pivot_to_grid([np.nan, np.inf], [np.nan, np.inf], [1.0, 2.0])


# --- scattered-data gridding: bin_to_grid ---

def test_bin_to_grid_shape_and_mean_aggregation():
    # Two points land in the same (low-x, low-y) bin; the cell holds their mean.
    x = [0.1, 0.2, 0.9]
    y = [0.1, 0.2, 0.9]
    z = [10.0, 20.0, 100.0]
    xs, ys, grid = bin_to_grid(x, y, z, bins=2)
    assert grid.shape == (2, 2)
    assert len(xs) == 2 and len(ys) == 2
    # bottom-left cell = mean(10, 20) = 15; top-right = 100.
    assert grid[0, 0] == 15.0
    assert grid[1, 1] == 100.0


def test_bin_to_grid_empty_cells_are_nan():
    xs, ys, grid = bin_to_grid([0.0, 1.0], [0.0, 1.0], [1.0, 2.0], bins=2)
    # Only the diagonal cells have points; off-diagonal cells are NaN.
    assert np.isnan(grid[0, 1])
    assert np.isnan(grid[1, 0])


def test_bin_to_grid_empty_raises():
    with pytest.raises(ValueError):
        bin_to_grid([], [], [], bins=4)


def test_bin_to_grid_drops_non_finite_triples_without_raising():
    """A non-finite X/Y breaks histogram2d's inferred range; a non-finite Z
    contaminates the weighted sum for an otherwise-valid bin. Dropping the
    whole (x, y, z) triple is safe -- it's equivalent to that point never
    having been sampled, which bin_to_grid already treats as an empty
    (NaN) cell. Flagged in PR #190 review."""
    x = [0.1, np.nan, 0.2, 0.9]
    y = [0.1, 0.0, np.nan, 0.9]
    z = [10.0, 999.0, 999.0, 100.0]
    xs, ys, grid = bin_to_grid(x, y, z, bins=2)
    assert grid.shape == (2, 2)
    assert grid[0, 0] == 10.0
    assert grid[1, 1] == 100.0


# --- scattered-data gridding: interpolate_to_grid ---

def test_interpolate_to_grid_shape_and_fills_interior():
    rng = np.random.default_rng(0)
    x = rng.random(100)
    y = rng.random(100)
    z = x + y
    xs, ys, grid = interpolate_to_grid(x, y, z, resolution=16)
    assert grid.shape == (16, 16)
    assert np.isfinite(grid).any()


def test_interpolate_to_grid_collinear_falls_back_to_nearest():
    # Collinear points can't be triangulated by linear griddata; the helper
    # must fall back to "nearest" and still produce a full field.
    xs, ys, grid = interpolate_to_grid([0, 0, 0], [0, 1, 2], [1, 2, 3], resolution=5)
    assert grid.shape == (5, 5)
    assert np.all(np.isfinite(grid))


def test_interpolate_to_grid_drops_non_finite_triples_without_raising():
    """A non-finite X/Y makes x.min()/y.min() non-finite, which would
    break BOTH the primary interpolation and the "nearest" fallback,
    discarding all otherwise-valid points. Flagged in PR #190 review."""
    rng = np.random.default_rng(0)
    x = np.concatenate([rng.random(50), [np.nan]])
    y = np.concatenate([rng.random(50), [0.0]])
    z = np.concatenate([x[:50] + y[:50], [999.0]])
    xs, ys, grid = interpolate_to_grid(x, y, z, resolution=10)
    assert grid.shape == (10, 10)
    assert np.isfinite(grid).any()


# --- dispatch: build_heatmap_grid ---

def test_build_heatmap_grid_dispatches_by_mode():
    x, y, z = [0, 1, 0, 1], [0, 0, 1, 1], [1, 2, 3, 4]
    _, _, grid_exact = build_heatmap_grid(x, y, z, "grid", 5)
    assert grid_exact.shape == (2, 2)
    _, _, grid_binned = build_heatmap_grid(x, y, z, "binned", 3)
    assert grid_binned.shape == (3, 3)
    _, _, grid_interp = build_heatmap_grid(x, y, z, "interpolated", 4)
    assert grid_interp.shape == (4, 4)


def test_build_heatmap_grid_unknown_mode_is_exact_grid():
    _, _, grid = build_heatmap_grid([0, 1, 0, 1], [0, 0, 1, 1], [1, 2, 3, 4], "???", 5)
    assert grid.shape == (2, 2)


# --- triangulated (scattered, ungridded) rendering: filter_finite_xyz ---

def test_filter_finite_xyz_passes_through_clean_data():
    x, y, z = filter_finite_xyz([0, 1, 2], [0, 1, 0], [10.0, 20.0, 30.0])
    np.testing.assert_array_equal(x, [0.0, 1.0, 2.0])
    np.testing.assert_array_equal(y, [0.0, 1.0, 0.0])
    np.testing.assert_array_equal(z, [10.0, 20.0, 30.0])


def test_filter_finite_xyz_drops_non_finite_triples():
    x, y, z = filter_finite_xyz(
        [0, np.nan, 1, 2, 3], [0, 0, np.inf, 1, 2], [10.0, 999.0, 999.0, 30.0, 40.0])
    np.testing.assert_array_equal(x, [0.0, 2.0, 3.0])
    np.testing.assert_array_equal(y, [0.0, 1.0, 2.0])
    np.testing.assert_array_equal(z, [10.0, 30.0, 40.0])


def test_filter_finite_xyz_empty_raises():
    with pytest.raises(ValueError):
        filter_finite_xyz([], [], [])


def test_filter_finite_xyz_fewer_than_3_points_raises():
    """matplotlib's Triangulation needs at least 3 points -- caught here
    up front rather than surfacing as an uncaught error mid-render."""
    with pytest.raises(ValueError):
        filter_finite_xyz([0, 1], [0, 1], [10.0, 20.0])


def test_filter_finite_xyz_exactly_3_points_is_ok():
    x, y, z = filter_finite_xyz([0, 1, 2], [0, 1, 0], [10.0, 20.0, 30.0])
    assert len(x) == 3


# --- matplotlib API smoke tests: guard the exact calls the renderer makes ---

def test_colormap_scatter_produces_colorbar_mappable():
    from matplotlib.figure import Figure

    fig = Figure()
    axes = fig.add_subplot(111)
    z = [1.0, 2.0, 3.0]
    vmin, vmax = resolve_color_limits(z, auto=True, vmin=0.0, vmax=0.0)
    mappable = axes.scatter([0, 1, 2], [0, 1, 0], c=z, cmap="viridis", vmin=vmin, vmax=vmax)
    # A colorbar can be built from the returned mappable, as update_chart does.
    cbar = fig.colorbar(mappable, ax=axes)
    assert cbar is not None
    cbar.remove()


def test_heatmap_pcolormesh_produces_colorbar_mappable():
    from matplotlib.figure import Figure

    fig = Figure()
    axes = fig.add_subplot(111)
    xs, ys, grid = pivot_to_grid([0, 1, 0, 1], [0, 0, 1, 1], [10, 20, 30, 40])
    mappable = axes.pcolormesh(xs, ys, grid, cmap="viridis", shading="nearest")
    cbar = fig.colorbar(mappable, ax=axes)
    assert cbar is not None
    cbar.remove()
