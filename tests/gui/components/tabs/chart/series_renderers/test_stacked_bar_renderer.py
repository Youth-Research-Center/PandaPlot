"""Tests for render_stacked_bar_series and its place_on_stack helper (#396),
on a bare matplotlib Axes -- no Qt needed, same as test_series_renderers.py.
"""
import matplotlib

matplotlib.use("Agg")  # no display needed for these pure-drawing tests
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.series_renderers import SERIES_RENDERERS, render_stacked_bar_series
from pandaplot.gui.components.tabs.chart.series_renderers.stacked_bar import place_on_stack
from pandaplot.models.chart.series_style import BarSeriesStyle
from pandaplot.models.chart.series_type import SeriesType


def _series_data(x_data, y_data) -> SeriesData:
    return SeriesData(x_data=x_data, y_data=y_data, x_err=None, y_err=None,
                      x_err_minus=None, y_err_minus=None, error=None)


def _bar_extents(ax) -> list[tuple[float, float]]:
    """(bottom, height) of every bar drawn on `ax`, in draw order."""
    return [(patch.get_y(), patch.get_height()) for container in ax.containers for patch in container]


@pytest.fixture
def ax():
    fig, ax = plt.subplots()
    yield ax
    plt.close(fig)


def test_stacked_bar_is_registered():
    assert SERIES_RENDERERS[SeriesType.STACKED_BAR] is render_stacked_bar_series


def test_each_series_starts_where_the_previous_one_ended(ax):
    stack = {}
    for y_data in ([1.0, 2.0, 3.0], [10.0, 20.0, 30.0], [100.0, 200.0, 300.0]):
        render_stacked_bar_series(ax, _series_data([1, 2, 3], y_data), BarSeriesStyle(), "s", 1.0,
                                  visible=True, extra={"stack_bottoms": stack})

    assert _bar_extents(ax) == [
        (0.0, 1.0), (0.0, 2.0), (0.0, 3.0),
        (1.0, 10.0), (2.0, 20.0), (3.0, 30.0),
        (11.0, 100.0), (22.0, 200.0), (33.0, 300.0),
    ]


def test_only_matching_x_values_stack(ax):
    """A later series' bar at an X no earlier series used starts from zero."""
    stack = {}
    render_stacked_bar_series(ax, _series_data([1, 2], [5.0, 6.0]), BarSeriesStyle(), "a", 1.0,
                              visible=True, extra={"stack_bottoms": stack})
    render_stacked_bar_series(ax, _series_data([2, 3], [1.0, 1.0]), BarSeriesStyle(), "b", 1.0,
                              visible=True, extra={"stack_bottoms": stack})

    assert _bar_extents(ax)[2:] == [(6.0, 1.0), (0.0, 1.0)]


def test_categorical_x_values_stack_by_category(ax):
    stack = {}
    render_stacked_bar_series(ax, _series_data(pd.Series(["a", "b"]), pd.Series([1.0, 2.0])), BarSeriesStyle(), "s1", 1.0,
                              visible=True, extra={"stack_bottoms": stack})
    render_stacked_bar_series(ax, _series_data(pd.Series(["b", "a"]), pd.Series([3.0, 4.0])), BarSeriesStyle(), "s2", 1.0,
                              visible=True, extra={"stack_bottoms": stack})

    assert _bar_extents(ax)[2:] == [(2.0, 3.0), (1.0, 4.0)]


def test_without_a_stack_it_draws_like_a_plain_bar(ax):
    render_stacked_bar_series(ax, _series_data([1, 2], [3.0, 4.0]), BarSeriesStyle(color="#ff0000"), "s", 0.5,
                              visible=True, extra={})

    assert _bar_extents(ax) == [(0.0, 3.0), (0.0, 4.0)]
    patch = ax.containers[0][0]
    assert matplotlib.colors.to_hex(patch.get_facecolor()) == "#ff0000"
    assert patch.get_alpha() == 0.5
    assert ax.containers[0].get_label() == "s"


def test_value_labels_show_each_segments_own_value_not_the_running_total(ax):
    stack = {}
    style = BarSeriesStyle(show_value_labels=True)
    render_stacked_bar_series(ax, _series_data([1], [2.0]), style, "a", 1.0, visible=True, extra={"stack_bottoms": stack})
    render_stacked_bar_series(ax, _series_data([1], [5.0]), style, "b", 1.0, visible=True, extra={"stack_bottoms": stack})

    assert [text.get_text() for text in ax.texts] == ["2", "5"]


def test_negative_values_stack_downward_on_their_own():
    """A negative value must not eat into the positive stack (it would be
    drawn overlapping the positive segments below it)."""
    stack = {}
    place_on_stack([1], [3.0], stack)
    bottoms = place_on_stack([1], [-2.0], stack)
    assert bottoms.tolist() == [0.0]
    assert place_on_stack([1], [4.0], stack).tolist() == [3.0]
    assert place_on_stack([1], [-1.0], stack).tolist() == [-2.0]


def test_nan_heights_leave_the_stack_untouched():
    stack = {}
    place_on_stack([1, 2], [np.nan, 2.0], stack)
    assert place_on_stack([1, 2], [1.0, 1.0], stack).tolist() == [0.0, 2.0]


def test_duplicate_x_within_one_series_stacks_too():
    assert place_on_stack(["a", "a", "b"], [1.0, 2.0, 3.0], {}).tolist() == [0.0, 1.0, 0.0]


def test_numpy_and_python_scalars_of_the_same_x_share_a_stack():
    stack = {}
    place_on_stack(np.array([1, 2]), [1.0, 1.0], stack)
    assert place_on_stack(pd.Series([2.0, 1.0]), [1.0, 1.0], stack).tolist() == [1.0, 1.0]
