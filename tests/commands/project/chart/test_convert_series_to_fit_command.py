"""Tests for ConvertSeriesToFitCommand execute/undo/redo."""

import json
import logging
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.chart.convert_series_to_fit_command import (
    ConvertSeriesToFitCommand,
)
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart


@pytest.fixture
def dataset():
    df = pd.DataFrame({
        "x": [1.0, 2.0, 3.0],
        "y": [10.0, 20.0, 30.0],
        "y_lower": [9.0, 19.0, 29.0],
        "y_upper": [11.0, 21.0, 31.0],
    })
    return Dataset(id="ds-1", name="DS", data=df)


@pytest.fixture
def chart_with_series(dataset):
    chart = Chart(id="chart-1", name="C")
    series = chart.add_data_series(
        dataset.id,
        x_column_id=dataset.column_id("x"),
        y_column_id=dataset.column_id("y"),
        label="My Series",
    )
    return chart, series


@pytest.fixture
def app_context_with_chart(chart_with_series, dataset):
    chart, _ = chart_with_series
    project = Mock()

    def _find_item(item_id):
        if item_id == chart.id:
            return chart
        if item_id == dataset.id:
            return dataset
        return None

    project.find_item.side_effect = _find_item

    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()
    return app_context, chart


def test_execute_moves_series_to_fit_data(app_context_with_chart):
    app_context, chart = app_context_with_chart
    command = ConvertSeriesToFitCommand(app_context, chart_id="chart-1", series_index=0)

    assert command.execute() is CommandResult.SUCCESS
    assert len(chart.data_series) == 0
    assert len(chart.fit_data) == 1

    fit = chart.fit_data[0]
    assert fit.source_dataset_id == "ds-1"
    assert fit.fit_type == "Custom"
    assert fit.label == "My Series"
    np.testing.assert_array_equal(fit.x_data, np.array([1.0, 2.0, 3.0]))
    np.testing.assert_array_equal(fit.y_data, np.array([10.0, 20.0, 30.0]))
    assert fit.confidence_lower is None
    assert fit.confidence_upper is None
    assert isinstance(fit.style, FitStyle)
    assert fit.is_manual is True


def test_execute_snapshots_confidence_columns_when_given(app_context_with_chart, dataset):
    app_context, chart = app_context_with_chart
    command = ConvertSeriesToFitCommand(
        app_context, chart_id="chart-1", series_index=0,
        confidence_lower_column_id=dataset.column_id("y_lower"),
        confidence_upper_column_id=dataset.column_id("y_upper"),
    )

    assert command.execute() is CommandResult.SUCCESS

    fit = chart.fit_data[0]
    np.testing.assert_array_equal(fit.confidence_lower, np.array([9.0, 19.0, 29.0]))
    np.testing.assert_array_equal(fit.confidence_upper, np.array([11.0, 21.0, 31.0]))
    assert fit.confidence_lower_column_id == dataset.column_id("y_lower")
    assert fit.confidence_upper_column_id == dataset.column_id("y_upper")


def test_fit_data_is_independent_of_later_source_mutations(app_context_with_chart, dataset):
    app_context, chart = app_context_with_chart
    command = ConvertSeriesToFitCommand(app_context, chart_id="chart-1", series_index=0)

    assert command.execute() is CommandResult.SUCCESS
    fit = chart.fit_data[0]

    original_x = fit.x_data.copy()
    original_y = fit.y_data.copy()

    # Mutate the source DataFrame in place, mirroring EditCommand's
    # iloc-based cell edit. If FitData.x_data/y_data alias the DataFrame's
    # block memory (e.g. via a non-copying to_numpy()), this mutation
    # would leak into the "frozen" fit data.
    dataset.data.iloc[0, dataset.data.columns.get_loc("x")] = 999.0
    dataset.data.iloc[0, dataset.data.columns.get_loc("y")] = 888.0

    np.testing.assert_array_equal(fit.x_data, original_x)
    np.testing.assert_array_equal(fit.y_data, original_y)
    assert fit.x_data[0] != 999.0
    assert fit.y_data[0] != 888.0


