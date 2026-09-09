"""
Command for running an analysis operation (derivative, integral, arc length,
smoothing, interpolation) on any series of a chart — a plotted data series or a
fitted curve — and storing the result as a new dataset, with undo/redo support.

Chart series come in two flavours:

* **data series** (:class:`DataSeries`) reference a dataset column by id; the
  x/y values are read live from that dataset.
* **fit series** (:class:`FitData`) carry their own resampled ``x_data`` /
  ``y_data`` arrays.

This command unifies both so the Chart Analysis panel can offer the full set of
analysis operations regardless of which kind of series the user picked.
"""

import uuid
from typing import Optional, override

import pandas as pd

from pandaplot.analysis import AnalysisEngine, AnalysisType
from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.chart.chart_finder import ChartFinder
from pandaplot.commands.project.chart.series_xy import (
    SourceKind,
    remove_result_dataset,
    resolve_series_xy,
    unique_sibling_name,
)
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.state import AppContext, AppState


class AnalyzeChartSeriesCommand(Command):
    """Analyze a chart series (data or fit) and add the result as a dataset."""

    def __init__(
        self,
        app_context: AppContext,
        chart_id: str,
        source_kind: SourceKind,
        source_index: int,
        analysis_type: AnalysisType,
        parameters: Optional[dict] = None,
        result_name: Optional[str] = None,
        folder_id: Optional[str] = None,
    ):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.chart_id = chart_id
        self.source_kind = source_kind
        self.source_index = source_index
        self.analysis_type = analysis_type
        self.parameters = parameters or {}
        self.result_name = result_name
        self.folder_id = folder_id

        # State for undo/redo.
        self.result_dataset_id: Optional[str] = None
        self._dataset: Optional[Dataset] = None

        # Cache for _resolve_xy_cached: the resolved series don't change over
        # the command's lifetime, and the UI calls it repeatedly (once per
        # segment bound, on every spinbox tick) to resolve/bound indices.
        self._resolved_xy_cache: Optional[tuple[pd.Series, pd.Series, str, str]] = None
        self._chart_finder = ChartFinder(app_context)

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
        ``_resolve_xy`` will actually produce — the raw dataset row count can
        be larger once rows with missing x/y are dropped.
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

    # -- analysis ---------------------------------------------------------

    def _run_engine(self, x: pd.Series, y: pd.Series):
        """Dispatch to the analysis engine for the configured operation."""
        start = self.parameters.get("start_index", 0)
        end = self.parameters.get("end_index", -1)
        method = self.parameters.get("method", "central")

        if self.analysis_type == AnalysisType.DERIVATIVE:
            return AnalysisEngine.calculate_derivative(x, y, method, start, end)
        if self.analysis_type == AnalysisType.INTEGRAL:
            return AnalysisEngine.calculate_integral(x, y, start, end)
        if self.analysis_type == AnalysisType.ARC_LENGTH:
            return AnalysisEngine.calculate_arc_length(x, y, start, end)
        if self.analysis_type == AnalysisType.SMOOTHING:
            extra = {k: v for k, v in self.parameters.items()
                     if k not in ("start_index", "end_index", "method")}
            return AnalysisEngine.smooth_data(x, y, method, start, end, **extra)
        if self.analysis_type == AnalysisType.INTERPOLATION:
            num_points = self.parameters.get("num_points")
            return AnalysisEngine.interpolate_data(x, y, method, num_points, start, end)
        raise ValueError(f"Unsupported analysis type: {self.analysis_type}")

    def _value_label(self, x_label: str, y_label: str) -> str:
        """Build a descriptive name for the result column."""
        if self.analysis_type == AnalysisType.DERIVATIVE:
            return f"d({y_label})/d{x_label}"
        if self.analysis_type == AnalysisType.INTEGRAL:
            return f"∫ {y_label} d{x_label}"
        if self.analysis_type == AnalysisType.ARC_LENGTH:
            return f"arc length of {y_label}"
        if self.analysis_type == AnalysisType.SMOOTHING:
            return f"{y_label} (smoothed)"
        if self.analysis_type == AnalysisType.INTERPOLATION:
            return f"{y_label} (interpolated)"
        return y_label

    def run_analysis(self) -> tuple[pd.DataFrame, str]:
        """Compute the analysis and return (result dataframe, default name).

        Raises ``ValueError`` if the chart/series is unavailable. Does not touch
        the project so the UI can call it for a preview.
        """
        chart = self._get_chart()
        if chart is None:
            raise ValueError("Chart is not available.")

        x, y, x_label, y_label = self._resolve_xy(chart)
        if len(x) < 2:
            raise ValueError("Series has too few points to analyze.")

        result = self._run_engine(x, y)
        value_label = self._value_label(x_label, y_label)

        results_df = pd.DataFrame({
            x_label: pd.Series(result.x_data).reset_index(drop=True),
            value_label: pd.Series(result.result_data).reset_index(drop=True),
        })
        op = self.analysis_type.value.replace("_", " ").title()
        default_name = f"{op} — {y_label}"
        return results_df, default_name

    # -- command ----------------------------------------------------------

    @override
    def execute(self) -> CommandResult:
        try:
            project = get_current_project(self.app_context)
            if project is None:
                message = "No project loaded; cannot analyze chart series."
                self.logger.warning(message)
                self.ui_controller.show_error_message("Chart Analysis Error", message)
                return CommandResult.FAILURE

            if self._dataset is None:
                results_df, default_name = self.run_analysis()
                unique_name = unique_sibling_name(project, self.folder_id, self.result_name or default_name)
                self.result_dataset_id = str(uuid.uuid4())
                self._dataset = Dataset(
                    id=self.result_dataset_id,
                    name=unique_name,
                    data=results_df,
                    source_file=None,
                )
            dataset = self._dataset

            project.add_item(dataset, parent_id=self.folder_id)
            reported_folder_id = (
                self.folder_id
                if self.folder_id is not None and project.find_item(self.folder_id) is not None
                else None
            )
            self.app_state.event_bus.emit(
                ProjectEvents.PROJECT_ITEM_ADDED,
                {
                    "project": project,
                    "item_id": dataset.id,
                    "item_type": "dataset",
                    "item_name": dataset.name,
                    "item": dataset,
                    "folder_id": reported_folder_id,
                },
            )

            self.logger.info("Created chart-analysis dataset '%s' (%s)", dataset.name, self.result_dataset_id)
            return CommandResult.SUCCESS

        except Exception as e:
            self.logger.error("Analyze-chart-series failed: %s", e, exc_info=True)
            self.ui_controller.show_error_message("Chart Analysis Error", str(e))
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        try:
            if not self.result_dataset_id or get_current_project(self.app_context) is None:
                return CommandResult.FAILURE
            remove_result_dataset(self.app_state, self.result_dataset_id)
            return CommandResult.SUCCESS
        except Exception as e:
            self.logger.error("Failed to undo analyze-chart-series: %s", e, exc_info=True)
            return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the cached resolved x/y series once this command is
        dropped from the stacks for good (see Command.cleanup)."""
        self._resolved_xy_cache = None
        self.result_dataset_id = None
        self._dataset = None
