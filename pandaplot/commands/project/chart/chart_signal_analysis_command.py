"""
Command for running a signal analysis (FFT/STFT/PSD/Autocorrelation/Peak
detection) on a chart series (a plotted data series, or a fitted curve),
on a background thread.

This mirrors SignalAnalysisCommand's async pattern (see
pandaplot/commands/project/dataset/signal_analysis_command.py), but sources
its input from a chart series/fit -- via ChartFinder/resolve_series_xy,
exactly like AnalyzeChartSeriesCommand -- instead of a dataset column, and
adds segment slicing (start_index/end_index), a capability
SignalEngine.run_analysis has no parameters of its own for.

`run_analysis_async` drives the non-undoable preview path; `execute` drives
the undo-tracked "Add to Project" path, dispatching the same computation and
then -- once the result is back -- running ApplySignalAnalysisResultCommand,
which is the command that actually occupies an undo slot.
"""

from typing import Any, Callable, Dict, Optional, override

import pandas as pd

from pandaplot.analysis import (
    SignalAnalysisResult,
    SignalAnalysisType,
    SignalEngine,
)
from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.composite_command import CompositeCommand
from pandaplot.commands.project.chart.add_analysis_series_command import AddAnalysisSeriesCommand
from pandaplot.commands.project.chart.chart_finder import ChartFinder
from pandaplot.commands.project.chart.series_xy import SourceKind, resolve_series_xy
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.commands.project.dataset.apply_signal_analysis_result_command import (
    ApplySignalAnalysisResultCommand,
)
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.state import AppContext, AppState


