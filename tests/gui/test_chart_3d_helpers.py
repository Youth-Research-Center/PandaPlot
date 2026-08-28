"""Tests for chart_3d.py's pure geometry helpers.

Qt-free and matplotlib-free (mirrors test_chart_heatmap_helpers.py): these
are the numeric parts of the 3-D renderers, split out precisely so they
can be tested without an Axes3D.
"""
import numpy as np
import pytest

from pandaplot.gui.components.tabs.chart.chart_3d import (
    build_surface_mesh,
    resolve_bar_footprint,
)


def _lattice(side=3):
    """A `side` x `side` lattice of (x, y, z) triples, z = 10*x + y."""
    xs = [float(x) for x in range(side) for _ in range(side)]
    ys = [float(y) for _ in range(side) for y in range(side)]
    zs = [10 * x + y for x, y in zip(xs, ys, strict=True)]
    return xs, ys, zs


def test_build_surface_mesh_broadcasts_the_grid_into_2d_meshes():
    x, y, z = _lattice(3)

    mesh_x, mesh_y, mesh_z = build_surface_mesh(x, y, z, "grid", 50)

    assert mesh_x.shape == mesh_y.shape == mesh_z.shape == (3, 3)
    # meshgrid semantics: x varies along the row, y along the column.
    assert np.array_equal(mesh_x[0], [0.0, 1.0, 2.0])
    assert np.array_equal(mesh_y[:, 0], [0.0, 1.0, 2.0])


def test_build_surface_mesh_places_each_z_at_its_own_x_y():
    x, y, z = _lattice(3)

    mesh_x, mesh_y, mesh_z = build_surface_mesh(x, y, z, "grid", 50)

    for row in range(3):
        for col in range(3):
            assert mesh_z[row, col] == 10 * mesh_x[row, col] + mesh_y[row, col]


def test_build_surface_mesh_leaves_unsampled_cells_as_nan():
    """A ragged lattice (a missing corner) becomes a hole in the surface,
    not a fabricated value -- the same contract pivot_to_grid has for a
    heatmap's transparent cells."""
    mesh_x, _mesh_y, mesh_z = build_surface_mesh(
        [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 2.0, 3.0], "grid", 50)

    assert mesh_x.shape == (2, 2)
    assert np.isnan(mesh_z[1, 1])


def test_build_surface_mesh_bins_scattered_data_to_the_requested_resolution():
    """Scattered (non-lattice) points can't be pivoted exactly, so the
    "binned" mode aggregates them onto a resolution x resolution grid."""
    rng = np.random.default_rng(0)
    x = rng.uniform(0, 10, 200)
    y = rng.uniform(0, 10, 200)
    z = x + y

    mesh_x, mesh_y, mesh_z = build_surface_mesh(x, y, z, "binned", 8)

    assert mesh_x.shape == mesh_y.shape == mesh_z.shape == (8, 8)


def test_build_surface_mesh_raises_when_there_is_nothing_to_grid():
    with pytest.raises(ValueError):
        build_surface_mesh([], [], [], "grid", 50)


def test_resolve_bar_footprint_is_a_fraction_of_the_median_spacing():
    # Values 10 apart, 80% of that spacing -> 8 wide.
    assert resolve_bar_footprint([0.0, 10.0, 20.0, 30.0], 0.8) == pytest.approx(8.0)


def test_resolve_bar_footprint_scales_with_the_data_not_absolute_units():
    """The whole reason the style field is a fraction: the same 0.8 has to
    produce a sensible bar on data 0.001 apart and on data 1000 apart."""
    tiny = resolve_bar_footprint([0.0, 0.001, 0.002], 0.8)
    huge = resolve_bar_footprint([0.0, 1000.0, 2000.0], 0.8)

    assert tiny == pytest.approx(0.0008)
    assert huge == pytest.approx(800.0)


def test_resolve_bar_footprint_ignores_duplicate_and_non_finite_values():
    """Bars sit on distinct coordinates; repeats of the same x (one per y
    row, which every lattice has) must not collapse the spacing to zero."""
    values = [0.0, 0.0, 5.0, 5.0, 10.0, float("nan")]

    assert resolve_bar_footprint(values, 0.8) == pytest.approx(4.0)


def test_resolve_bar_footprint_falls_back_when_there_is_no_spacing_to_measure():
    """A single distinct value has no neighbour to be a fraction of."""
    assert resolve_bar_footprint([7.0, 7.0, 7.0], 0.8) == pytest.approx(0.8)


def test_resolve_bar_footprint_never_returns_zero_width():
    """A zero-width box draws nothing at all, so a 0 (or negative) fraction
    clamps to a small positive width instead of silently hiding the series."""
    assert resolve_bar_footprint([0.0, 1.0, 2.0], 0.0) > 0
    assert resolve_bar_footprint([0.0, 1.0, 2.0], -1.0) > 0
