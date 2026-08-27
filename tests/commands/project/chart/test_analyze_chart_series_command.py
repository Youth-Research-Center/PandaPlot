"""Tests for AnalyzeChartSeriesCommand (analysis on chart data + fit series)."""

from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.analysis import AnalysisType
from pandaplot.commands.project.chart.analyze_chart_series_command import (
    AnalyzeChartSeriesCommand,
)
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState


@pytest.fixture
def ctx():
    project = Project(name="P")

    # A source dataset with x = t, y = t^2.
    t = np.linspace(0.0, 10.0, 101)
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"t": t, "sq": t ** 2}))
    project.add_item(dataset)

    # A chart with one data series (bound by column id) and one fit curve.
    chart = Chart(id="chart-1", name="C")
    x_id = dataset.column_id("t")
    y_id = dataset.column_id("sq")
    chart.add_data_series(dataset_id="ds-1", x_column_id=x_id, y_column_id=y_id,
                          x_column="t", y_column="sq", label="Squared")
    chart.add_fit_data(source_dataset_id="ds-1", fit_type="quadratic",
                       x_data=t, y_data=t ** 2, label="Quadratic Fit", source_x_column="t")
    project.add_item(chart)

    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = Mock()
    app_context.get_app_state.return_value = app_state
    return app_context, project


def _cmd(ctx, **kw):
    app_context, _ = ctx
    kw.setdefault("source_kind", "series")
    kw.setdefault("source_index", 0)
    kw.setdefault("analysis_type", AnalysisType.DERIVATIVE)
    return AnalyzeChartSeriesCommand(app_context, "chart-1", **kw)


class TestAnalyzeChartSeriesCommand:
    def test_derivative_on_data_series(self, ctx):
        _, project = ctx
        command = _cmd(ctx, source_kind="series", analysis_type=AnalysisType.DERIVATIVE)
        assert command.execute() is True
        result = project.find_item(command.result_dataset_id)
        assert "t" in result.data.columns
        deriv_col = [c for c in result.data.columns if c != "t"][0]
        mid = len(result.data) // 2
        # d/dt of t^2 = 2t.
        assert result.data[deriv_col].iloc[mid] == pytest.approx(2 * result.data["t"].iloc[mid], abs=0.2)

    def test_integral_on_fit_series(self, ctx):
        _, project = ctx
        command = _cmd(ctx, source_kind="fit", analysis_type=AnalysisType.INTEGRAL)
        assert command.execute() is True
        result = project.find_item(command.result_dataset_id)
        int_col = [c for c in result.data.columns if c != "t"][0]
        assert result.data[int_col].iloc[-1] == pytest.approx(1000 / 3, rel=1e-3)

    def test_cleanup_clears_the_resolved_xy_cache(self, ctx):
        command = _cmd(ctx, source_kind="series", analysis_type=AnalysisType.DERIVATIVE)
        command.source_length()  # populates _resolved_xy_cache
        assert command._resolved_xy_cache is not None

        command.cleanup()

        assert command._resolved_xy_cache is None

    def test_arc_length_on_fit_series(self, ctx):
        _, project = ctx
        command = _cmd(ctx, source_kind="fit", analysis_type=AnalysisType.ARC_LENGTH)
        assert command.execute() is True
        result = project.find_item(command.result_dataset_id)
        arc_col = [c for c in result.data.columns if c != "t"][0]
        exact = 0.5 * (10 * np.sqrt(1 + 400) + 0.5 * np.arcsinh(20))
        assert result.data[arc_col].iloc[-1] == pytest.approx(exact, rel=1e-3)

    def test_segment_restricts_range(self, ctx):
        _, project = ctx
        command = _cmd(ctx, source_kind="series", analysis_type=AnalysisType.INTEGRAL,
                       parameters={"start_index": 0, "end_index": 51})
        assert command.execute() is True
        result = project.find_item(command.result_dataset_id)
        assert len(result.data) == 51
        assert result.data["t"].iloc[-1] == pytest.approx(5.0)

    def test_smoothing_runs(self, ctx):
        _, project = ctx
        command = _cmd(ctx, source_kind="series", analysis_type=AnalysisType.SMOOTHING,
                       parameters={"method": "rolling_mean", "window": 5})
        assert command.execute() is True
        assert project.find_item(command.result_dataset_id) is not None

    def test_interpolation_resamples(self, ctx):
        _, project = ctx
        command = _cmd(ctx, source_kind="series", analysis_type=AnalysisType.INTERPOLATION,
                       parameters={"method": "linear", "num_points": 250})
        assert command.execute() is True
        result = project.find_item(command.result_dataset_id)
        assert len(result.data) == 250

    def test_custom_result_name(self, ctx):
        _, project = ctx
        command = _cmd(ctx, result_name="My Derivative")
        assert command.execute() is True
        assert project.find_item(command.result_dataset_id).name == "My Derivative"

    def test_undo_removes_dataset(self, ctx):
        _, project = ctx
        command = _cmd(ctx)
        command.execute()
        new_id = command.result_dataset_id
        assert project.find_item(new_id) is not None
        assert command.undo() is True
        assert project.find_item(new_id) is None

    def test_invalid_source_index_fails(self, ctx):
        app_context, _ = ctx
        command = _cmd(ctx, source_kind="fit", source_index=9)
        assert command.execute() is False
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_execute_surfaces_no_project_loaded_to_the_user(self, ctx):
        app_context, _ = ctx
        app_context.get_app_state.return_value.has_project = False
        app_context.get_app_state.return_value.current_project = None
        command = _cmd(ctx)
        assert command.execute() is False
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_source_length_excludes_nan_rows(self, ctx):
        _, project = ctx
        dataset = project.find_item("ds-1")
        # Two of 101 rows become unanalyzable once a y value goes missing.
        dataset.data.loc[3, "sq"] = np.nan
        command = _cmd(ctx, source_kind="series")
        assert command.source_length() == len(dataset.data) - 1

    def test_fit_source_dataset_of_wrong_type_does_not_raise(self, ctx):
        _, project = ctx
        chart = project.find_item("chart-1")
        # Point the fit at a non-Dataset item id (the chart itself) to
        # simulate a stale/mistyped reference.
        chart.fit_data[0].source_dataset_id = "chart-1"
        command = _cmd(ctx, source_kind="fit", analysis_type=AnalysisType.INTEGRAL)
        assert command.execute() is True

    def test_resolve_point_returns_xy_at_index(self, ctx):
        command = _cmd(ctx, source_kind="series")
        point = command.resolve_point(10)
        assert point == pytest.approx((1.0, 1.0))

    def test_resolve_point_out_of_range_returns_none(self, ctx):
        command = _cmd(ctx, source_kind="series")
        assert command.resolve_point(101) is None
        assert command.resolve_point(-1) is None

    def test_resolve_point_invalid_source_returns_none(self, ctx):
        command = _cmd(ctx, source_kind="fit", source_index=9)
        assert command.resolve_point(0) is None