def test_execute_out_of_range_returns_failure(app_context_with_chart, caplog):
    app_context, chart = app_context_with_chart
    command = ConvertSeriesToFitCommand(app_context, chart_id="chart-1", series_index=5)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert len(chart.data_series) == 1
    assert len(chart.fit_data) == 0
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_execute_logs_a_warning_when_chart_not_found(caplog):
    project = Mock()
    project.find_item.return_value = None
    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project
    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()

    command = ConvertSeriesToFitCommand(app_context, chart_id="missing", series_index=0)

    with caplog.at_level(logging.WARNING):
        assert command.execute() is CommandResult.FAILURE
    assert "missing" in caplog.text


def test_undo_restores_the_original_series(app_context_with_chart, chart_with_series):
    app_context, chart = app_context_with_chart
    _, original_series = chart_with_series

    command = ConvertSeriesToFitCommand(app_context, chart_id="chart-1", series_index=0)
    command.execute()

    command.undo()

    assert len(chart.data_series) == 1
    assert len(chart.fit_data) == 0
    restored = chart.data_series[0]
    assert restored.dataset_id == original_series.dataset_id
    assert restored.x_column_id == original_series.x_column_id
    assert restored.y_column_id == original_series.y_column_id
    assert restored.label == original_series.label


def test_redo_converts_again(app_context_with_chart):
    app_context, chart = app_context_with_chart
    command = ConvertSeriesToFitCommand(app_context, chart_id="chart-1", series_index=0)

    command.execute()
    command.undo()
    command.redo()

    assert len(chart.data_series) == 0
    assert len(chart.fit_data) == 1


def test_datetime_x_column_is_coerced_to_numeric_and_json_safe(app_context_with_chart):
    """Regression test for final-review Fix 1 (#298): a non-numeric (e.g.
    datetime64) source column must not be snapshotted as-is into
    FitData.x_data/y_data. Chart.to_dict() calls .tolist() on those
    arrays and the project save path json.dumps()s the result with no
    custom encoder, so a raw datetime64 dtype would make the project
    fail to save -- and since ProjectDataManager.save() truncates the
    zip before writing, a failed save can destroy the previously-saved
    project file.
    """
    app_context, chart = app_context_with_chart

    project = app_context.get_app_state.return_value.current_project
    datetime_dataset = Dataset(
        id="ds-datetime",
        name="DS-Datetime",
        data=pd.DataFrame({
            "x": pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
            "y": [10.0, 20.0, 30.0],
        }),
    )
    original_find_item = project.find_item.side_effect

    def _find_item(item_id):
        if item_id == datetime_dataset.id:
            return datetime_dataset
        return original_find_item(item_id)

    project.find_item.side_effect = _find_item

    datetime_series = chart.add_data_series(
        datetime_dataset.id,
        x_column_id=datetime_dataset.column_id("x"),
        y_column_id=datetime_dataset.column_id("y"),
        label="Datetime Series",
    )
    series_index = chart.data_series.index(datetime_series)

    command = ConvertSeriesToFitCommand(app_context, chart_id="chart-1", series_index=series_index)

    assert command.execute() is CommandResult.SUCCESS

    fit = next(f for f in chart.fit_data if f.label == "Datetime Series")
    assert np.issubdtype(fit.x_data.dtype, np.number)
    assert np.issubdtype(fit.y_data.dtype, np.number)

    # Must round-trip through Chart.to_dict() -> json.dumps() without
    # raising (this is what the project save path does).
    json.dumps(chart.to_dict())


