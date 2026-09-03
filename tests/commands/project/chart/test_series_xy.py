"""Tests for the shared chart-series x/y resolver."""

from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.commands.project.chart.series_xy import resolve_series_xy
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppState


@pytest.fixture
def app_state():
    project = Project(name="P")
    t = np.linspace(0.0, 10.0, 11)
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"t": t, "sq": t ** 2}))
    project.add_item(dataset)

    chart = Chart(id="chart-1", name="C")
    x_id = dataset.column_id("t")
    y_id = dataset.column_id("sq")
    chart.add_data_series(dataset_id="ds-1", x_column_id=x_id, y_column_id=y_id,
                          x_column="t", y_column="sq", label="Squared")
    chart.add_fit_data(source_dataset_id="ds-1", fit_type="quadratic",
                       x_data=t, y_data=t ** 2, label="Quadratic Fit", source_x_column="t")
    project.add_item(chart)

    state = Mock(spec=AppState)
    state.current_project = project
    return state, chart


class TestResolveSeriesXY:
    def test_resolves_a_data_series(self, app_state):
        state, chart = app_state
        x, y, x_label, y_label = resolve_series_xy(state, chart, "series", 0)
        assert x_label == "t"
        assert y_label == "Squared"
        assert y.iloc[5] == pytest.approx(x.iloc[5] ** 2)

    def test_resolves_a_fit(self, app_state):
        state, chart = app_state
        x, y, x_label, y_label = resolve_series_xy(state, chart, "fit", 0)
        assert x_label == "t"
        assert y_label == "Quadratic Fit"
        assert len(x) == 11

    def test_missing_series_index_raises(self, app_state):
        state, chart = app_state
        with pytest.raises(ValueError, match="no longer exists"):
            resolve_series_xy(state, chart, "series", 9)

    def test_missing_fit_index_raises(self, app_state):
        state, chart = app_state
        with pytest.raises(ValueError, match="no longer exists"):
            resolve_series_xy(state, chart, "fit", 9)

    def test_series_type_without_curve_support_raises(self, app_state):
        state, chart = app_state
        chart.data_series[0].series_type = SeriesType.BAR
        with pytest.raises(ValueError, match="bar"):
            resolve_series_xy(state, chart, "series", 0)

    def test_coerce_numeric_defaults_to_true(self, app_state):
        """AnalyzeChartSeriesCommand relies on the default -- a non-numeric
        axis is meaningless for derivative/integral/etc."""
        state, chart = app_state
        dataset = state.current_project.find_item("ds-1")
        dataset.data["t"] = dataset.data["t"].astype(str)

        x, _y, _x_label, _y_label = resolve_series_xy(state, chart, "series", 0)

        assert pd.api.types.is_numeric_dtype(x)

    def test_coerce_numeric_false_preserves_the_untouched_axis_dtype(self, app_state):
        """TransformChartSeriesCommand passes coerce_numeric=False so a
        categorical/string/datetime axis round-trips unchanged instead of
        being rewritten to NaN, and a string axis stays visible to a
        transform expression like x.str.upper()."""
        state, chart = app_state
        dataset = state.current_project.find_item("ds-1")
        dataset.data["t"] = ["cat", "dog", "bird", "fish", "ant", "bee", "cow", "pig", "rat", "owl", "fox"]

        x, y, _x_label, _y_label = resolve_series_xy(state, chart, "series", 0, coerce_numeric=False)

        assert list(x) == ["cat", "dog", "bird", "fish", "ant", "bee", "cow", "pig", "rat", "owl", "fox"]
        assert pd.api.types.is_numeric_dtype(y)
