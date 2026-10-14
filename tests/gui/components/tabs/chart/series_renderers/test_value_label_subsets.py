"""Tests for choosing which points get a value label."""
from matplotlib.figure import Figure

from pandaplot.gui.components.tabs.chart.series_renderers.value_labels import (
    annotate_point_labels,
    resolve_label_indices,
)

Y = [3.0, 9.0, 1.0, 5.0, 7.0]  # min is at position 2, max at position 1


def test_all_labels_every_point():
    assert resolve_label_indices(Y, "all") == {0, 1, 2, 3, 4}


def test_default_mode_is_all():
    assert resolve_label_indices(Y) == {0, 1, 2, 3, 4}


def test_min_only():
    assert resolve_label_indices(Y, "min") == {2}


def test_max_only():
    assert resolve_label_indices(Y, "max") == {1}


def test_extremes_gives_min_and_max():
    assert resolve_label_indices(Y, "extremes") == {1, 2}


def test_extremes_with_one_point_gives_one_label():
    assert resolve_label_indices([4.0], "extremes") == {0}


def test_ties_use_first_occurrence():
    assert resolve_label_indices([1.0, 5.0, 1.0, 5.0], "min") == {0}
    assert resolve_label_indices([1.0, 5.0, 1.0, 5.0], "max") == {1}


def test_nan_values_are_ignored_for_min_and_max():
    assert resolve_label_indices([float("nan"), 4.0, 2.0, float("nan")], "extremes") == {1, 2}


def test_all_nan_gives_no_labels():
    assert resolve_label_indices([float("nan"), float("nan")], "extremes") == set()


def test_empty_data_gives_no_labels():
    assert resolve_label_indices([], "extremes") == set()
    assert resolve_label_indices([], "all") == set()


def test_custom_keeps_only_valid_positions():
    assert resolve_label_indices(Y, "custom", [0, 2, 99, -1]) == {0, 2}


def test_custom_with_no_positions_gives_no_labels():
    assert resolve_label_indices(Y, "custom", []) == set()


def test_unknown_mode_falls_back_to_all():
    assert resolve_label_indices(Y, "something_else") == {0, 1, 2, 3, 4}


def _count_labels(**kwargs) -> int:
    axes = Figure().add_subplot()
    annotate_point_labels(axes, [0, 1, 2, 3, 4], Y, **kwargs)
    return len(axes.texts)


def test_annotate_labels_all_points_by_default():
    assert _count_labels() == 5


def test_annotate_extremes_draws_two_labels():
    assert _count_labels(subset_mode="extremes") == 2


def test_annotate_custom_draws_only_chosen_labels():
    assert _count_labels(subset_mode="custom", custom_indices=[0, 4]) == 2