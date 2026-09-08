"""Tests for ChartSignalAnalysisCommand: preview (run_analysis_async) and
commit (execute -> ApplySignalAnalysisResultCommand) paths, sourcing from a
chart data series or fit series instead of a plain dataset column."""

import logging
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.analysis import SignalAnalysisType
from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.commands.project.chart.chart_signal_analysis_command import (
    ChartSignalAnalysisCommand,
)
from pandaplot.commands.project.dataset.apply_signal_analysis_result_command import (
    ApplySignalAnalysisResultCommand,
)
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState
from tests.commands.project.conftest import SyncTaskScheduler


@pytest.fixture
def ctx():
    fs = 1000
    t = np.linspace(0, 1, fs, endpoint=False)
    signal = np.sin(2 * np.pi * 50 * t)

    project = Project(name="P")
    dataset = Dataset(id="ds-1", name="Signal Data", data=pd.DataFrame({"t": t, "signal": signal}))
    project.add_item(dataset)

    chart = Chart(id="chart-1", name="C")
    x_id = dataset.column_id("t")
    y_id = dataset.column_id("signal")
    chart.add_data_series(dataset_id="ds-1", x_column_id=x_id, y_column_id=y_id,
                          x_column="t", y_column="signal", label="Signal")
    chart.add_fit_data(source_dataset_id="ds-1", fit_type="custom",
                       x_data=t, y_data=signal, label="Signal Fit", source_x_column="t")
    project.add_item(chart)

    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = Mock()
    app_context.event_bus = app_state.event_bus

    app_context.get_app_state.return_value = app_state
    app_context.get_task_scheduler.return_value = SyncTaskScheduler()
    app_context.get_command_executor.return_value = CommandExecutor()

    return app_context, project


def _cmd(ctx, **kw):
    app_context, _ = ctx
    kw.setdefault("source_kind", "series")
    kw.setdefault("source_index", 0)
    kw.setdefault("analysis_type", SignalAnalysisType.FFT)
    kw.setdefault("sampling_rate", 1000)
    return ChartSignalAnalysisCommand(app_context, "chart-1", **kw)