def test_wholly_non_numeric_x_column_fails_instead_of_producing_an_all_nan_fit(app_context_with_chart):
    """A source column that's genuinely non-numeric (every value fails to
    coerce) must reject the conversion with the existing "could not read
    source data" error, not silently succeed with an all-NaN fit curve
    that renders nothing and gives the user no indication anything went
    wrong -- recoverable only via undo."""
    app_context, chart = app_context_with_chart

    project = app_context.get_app_state.return_value.current_project
    text_dataset = Dataset(
        id="ds-text",
        name="DS-Text",
        data=pd.DataFrame({
            "x": ["alpha", "beta", "gamma"],
            "y": [10.0, 20.0, 30.0],
        }),
    )
    original_find_item = project.find_item.side_effect

    def _find_item(item_id):
        if item_id == text_dataset.id:
            return text_dataset
        return original_find_item(item_id)

    project.find_item.side_effect = _find_item

    text_series = chart.add_data_series(
        text_dataset.id,
        x_column_id=text_dataset.column_id("x"),
        y_column_id=text_dataset.column_id("y"),
        label="Text Series",
    )
    series_index = chart.data_series.index(text_series)

    command = ConvertSeriesToFitCommand(app_context, chart_id="chart-1", series_index=series_index)

    assert command.execute() is CommandResult.FAILURE
    assert not any(f.label == "Text Series" for f in chart.fit_data)
    assert any(s.label == "Text Series" for s in chart.data_series)
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_a_non_empty_but_unresolvable_confidence_column_fails_the_whole_conversion(app_context_with_chart, dataset):
    """A confidence column id must be either empty ("no confidence band",
    valid) or resolve to real numeric data -- a non-empty pick that
    fails to resolve (e.g. wholly non-numeric) must reject the WHOLE
    conversion, not silently succeed with a confidence_lower_column_id
    that points at a column the fit's confidence_lower array doesn't
    actually reflect."""
    app_context, chart = app_context_with_chart
    dataset.data["label"] = ["a", "b", "c"]
    dataset._sync_column_ids()

    command = ConvertSeriesToFitCommand(
        app_context, chart_id="chart-1", series_index=0,
        confidence_lower_column_id=dataset.column_id("label"),
    )

    assert command.execute() is CommandResult.FAILURE
    assert len(chart.fit_data) == 0
    assert len(chart.data_series) == 1


def test_a_column_with_some_unconvertible_values_still_succeeds(app_context_with_chart):
    """Only a WHOLLY unusable column is rejected -- a column with some
    real numeric values alongside a few unconvertible ones still
    converts fine (NaN mixed with real data is normal/expected)."""
    app_context, chart = app_context_with_chart

    project = app_context.get_app_state.return_value.current_project
    mixed_dataset = Dataset(
        id="ds-mixed",
        name="DS-Mixed",
        data=pd.DataFrame({
            "x": ["1.0", "not-a-number", "3.0"],
            "y": [10.0, 20.0, 30.0],
        }),
    )
    original_find_item = project.find_item.side_effect

    def _find_item(item_id):
        if item_id == mixed_dataset.id:
            return mixed_dataset
        return original_find_item(item_id)

    project.find_item.side_effect = _find_item

    mixed_series = chart.add_data_series(
        mixed_dataset.id,
        x_column_id=mixed_dataset.column_id("x"),
        y_column_id=mixed_dataset.column_id("y"),
        label="Mixed Series",
    )
    series_index = chart.data_series.index(mixed_series)

    command = ConvertSeriesToFitCommand(app_context, chart_id="chart-1", series_index=series_index)

    assert command.execute() is CommandResult.SUCCESS
    fit = next(f for f in chart.fit_data if f.label == "Mixed Series")
    assert fit.x_data[0] == 1.0
    assert np.isnan(fit.x_data[1])
    assert fit.x_data[2] == 3.0


def test_empty_series_label_falls_back_to_custom_fit(app_context_with_chart, dataset):
    """Regression test for final-review Fix 3 (#298): an empty (but
    normal/supported) series label must not produce an unlabeled fit --
    fit cards render f"\U0001f527 {fit.label}" with no fallback, unlike
    series cards.
    """
    app_context, chart = app_context_with_chart

    unlabeled_series = chart.add_data_series(
        dataset.id,
        x_column_id=dataset.column_id("x"),
        y_column_id=dataset.column_id("y"),
        label="",
    )
    series_index = chart.data_series.index(unlabeled_series)

    command = ConvertSeriesToFitCommand(app_context, chart_id="chart-1", series_index=series_index)

    assert command.execute() is CommandResult.SUCCESS

    fit = chart.fit_data[-1]
    assert fit.label == "Custom Fit"


def test_cleanup_releases_bookkeeping(app_context_with_chart):
    app_context, chart = app_context_with_chart
    command = ConvertSeriesToFitCommand(app_context, chart_id="chart-1", series_index=0)
    command.execute()

    assert command.removed_series is not None
    assert command.added_fit_index is not None

    command.cleanup()
    assert command.removed_series is None
    assert command.added_fit_index is None
