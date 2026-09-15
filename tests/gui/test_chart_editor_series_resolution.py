"""Tests for resolve_series_data and build_error_array (no Qt widgets involved)."""

import numpy as np
import pandas as pd

from pandaplot.gui.components.tabs.chart.chart_editor import resolve_series_data
from pandaplot.gui.components.tabs.chart.chart_error_bars import build_error_array
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_style.line import LineSeriesStyle
from pandaplot.models.project.items.chart import DataSeries, ErrorDirection
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project


def _project_with_dataset():
    project = Project("P")
    dataset = Dataset(name="ds", data=pd.DataFrame({
        "a": [1, 2], "b": [3, 4], "err": [0.1, 0.2], "err_minus": [0.05, 0.15],
    }))
    project.add_item(dataset)
    return project, dataset


def test_resolves_x_and_y_columns():
    project, dataset = _project_with_dataset()
    series = DataSeries(dataset_id=dataset.id, x_column="a", y_column="b")
    result = resolve_series_data(project, series)
    assert result.error is None
    assert list(result.x_data) == [1, 2]
    assert list(result.y_data) == [3, 4]
    assert result.x_err is None
    assert result.y_err is None
    assert result.x_err_minus is None
    assert result.y_err_minus is None


def test_empty_x_column_uses_dataframe_index():
    project, dataset = _project_with_dataset()
    series = DataSeries(dataset_id=dataset.id, x_column="", y_column="b")
    result = resolve_series_data(project, series)
    assert result.error is None
    assert list(result.x_data) == [0, 1]


def test_missing_dataset_returns_error():
    project, _ = _project_with_dataset()
    series = DataSeries(dataset_id="nope", x_column="a", y_column="b")
    result = resolve_series_data(project, series)
    assert result.x_data is None and result.y_data is None
    assert "nope" in result.error


def test_missing_column_returns_error_naming_the_column():
    project, dataset = _project_with_dataset()
    series = DataSeries(dataset_id=dataset.id, x_column="a", y_column="gone")
    result = resolve_series_data(project, series)
    assert result.x_data is None and result.y_data is None
    assert "gone" in result.error


def test_resolves_z_label_from_z_column():
    """z_label should be the resolved display name of the series' Z column
    (used for the colorbar's default label), precomputed here instead of a
    second live project lookup during rendering."""
    from pandaplot.models.chart.series_type import SeriesType

    project, dataset = _project_with_dataset()
    dataset.data["z"] = [10.0, 20.0]
    series = DataSeries(dataset_id=dataset.id, x_column="a", y_column="b", series_type=SeriesType.COLORMAP)
    series.style.z_column = "z"
    result = resolve_series_data(project, series)
    assert result.z_label == "z"


def test_no_project_returns_error():
    series = DataSeries(dataset_id="ds", x_column="a", y_column="b")
    result = resolve_series_data(None, series)
    assert result.error is not None


def test_histogram_ignores_stale_x_column():
    project, dataset = _project_with_dataset()
    series = DataSeries(dataset_id=dataset.id, x_column="gone", y_column="b")
    result = resolve_series_data(project, series, chart_type="hist")
    assert result.error is None
    assert list(result.y_data) == [3, 4]


def test_resolves_y_error_column():
    project, dataset = _project_with_dataset()
    style = LineSeriesStyle(error_bars=ErrorBarConfig(y_error_column="err"))
    series = DataSeries(dataset_id=dataset.id, x_column="a", y_column="b", style=style)
    result = resolve_series_data(project, series)
    assert result.error is None
    assert list(result.y_err) == [0.1, 0.2]
    assert result.x_err is None


def test_missing_error_column_is_lenient():
    """A stale/unset error-column reference must not turn the whole series into an error."""
    project, dataset = _project_with_dataset()
    style = LineSeriesStyle(error_bars=ErrorBarConfig(y_error_column="gone"))
    series = DataSeries(dataset_id=dataset.id, x_column="a", y_column="b", style=style)
    result = resolve_series_data(project, series)
    assert result.error is None
    assert list(result.y_data) == [3, 4]
    assert result.y_err is None


def test_resolves_asymmetric_minus_column():
    project, dataset = _project_with_dataset()
    style = LineSeriesStyle(error_bars=ErrorBarConfig(
        y_error_column="err", y_error_minus_column="err_minus", error_symmetric=False,
    ))
    series = DataSeries(dataset_id=dataset.id, x_column="a", y_column="b", style=style)
    result = resolve_series_data(project, series)
    assert result.error is None
    assert list(result.y_err) == [0.1, 0.2]
    assert list(result.y_err_minus) == [0.05, 0.15]


# --- build_error_array ---

def test_symmetric_both_direction_returns_raw_magnitude():
    magnitude = np.array([0.1, 0.2])
    result = build_error_array(magnitude, None, direction=ErrorDirection.BOTH, symmetric=True)
    assert list(result) == [0.1, 0.2]


def test_symmetric_plus_direction_zeroes_lower_side():
    magnitude = np.array([0.1, 0.2])
    result = build_error_array(magnitude, None, direction=ErrorDirection.PLUS, symmetric=True)
    assert list(result[0]) == [0.0, 0.0]
    assert list(result[1]) == [0.1, 0.2]


def test_symmetric_no_magnitude_returns_none():
    assert build_error_array(None, None, direction=ErrorDirection.BOTH, symmetric=True) is None


def test_asymmetric_combines_plus_and_minus_columns():
    plus = np.array([0.1, 0.2])
    minus = np.array([0.05, 0.15])
    result = build_error_array(plus, minus, direction=ErrorDirection.BOTH, symmetric=False)
    assert list(result[0]) == [0.05, 0.15]
    assert list(result[1]) == [0.1, 0.2]


def test_asymmetric_missing_minus_side_defaults_to_zero():
    plus = np.array([0.1, 0.2])
    result = build_error_array(plus, None, direction=ErrorDirection.BOTH, symmetric=False)
    assert list(result[0]) == [0.0, 0.0]
    assert list(result[1]) == [0.1, 0.2]


def test_asymmetric_missing_plus_side_defaults_to_zero():
    minus = np.array([0.05, 0.15])
    result = build_error_array(None, minus, direction=ErrorDirection.BOTH, symmetric=False)
    assert list(result[0]) == [0.05, 0.15]
    assert list(result[1]) == [0.0, 0.0]


def test_asymmetric_no_columns_returns_none():
    assert build_error_array(None, None, direction=ErrorDirection.BOTH, symmetric=False) is None