class TestChartSignalAnalysisCommandCommitPath:
    def test_execute_adds_fft_results_dataset_for_data_series(self, ctx):
        _, project = ctx
        command = _cmd(ctx, source_kind="series", analysis_type=SignalAnalysisType.FFT, sampling_rate=1000)
        assert command.execute() is CommandResult.SUCCESS

        results = project.find_item(command.result_dataset_id)
        assert results is not None
        assert "Frequency (Hz)" in results.data.columns
        assert "Amplitude" in results.data.columns

    def test_execute_adds_fft_results_dataset_for_fit_series(self, ctx):
        _, project = ctx
        command = _cmd(ctx, source_kind="fit", analysis_type=SignalAnalysisType.FFT, sampling_rate=1000)
        assert command.execute() is CommandResult.SUCCESS

        results = project.find_item(command.result_dataset_id)
        assert results is not None
        assert "Frequency (Hz)" in results.data.columns

    def test_psd_runs_on_data_series(self, ctx):
        _, project = ctx
        command = _cmd(ctx, analysis_type=SignalAnalysisType.PSD, sampling_rate=1000)
        assert command.execute() is CommandResult.SUCCESS
        assert project.find_item(command.result_dataset_id) is not None

    def test_autocorrelation_runs(self, ctx):
        _, project = ctx
        command = _cmd(ctx, analysis_type=SignalAnalysisType.AUTOCORRELATION, sampling_rate=None)
        assert command.execute() is CommandResult.SUCCESS
        assert project.find_item(command.result_dataset_id) is not None

    def test_peaks_runs(self, ctx):
        _, project = ctx
        command = _cmd(ctx, analysis_type=SignalAnalysisType.PEAKS, sampling_rate=None)
        assert command.execute() is CommandResult.SUCCESS
        assert project.find_item(command.result_dataset_id) is not None

    def test_occupies_no_undo_slot(self, ctx):
        command = _cmd(ctx, analysis_type=SignalAnalysisType.PEAKS, sampling_rate=None)
        assert command.occupies_undo_slot() is False

    def test_marks_project_modified_is_false(self, ctx):
        command = _cmd(ctx)
        assert command.marks_project_modified() is False

    def test_undo_via_executor_removes_results_dataset(self, ctx):
        app_context, project = ctx
        executor: CommandExecutor = app_context.get_command_executor()
        command = _cmd(ctx, analysis_type=SignalAnalysisType.PEAKS, sampling_rate=None)

        assert executor.execute_command(command) is True
        assert isinstance(executor.undo_stack[-1], ApplySignalAnalysisResultCommand)

        new_id = command.result_dataset_id
        assert project.find_item(new_id) is not None

        assert executor.undo() is True
        assert project.find_item(new_id) is None

    def test_segment_restricts_range(self, ctx):
        """The segment must actually restrict what's analyzed: FFT bin
        spacing is sampling_rate / n, so a shorter segment produces a
        coarser (larger-spaced) frequency axis than the full range."""
        _, project = ctx
        full = _cmd(ctx, analysis_type=SignalAnalysisType.FFT, sampling_rate=1000)
        assert full.execute() is CommandResult.SUCCESS
        full_result = project.find_item(full.result_dataset_id)

        segment = _cmd(ctx, analysis_type=SignalAnalysisType.FFT, sampling_rate=1000,
                       parameters={"start_index": 0, "end_index": 200})
        assert segment.execute() is CommandResult.SUCCESS
        segment_result = project.find_item(segment.result_dataset_id)

        full_spacing = full_result.data["Frequency (Hz)"].iloc[1] - full_result.data["Frequency (Hz)"].iloc[0]
        segment_spacing = segment_result.data["Frequency (Hz)"].iloc[1] - segment_result.data["Frequency (Hz)"].iloc[0]
        assert segment_spacing == pytest.approx(full_spacing * (1000 / 200), rel=1e-2)

    def test_missing_source_index_fails_gracefully(self, ctx):
        app_context, _ = ctx
        command = _cmd(ctx, source_kind="fit", source_index=9)
        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_series_type_that_does_not_support_curve_analysis_fails(self, ctx):
        app_context, project = ctx
        chart = project.find_item("chart-1")
        chart.data_series[0].series_type = SeriesType.BAR
        command = _cmd(ctx, source_kind="series", source_index=0)

        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_execute_surfaces_no_project_loaded_to_the_user(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        app_state.has_project = False
        app_state.current_project = None
        app_context.get_app_state.return_value = app_state
        app_context.get_task_scheduler.return_value = SyncTaskScheduler()

        command = ChartSignalAnalysisCommand(
            app_context, "chart-1", "series", 0, SignalAnalysisType.FFT, sampling_rate=1000,
        )
        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_execute_fails_fast_when_already_running(self, ctx, caplog):
        command = _cmd(ctx)
        command._is_running = True

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "already in progress" in caplog.text

    def test_on_complete_reports_success(self, ctx):
        outcomes = []
        command = _cmd(ctx, on_complete=outcomes.append)
        assert command.execute() is CommandResult.SUCCESS
        assert outcomes == [CommandResult.SUCCESS]

    def test_redo_reuses_the_same_dataset_id(self, ctx):
        app_context, project = ctx
        executor: CommandExecutor = app_context.get_command_executor()
        command = _cmd(ctx, analysis_type=SignalAnalysisType.PEAKS, sampling_rate=None)

        assert executor.execute_command(command) is True
        original_id = command.result_dataset_id

        assert executor.undo() is True
        assert project.find_item(original_id) is None

        assert executor.redo() is True
        assert command.result_dataset_id == original_id
        assert project.find_item(original_id) is not None

    def test_project_changed_while_running_discards_the_result(self, ctx):
        app_context, project = ctx
        captured = {}
        fake_scheduler = Mock()
        fake_scheduler.run_task.side_effect = lambda **kwargs: captured.update(kwargs)
        app_context.get_task_scheduler.return_value = fake_scheduler

        command = _cmd(ctx, analysis_type=SignalAnalysisType.FFT, sampling_rate=1000)
        assert command.execute() is CommandResult.SUCCESS  # dispatched only

        # Simulate the user closing this project and opening another one
        # while the computation is still "running" in the background.
        app_context.get_app_state.return_value.current_project = Project(name="Other")

        outcome = captured["task"](lambda *_: None, **captured["task_arguments"])
        captured["on_result"](outcome)

        assert command.result_dataset_id is None
        app_context.get_ui_controller.return_value.show_warning_message.assert_called_once()
        assert all(not isinstance(item, Dataset) or item.id == "ds-1" for item in project.items_index.values())

    def test_cleanup_releases_cached_state(self, ctx):
        command = _cmd(ctx)
        command.source_length()  # populates _resolved_xy_cache
        assert command.execute() is CommandResult.SUCCESS
        assert command._resolved_xy_cache is not None
        assert command.result_dataset_id is not None
        assert command.result is not None

        command.cleanup()

        assert command._resolved_xy_cache is None
        assert command.result_dataset_id is None
        assert command.result is None


class TestChartSignalAnalysisCommandPreviewPath:
    def test_run_analysis_async_reports_result(self, ctx):
        command = _cmd(ctx)

        results = []
        errors = []
        command.run_analysis_async(lambda result, error: (results.append(result), errors.append(error)))

        assert errors == [None]
        assert results[0] is not None
        assert "Frequency (Hz)" in results[0].data.columns

    def test_run_analysis_async_reports_missing_source(self, ctx):
        command = _cmd(ctx, source_kind="fit", source_index=9)

        results = []
        errors = []
        command.run_analysis_async(lambda result, error: (results.append(result), errors.append(error)))

        assert results == [None]
        assert errors[0] is not None

    def test_run_analysis_async_does_not_touch_the_project(self, ctx):
        _, project = ctx
        before = len(project.get_all_items())

        command = _cmd(ctx)
        command.run_analysis_async(lambda result, error: None)

        assert len(project.get_all_items()) == before


class TestChartSignalAnalysisCommandSourceResolution:
    """source_length()/resolve_point() must behave identically to
    AnalyzeChartSeriesCommand's -- the UI reuses the exact segment-picker
    pattern for both commands."""

    def test_source_length_excludes_nan_rows(self, ctx):
        _, project = ctx
        dataset = project.find_item("ds-1")
        dataset.data.loc[3, "signal"] = np.nan
        command = _cmd(ctx, source_kind="series")
        assert command.source_length() == len(dataset.data) - 1

    def test_resolve_point_returns_xy_at_index(self, ctx):
        _, project = ctx
        dataset = project.find_item("ds-1")
        command = _cmd(ctx, source_kind="series")
        point = command.resolve_point(10)
        assert point == pytest.approx((dataset.data["t"].iloc[10], dataset.data["signal"].iloc[10]))

    def test_resolve_point_out_of_range_returns_none(self, ctx):
        _, project = ctx
        dataset = project.find_item("ds-1")
        command = _cmd(ctx, source_kind="series")
        assert command.resolve_point(len(dataset.data)) is None
        assert command.resolve_point(-1) is None

    def test_resolve_point_invalid_source_returns_none(self, ctx):
        command = _cmd(ctx, source_kind="fit", source_index=9)
        assert command.resolve_point(0) is None

    def test_cleanup_clears_the_resolved_xy_cache(self, ctx):
        command = _cmd(ctx, source_kind="series")
        command.source_length()  # populates _resolved_xy_cache
        assert command._resolved_xy_cache is not None

        command.cleanup()

        assert command._resolved_xy_cache is None


class TestResolveSegmentX:
    """resolve_segment_x() lets the UI derive a sampling-rate default from
    the segment's x spacing in one vectorized pass, backed by the same
    _resolved_xy_cache source_length()/resolve_point() share -- instead of
    looping resolve_point() once per index in the segment."""

    def test_returns_full_x_by_default(self, ctx):
        _, project = ctx
        dataset = project.find_item("ds-1")
        command = _cmd(ctx, source_kind="series")
        x_segment = command.resolve_segment_x()
        assert list(x_segment) == pytest.approx(list(dataset.data["t"]))

    def test_slices_to_the_requested_start_end(self, ctx):
        _, project = ctx
        dataset = project.find_item("ds-1")
        command = _cmd(ctx, source_kind="series")
        x_segment = command.resolve_segment_x(10, 20)
        assert list(x_segment) == pytest.approx(list(dataset.data["t"].iloc[10:20]))

    def test_reuses_the_resolved_xy_cache_across_calls(self, ctx):
        """Regression: the panel builds one command per (chart, source) and
        calls resolve_segment_x() repeatedly (once per segment-bound tick)
        -- it must hit the memoized cache, not re-resolve the series (NaN
        drop/to_numeric) every time."""
        command = _cmd(ctx, source_kind="series")
        command.resolve_segment_x(0, 5)
        cache_after_first_call = command._resolved_xy_cache
        assert cache_after_first_call is not None

        command.resolve_segment_x(5, 10)

        assert command._resolved_xy_cache is cache_after_first_call

    def test_invalid_source_returns_none(self, ctx):
        command = _cmd(ctx, source_kind="fit", source_index=9)
        assert command.resolve_segment_x() is None

    def test_no_chart_returns_none(self, ctx):
        command = _cmd(ctx, source_kind="series")
        command.chart_id = "not-a-real-chart"
        assert command.resolve_segment_x() is None


class TestChartSignalAnalysisCommandPlotResult:
    def test_plot_result_with_no_target_creates_a_new_chart(self, ctx):
        _, project = ctx
        command = _cmd(ctx, plot_result=True)

        assert command.execute() is CommandResult.SUCCESS

        original_chart = project.find_item("chart-1")
        assert len(original_chart.data_series) == 1  # untouched

        new_charts = [
            item for item in project.get_all_items()
            if isinstance(item, Chart) and item.id != "chart-1"
        ]
        assert len(new_charts) == 1
        assert len(new_charts[0].data_series) == 1
        assert new_charts[0].data_series[0].dataset_id == command.result_dataset_id

    def test_plot_result_with_target_chart_id_plots_on_that_chart(self, ctx):
        _, project = ctx
        other_chart = Chart(id="chart-2", name="Other")
        project.add_item(other_chart)

        command = _cmd(ctx, plot_result=True, plot_target_chart_id="chart-2")

        assert command.execute() is CommandResult.SUCCESS
        assert len(other_chart.data_series) == 1
        assert other_chart.data_series[0].dataset_id == command.result_dataset_id

    def test_plot_result_false_plots_nowhere(self, ctx):
        _, project = ctx
        command = _cmd(ctx, plot_result=False)

        assert command.execute() is CommandResult.SUCCESS
        assert all(
            isinstance(item, Chart) is False or item.id == "chart-1"
            for item in project.get_all_items()
        )


class TestChartSignalAnalysisCommandRealTaskScheduler:
    """Proves the background-thread -> main-thread callback delivery
    actually works end to end, mirroring
    TestSignalAnalysisCommandRealTaskScheduler."""

    def test_run_analysis_async_via_real_task_scheduler_delivers_result_on_main_thread(
        self, qtbot, ctx
    ):
        import threading

        from pandaplot.services.qtasks.task_scheduler import TaskScheduler

        app_context, _ = ctx
        app_context.get_task_scheduler.return_value = TaskScheduler()

        command = _cmd(ctx)

        main_thread = threading.current_thread()
        outcome = {}

        def _on_complete(result, error):
            outcome["result"] = result
            outcome["error"] = error
            outcome["thread"] = threading.current_thread()

        command.run_analysis_async(_on_complete)

        assert "thread" not in outcome

        qtbot.waitUntil(lambda: "thread" in outcome, timeout=5000)

        assert outcome["error"] is None
        assert outcome["result"] is not None
        assert "Frequency (Hz)" in outcome["result"].data.columns
        assert outcome["thread"] is main_thread
