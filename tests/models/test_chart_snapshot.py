"""Tests for model-level chart state snapshot/restore helpers."""

import numpy as np

from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.series_style import LineSeriesStyle
from pandaplot.models.project.items.chart import (
    Chart,
    restore_chart_state,
    snapshot_chart_state,
)


def _make_chart():
    chart = Chart(name="My Chart")
    chart.add_data_series("ds1", "x", "y", label="s1", style=LineSeriesStyle(color="#112233"))
    return chart


def test_restore_reverts_config_type_name_and_series():
    chart = _make_chart()
    snap = snapshot_chart_state(chart)

    chart.config["x_label"] = "changed"
    chart.chart_type = "scatter"
    chart.name = "Renamed"
    chart.data_series[0].style.color = "#ffffff"

    restore_chart_state(chart, snap)

    assert chart.config["x_label"] == ""
    assert chart.chart_type == "line"
    assert chart.name == "My Chart"
    assert chart.data_series[0].style.color == "#112233"


def test_snapshot_is_a_deep_copy_of_config():
    chart = _make_chart()
    snap = snapshot_chart_state(chart)
    chart.config["title"] = "mutated after snapshot"
    assert snap["config"]["title"] == "My Chart"


def test_restore_recreates_removed_series():
    chart = _make_chart()
    snap = snapshot_chart_state(chart)
    chart.data_series.clear()
    restore_chart_state(chart, snap)
    assert len(chart.data_series) == 1
    assert chart.data_series[0].label == "s1"


def test_restore_reverts_background_style_fields():
    chart = _make_chart()
    snap = snapshot_chart_state(chart)

    chart.style["figure_background_color"] = "#000000"
    chart.style["axes_background_color"] = "#111111"

    restore_chart_state(chart, snap)

    assert chart.style["figure_background_color"] == "#ffffff"
    assert chart.style["axes_background_color"] == "#ffffff"


def test_restore_only_touches_fit_style_fields():
    chart = _make_chart()
    chart.add_fit_data(
        "ds1", "Linear",
        np.array([1.0]), np.array([2.0]),
        style=FitStyle(color="#ff0000", line_width=2.0),
    )
    snap = snapshot_chart_state(chart)

    chart.fit_data[0].style.color = "#00ff00"
    chart.fit_data[0].style.line_width = 5.0

    restore_chart_state(chart, snap)

    assert chart.fit_data[0].style.color == "#ff0000"
    assert chart.fit_data[0].style.line_width == 2.0


def test_restore_reverts_fit_alpha():
    """Regression: fit opacity (alpha) must be part of the snapshot/restore
    cycle, same as color and line_width -- otherwise Revert silently leaves
    an opacity edit in place."""
    chart = _make_chart()
    chart.add_fit_data(
        "ds1", "Linear",
        np.array([1.0]), np.array([2.0]),
        style=FitStyle(alpha=1.0),
    )
    snap = snapshot_chart_state(chart)

    chart.fit_data[0].style.alpha = 0.3

    restore_chart_state(chart, snap)

    assert chart.fit_data[0].style.alpha == 1.0


def test_restore_reverts_fit_label():
    """Regression (#187): the fit's label -- editable via the same Data-tab
    field used for data-series labels -- was never snapshotted (only
    `fit.style` was), so Undo left a fit-data label edit in place even
    though the equivalent data-series edit correctly reverted."""
    chart = _make_chart()
    chart.add_fit_data(
        "ds1", "Linear",
        np.array([1.0]), np.array([2.0]),
        label="Original Fit",
    )
    snap = snapshot_chart_state(chart)

    chart.fit_data[0].label = "Renamed Fit"

    restore_chart_state(chart, snap)

    assert chart.fit_data[0].label == "Original Fit"


def test_restore_reverts_a_manual_fits_source_and_data_edits():
    """Regression test (PR #309 review): a manually-converted fit's
    dataset/X/Y/confidence source columns and x_data/y_data are editable
    from the Data tab (#298 follow-up), same as a data series -- Reset
    (and ApplyChartPropertiesCommand's own undo/redo) must revert those
    edits too, not just style/label."""
    chart = _make_chart()
    chart.add_fit_data(
        "ds1", "Custom",
        np.array([1.0, 2.0]), np.array([3.0, 4.0]),
        source_x_column_id="x-col", source_y_column_id="y-col",
        is_manual=True,
    )
    snap = snapshot_chart_state(chart)

    fit = chart.fit_data[0]
    fit.source_dataset_id = "ds2"
    fit.source_x_column_id = "x-col-2"
    fit.source_y_column_id = "y-col-2"
    fit.x_data = np.array([99.0, 98.0])
    fit.y_data = np.array([97.0, 96.0])

    restore_chart_state(chart, snap)

    restored = chart.fit_data[0]
    assert restored.source_dataset_id == "ds1"
    assert restored.source_x_column_id == "x-col"
    assert restored.source_y_column_id == "y-col"
    np.testing.assert_array_equal(restored.x_data, np.array([1.0, 2.0]))
    np.testing.assert_array_equal(restored.y_data, np.array([3.0, 4.0]))


def test_restore_reverts_fit_line_style():
    """Regression test for a bug that survived until this phase: only
    color/line_width/alpha were snapshotted, so line_style silently kept
    whatever the user changed it to even after Revert/Cancel."""
    chart = _make_chart()
    chart.add_fit_data(
        "ds1", "Linear",
        np.array([1.0]), np.array([2.0]),
        style=FitStyle(line_style="solid"),
    )
    snap = snapshot_chart_state(chart)

    chart.fit_data[0].style.line_style = "dotted"

    restore_chart_state(chart, snap)

    assert chart.fit_data[0].style.line_style == "solid"
