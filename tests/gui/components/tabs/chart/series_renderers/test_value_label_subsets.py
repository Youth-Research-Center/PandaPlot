"""Tests for choosing which points get a value label."""
import math

import pandas as pd
from matplotlib.figure import Figure

from pandaplot.gui.components.tabs.chart.series_renderers.value_labels import (
    annotate_point_labels,
    resolve_label_indices,
)

NAN = float("nan")
INF = float("inf")
X = [0, 1, 2, 3, 4]
Y = [3.0, 9.0, 1.0, 5.0, 7.0]  # min is at position 2, max at position 1


def test_all_labels_every_point():
    assert resolve_label_indices(X, Y, subset_mode="all") == {0, 1, 2, 3, 4}


def test_default_mode_is_all():
    assert resolve_label_indices(X, Y) == {0, 1, 2, 3, 4}


def test_min_only():
    assert resolve_label_indices(X, Y, subset_mode="min") == {2}


def test_max_only():
    assert resolve_label_indices(X, Y, subset_mode="max") == {1}


def test_extremes_gives_min_and_max():
    assert resolve_label_indices(X, Y, subset_mode="extremes") == {1, 2}


def test_extremes_with_one_point_gives_one_label():
    assert resolve_label_indices([0], [4.0], subset_mode="extremes") == {0}


def test_ties_use_first_occurrence():
    x = [0, 1, 2, 3]
    y = [1.0, 5.0, 1.0, 5.0]
    assert resolve_label_indices(x, y, subset_mode="min") == {0}
    assert resolve_label_indices(x, y, subset_mode="max") == {1}


def test_nan_y_values_are_ignored_for_min_and_max():
    assert resolve_label_indices([0, 1, 2, 3], [NAN, 4.0, 2.0, NAN], subset_mode="extremes") == {1, 2}


def test_nan_x_point_is_never_chosen():
    # The lowest y belongs to a point with no x, so it can't be drawn.
    assert resolve_label_indices([NAN, 1, 2, 3], [0, 5, 3, 4], subset_mode="min") == {2}


def test_infinite_y_is_never_chosen():
    assert resolve_label_indices([0, 1, 2, 3], [1, 2, INF, 3], subset_mode="max") == {3}
    assert resolve_label_indices([0, 1, 2, 3], [-INF, 2, 5, 3], subset_mode="min") == {1}


def test_missing_datetime_y_is_never_chosen():
    y = pd.to_datetime(["2020-01-01", None, "2020-01-03"])
    assert resolve_label_indices([0, 1, 2], y, subset_mode="min") == {0}
    assert resolve_label_indices([0, 1, 2], y, subset_mode="max") == {2}


def test_all_nan_gives_no_labels():
    assert resolve_label_indices([0, 1], [NAN, NAN], subset_mode="extremes") == set()


def test_empty_data_gives_no_labels():
    assert resolve_label_indices([], [], subset_mode="extremes") == set()
    assert resolve_label_indices([], [], subset_mode="all") == set()


def test_unknown_mode_falls_back_to_all():
    assert resolve_label_indices(X, Y, subset_mode="something_else") == {0, 1, 2, 3, 4}


def _labeled_points(x, y, **kwargs) -> list:
    """The (x, y) position of every label drawn, in drawing order."""
    axes = Figure().add_subplot()
    annotate_point_labels(axes, x, y, **kwargs)
    return [annotation.xy for annotation in axes.texts]


def test_annotate_labels_all_points_by_default():
    assert _labeled_points(X, Y) == list(zip(X, Y, strict=True))


def test_annotate_extremes_labels_the_min_and_max_points():
    assert _labeled_points(X, Y, subset_mode="extremes") == [(1, 9.0), (2, 1.0)]


def test_annotate_min_skips_a_point_with_missing_x_and_labels_the_real_min():
    assert _labeled_points([NAN, 1, 2, 3], [0, 5, 3, 4], subset_mode="min") == [(2, 3)]


def test_tz_aware_datetime_y_still_picks_min_and_max():
    y = pd.to_datetime(["2020-01-02", "2020-01-01", "2020-01-03"]).tz_localize("UTC")
    assert resolve_label_indices([0, 1, 2], y, subset_mode="extremes") == {1, 2}
    assert resolve_label_indices([0, 1, 2], list(y), subset_mode="min") == {1}


def test_datetime_y_ranks_without_losing_nanosecond_precision():
    y = pd.to_datetime(["2020-01-01 00:00:00.000000002", "2020-01-01 00:00:00.000000001", "2020-01-01 00:00:00.000000003"])
    assert resolve_label_indices([0, 1, 2], y, subset_mode="min") == {1}
    assert resolve_label_indices([0, 1, 2], y, subset_mode="max") == {2}


def test_local_extremes_finds_peaks_and_valleys():
    # Peaks at 1, 3 and 5; valleys at 2 and 4. The ends are never extrema.
    y = [0, 2, 1, 3, 0, 4, 1]
    assert resolve_label_indices(range(7), y, subset_mode="local_extremes") == {1, 2, 3, 4, 5}


def test_local_extremes_of_a_sine_wave_are_its_peaks_and_valleys():
    x = [i * 0.1 for i in range(200)]
    y = [math.sin(value) for value in x]

    indices = resolve_label_indices(x, y, subset_mode="local_extremes")

    assert len(indices) == 6
    assert all(abs(abs(y[index]) - 1) < 0.01 for index in indices)


def test_local_extremes_labels_a_flat_top_once_at_its_first_point():
    assert resolve_label_indices(range(4), [1, 3, 3, 1], subset_mode="local_extremes") == {1}


def test_local_extremes_of_a_rising_series_are_empty():
    assert resolve_label_indices(range(4), [1, 2, 3, 4], subset_mode="local_extremes") == set()


def test_local_extremes_never_include_the_first_or_last_point():
    assert resolve_label_indices(range(4), [5, 1, 2, 0], subset_mode="local_extremes") == {1, 2}


def test_local_extremes_need_at_least_three_points():
    assert resolve_label_indices(range(2), [1, 2], subset_mode="local_extremes") == set()
    assert resolve_label_indices([], [], subset_mode="local_extremes") == set()


def test_local_extremes_of_a_constant_series_are_empty():
    assert resolve_label_indices(range(4), [2, 2, 2, 2], subset_mode="local_extremes") == set()


def test_local_extremes_skip_undrawable_points_and_compare_across_them():
    nan = float("nan")
    assert resolve_label_indices(range(6), [1, 5, nan, 3, 0, 2], subset_mode="local_extremes") == {1, 4}


def test_local_extremes_work_for_datetime_y():
    y = pd.to_datetime(["2020-01-02", "2020-01-05", "2020-01-03", "2020-01-04"])
    assert resolve_label_indices(range(4), y, subset_mode="local_extremes") == {1, 2}


def test_annotate_local_extremes_labels_the_peaks_and_valleys():
    axes = Figure().add_subplot()

    annotate_point_labels(axes, list(range(7)), [0, 2, 1, 3, 0, 4, 1], subset_mode="local_extremes")

    assert [annotation.xy for annotation in axes.texts] == [(1, 2), (2, 1), (3, 3), (4, 0), (5, 4)]