class ChartSignalAnalysisCommand(Command):
    """
    Runs a signal analysis on a chart series/fit (optionally restricted to a
    segment), either as a non-undoable preview (run_analysis_async) or
    committed as a new project dataset (execute).
    """

    def __init__(
        self,
        app_context: AppContext,
        chart_id: str,
        source_kind: SourceKind,
        source_index: int,
        analysis_type: SignalAnalysisType,
        sampling_rate: Optional[float] = None,
        parameters: Optional[Dict[str, Any]] = None,
        result_name: Optional[str] = None,
        folder_id: Optional[str] = None,
        *,
        plot_result: bool = False,
        on_complete: Optional[Callable[[CommandResult], None]] = None,
    ):
        super().__init__()

        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.task_scheduler = app_context.get_task_scheduler()

        self.chart_id = chart_id
        self.source_kind = source_kind
        self.source_index = source_index
        self.analysis_type = analysis_type
        self.sampling_rate = sampling_rate
        self.parameters = parameters or {}

        self.result_name = result_name
        self.folder_id = folder_id
        self.plot_result = plot_result
        self.on_complete = on_complete

        self.result_dataset_id: Optional[str] = None
        self.result: Optional[SignalAnalysisResult] = None
        self._is_running = False
        # The project active at dispatch time, so a project switch while the
        # computation runs in the background can be detected and the result
        # rejected instead of silently landing in whatever project happens
        # to be current when the background thread finishes.
        self._dispatch_project = None

        # Cache for _resolve_xy_cached: the resolved series don't change over
        # the command's lifetime, and the UI calls it repeatedly (once per
        # segment bound, on every spinbox tick) to resolve/bound indices.
        self._resolved_xy_cache: Optional[tuple[pd.Series, pd.Series, str, str]] = None
        self._chart_finder = ChartFinder(app_context)

    @override
    def marks_project_modified(self) -> bool:
        """execute() only dispatches the computation -- it returns SUCCESS
        before anything has actually mutated the project, and the
        dispatched computation may yet fail or be discarded (see
        _on_commit_computed). The real mutation, and the real "unsaved
        changes" flag, belongs to ApplySignalAnalysisResultCommand alone."""
        return False

    @override
    def occupies_undo_slot(self) -> bool:
        """The real, undoable effect is ApplySignalAnalysisResultCommand,
        executed once the background computation's result is back (see
        _on_commit_computed)."""
        return False

    # -- source resolution ------------------------------------------------

    def _get_chart(self) -> Optional[Chart]:
        return self._chart_finder.find(self.chart_id)

    def _resolve_xy(self, chart: Chart) -> tuple[pd.Series, pd.Series, str, str]:
        """Return (x, y, x_label, y_label) for the selected chart series."""
        return resolve_series_xy(self.app_state, chart, self.source_kind, self.source_index)

    def _resolve_xy_cached(self, chart: Chart) -> tuple[pd.Series, pd.Series, str, str]:
        """``_resolve_xy``, memoized for the lifetime of this command.

        ``source_length``/``resolve_point`` are called repeatedly by the UI
        (once per segment bound, on every spinbox tick); re-running the
        NaN-dropping/``to_numeric`` work on every call is wasted since the
        resolved series can't change within a single command instance.
        """
        if self._resolved_xy_cache is None:
            self._resolved_xy_cache = self._resolve_xy(chart)
        return self._resolved_xy_cache

    def source_length(self) -> int:
        """Best-effort length of the resolved series, after NaN-dropping.

        Used by the UI to bound the segment start/end indices to what
        ``_resolve_xy`` will actually produce -- the raw dataset row count
        can be larger once rows with missing x/y are dropped.
        """
        try:
            chart = self._get_chart()
            if chart is None:
                return 0
            x, _y, _x_label, _y_label = self._resolve_xy_cached(chart)
            return len(x)
        except (ValueError, AttributeError):
            return 0

    def resolve_point(self, index: int) -> Optional[tuple[float, float]]:
        """Return the resolved (x, y) at a source-series index, or None.

        Used by the UI to show the actual data point a segment start/end
        index refers to, on the same resolved series ``source_length`` uses.
        """
        try:
            chart = self._get_chart()
            if chart is None:
                return None
            x, y, _x_label, _y_label = self._resolve_xy_cached(chart)
            if not (0 <= index < len(x)):
                return None
            return float(x.iloc[index]), float(y.iloc[index])
        except (ValueError, AttributeError):
            return None

    def resolve_segment_x(self, start: int = 0, end: Optional[int] = None) -> Optional[pd.Series]:
        """Return the resolved x values for the [start:end) segment (the
        same exclusive-end convention as parameters["end_index"]), or None
        if the chart/series is unavailable.

        Takes start/end explicitly rather than reading self.parameters, so
        the UI can reuse one cached command instance to inspect several
        candidate segments (e.g. while the user is still dragging a spinbox)
        without mutating it. Used to derive a sampling-rate default from
        the segment's x spacing in one vectorized pass, instead of looping
        resolve_point() once per index in the segment -- backed by the same
        _resolved_xy_cache source_length()/resolve_point() share.
        """
        try:
            chart = self._get_chart()
            if chart is None:
                return None
            x, _y, _x_label, _y_label = self._resolve_xy_cached(chart)
        except (ValueError, AttributeError):
            return None
        return x.iloc[start:end]

    # -- analysis -----------------------------------------------------------

    def _resolve_segment(self, chart: Chart) -> pd.Series:
        """Resolve the chart series' y values and slice them to the
        configured segment (start_index/end_index), with .name set to the
        resolved y-label so SignalAnalysisResult.source_columns reads
        correctly -- a chart series may have a custom label distinct from
        the underlying dataset column name."""
        _x, y, _x_label, y_label = self._resolve_xy(chart)
        start = self.parameters.get("start_index", 0)
        end = self.parameters.get("end_index")
        y_segment = y.iloc[start:end].reset_index(drop=True)
        y_segment.name = y_label
        return y_segment

    def _extra_kwargs(self) -> Dict[str, Any]:
        """Signal-specific kwargs for SignalEngine.run_analysis: everything
        in `parameters` except the segment bounds, which are consumed here
        rather than passed through (SignalEngine has no such parameters)."""
        return {k: v for k, v in self.parameters.items() if k not in ("start_index", "end_index")}

    def _compute_signal_task(self, progress_callback, column: pd.Series) -> dict:
        """Runs on a background thread. Never raises for an expected
        computation failure; returns a plain dict instead."""
        try:
            result = SignalEngine.run_analysis(
                analysis_type=self.analysis_type,
                column=column,
                sampling_rate=self.sampling_rate,
                **self._extra_kwargs(),
            )
            return {"success": True, "result": result, "error": None}
        except Exception as e:
            self.logger.error("Chart signal analysis computation failed: %s", e, exc_info=True)
            return {"success": False, "result": None, "error": str(e)}

    def run_analysis_async(self, on_complete: Callable[[Optional[SignalAnalysisResult], Optional[str]], None]) -> None:
        """Non-undoable preview path: computes a SignalAnalysisResult on a
        background thread and reports it (or an error message) via
        on_complete(result, error). Does not touch the project."""
        try:
            chart = self._get_chart()
            if chart is None:
                on_complete(None, "Chart is not available.")
                return
            y_segment = self._resolve_segment(chart)
        except ValueError as e:
            on_complete(None, str(e))
            return

        def _on_result(outcome: dict) -> None:
            if outcome["success"]:
                self.result = outcome["result"]
                on_complete(self.result, None)
            else:
                self.result = None
                on_complete(None, outcome["error"])

        def _on_error(error_info) -> None:
            _, value, _ = error_info
            self.result = None
            on_complete(None, str(value))

        self.task_scheduler.run_task(
            task=self._compute_signal_task,
            task_arguments={"column": y_segment},
            on_result=_on_result,
            on_error=_on_error,
        )

    @override
    def execute(self) -> CommandResult:
        """Commit path ("Add to Project"): validate, dispatch the
        computation, and return SUCCESS once dispatched -- not once the
        dataset is actually created; use on_complete for that."""
        try:
            self.logger.info("Executing ChartSignalAnalysisCommand (%s)", self.analysis_type.value)

            if self._is_running:
                self.logger.warning("Chart signal analysis already in progress")
                return CommandResult.FAILURE

            if get_current_project(self.app_context) is None:
                message = "No project loaded; cannot run chart signal analysis."
                self.logger.warning(message)
                self.ui_controller.show_error_message("Chart Signal Analysis Error", message)
                return CommandResult.FAILURE

            chart = self._get_chart()
            if chart is None:
                message = "Chart is not available."
                self.logger.warning(message)
                self.ui_controller.show_error_message("Chart Signal Analysis Error", message)
                return CommandResult.FAILURE

            try:
                y_segment = self._resolve_segment(chart)
            except ValueError as e:
                message = str(e)
                self.logger.warning(message)
                self.ui_controller.show_error_message("Chart Signal Analysis Error", message)
                return CommandResult.FAILURE

            self._dispatch_project = self.app_state.current_project
            self._is_running = True
            self.task_scheduler.run_task(
                task=self._compute_signal_task,
                task_arguments={"column": y_segment},
                on_result=self._on_commit_computed,
                on_error=self._on_commit_error,
                on_finished=self._on_commit_finished,
            )
            return CommandResult.SUCCESS

        except Exception as e:
            self.logger.error("Chart signal analysis failed: %s", e, exc_info=True)
            self.ui_controller.show_error_message("Chart Signal Analysis Error", str(e))
            self._is_running = False
            return CommandResult.FAILURE

    def _on_commit_computed(self, outcome: dict) -> None:
        if not outcome["success"]:
            self.ui_controller.show_error_message(
                "Chart Signal Analysis Error", outcome["error"] or "Chart signal analysis failed",
            )
            self._notify_complete(CommandResult.FAILURE)
            return

        if self.app_state.current_project is not self._dispatch_project:
            # The project changed (or was closed) while this computation was
            # running in the background -- adding the result to whatever
            # project happens to be current now would silently attach it to
            # the wrong project.
            message = "The project changed while the chart signal analysis was running. The result was discarded."
            self.logger.warning(message)
            self.ui_controller.show_warning_message("Chart Signal Analysis Cancelled", message)
            self._notify_complete(CommandResult.FAILURE)
            return

        apply_command = ApplySignalAnalysisResultCommand(
            self.app_context, self.result_name, self.folder_id, outcome["result"],
        )
        executor = self.app_context.get_command_executor()

        if self.plot_result:
            add_series_cmd = AddAnalysisSeriesCommand(
                app_context=self.app_context,
                chart_id=self.chart_id,
                dataset_command=apply_command,
            )
            composite = CompositeCommand([apply_command, add_series_cmd])
            success = executor.execute_command(composite)
        else:
            success = executor.execute_command(apply_command)

        if success:
            self.result = outcome["result"]
            self.result_dataset_id = apply_command.result_dataset_id
            self._notify_complete(CommandResult.SUCCESS)
        else:
            self._notify_complete(CommandResult.FAILURE)

    def _on_commit_error(self, error_info) -> None:
        error_type, error_value, error_traceback = error_info
        message = f"Chart signal analysis failed with {error_type.__name__}: {error_value}"
        self.logger.error(message)
        self.logger.error(error_traceback)
        self.ui_controller.show_error_message("Chart Signal Analysis Error", message)
        self._notify_complete(CommandResult.FAILURE)

    def _on_commit_finished(self) -> None:
        self._is_running = False

    def _notify_complete(self, result: CommandResult) -> None:
        if self.on_complete:
            self.on_complete(result)

    @override
    def undo(self) -> CommandResult:
        """Unreachable via CommandExecutor: occupies_undo_slot() is False."""
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        return CommandResult.SUCCESS

    @override
    def cleanup(self) -> None:
        self._resolved_xy_cache = None
        self.result_dataset_id = None
        self.result = None
