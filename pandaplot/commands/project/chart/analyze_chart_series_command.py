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
from typing import Literal, Optional, override

import numpy as np
import pandas as pd

from pandaplot.analysis import AnalysisEngine, AnalysisType
from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import DatasetEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart, resolve_series_column
from pandaplot.models.state import AppContext, AppState

SourceKind = Literal["series", "fit"]


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

        # Cache for _resolve_xy_cached: the resolved series don't change over
        # the command's lifetime, and the UI calls it repeatedly (once per
        # segment bound, on every spinbox tick) to resolve/bound indices.
        self._resolved_xy_cache: Optional[tuple[pd.Series, pd.Series, str, str]] = None

    # -- source resolution ------------------------------------------------

    def _get_chart(self) -> Optional[Chart]:
        project = self.app_state.current_project
        if not project:
            return None
        item = project.find_item(self.chart_id)
        return item if isinstance(item, Chart) else None

    def _resolve_xy(self, chart: Chart) -> tuple[pd.Series, pd.Series, str, str]:
        """Return (x, y, x_label, y_label) for the selected chart series."""
        if self.source_kind == "fit":
            if not (0 <= self.source_index < len(chart.fit_data)):
                raise ValueError("Selected fit no longer exists.")
            fit = chart.fit_data[self.source_index]
            dataset = self.app_state.current_project.find_item(fit.source_dataset_id)
            if not isinstance(dataset, Dataset):
                dataset = None
            x_label = resolve_series_column(dataset, fit.source_x_column_id, fit.source_x_column) or "x"
            x = pd.Series(np.asarray(fit.x_data), dtype="float64")
            y = pd.Series(np.asarray(fit.y_data), dtype="float64")
            return x, y, x_label, fit.label

        if not (0 <= self.source_index < len(chart.data_series)):
            raise ValueError("Selected series no longer exists.")
        series = chart.data_series[self.source_index]
        dataset = self.app_state.current_project.find_item(series.dataset_id)
        if not isinstance(dataset, Dataset) or dataset.data is None:
            raise ValueError("Series dataset is not available.")

        x_name = resolve_series_column(dataset, series.x_column_id, series.x_column)
        y_name = resolve_series_column(dataset, series.y_column_id, series.y_column)
        df = dataset.data
        if y_name is None or y_name not in df.columns:
            raise ValueError("Series y column not found.")

        if x_name and x_name in df.columns:
            x_full = df[x_name]
            x_label = x_name
        else:
            # No x column configured: analyze against the row index.
            x_full = pd.Series(np.arange(len(df)), index=df.index)
            x_label = "index"
        y_full = df[y_name]

        # Drop rows where either coordinate is missing so the maths is clean.
        mask = ~(pd.isna(x_full) | pd.isna(y_full))
        x = pd.to_numeric(x_full[mask], errors="coerce").reset_index(drop=True)
        y = pd.to_numeric(y_full[mask], errors="coerce").reset_index(drop=True)
        label = series.label or y_name
        return x, y, x_label, label

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
    def execute(self) -> bool:
        try:
            if not self.app_state.has_project or not self.app_state.current_project:
                message = "No project loaded; cannot analyze chart series."
                self.logger.warning(message)
                self.ui_controller.show_error_message("Chart Analysis Error", message)
                return False

            project = self.app_state.current_project
            results_df, default_name = self.run_analysis()
            name = self.result_name or default_name

            self.result_dataset_id = str(uuid.uuid4())
            dataset = Dataset(
                id=self.result_dataset_id,
                name=name,
                data=results_df,
                source_file=None,
            )
            project.add_item(dataset, parent_id=self.folder_id)

            self.app_state.event_bus.emit(DatasetEvents.DATASET_CREATED, {
                "project": project,
                "dataset_id": self.result_dataset_id,
                "dataset_name": name,
                "folder_id": self.folder_id,
                "dataset_data": dataset.data,
            })
            self.logger.info("Created chart-analysis dataset '%s' (%s)", name, self.result_dataset_id)
            return True

        except Exception as e:
            self.logger.error("Analyze-chart-series failed: %s", e, exc_info=True)
            self.ui_controller.show_error_message("Chart Analysis Error", str(e))
            return False

    @override
    def undo(self) -> bool:
        try:
            if not self.result_dataset_id or not self.app_state.current_project:
                return False
            project = self.app_state.current_project
            dataset = project.find_item(self.result_dataset_id)
            if dataset:
                project.remove_item(dataset)
                self.app_state.event_bus.emit(DatasetEvents.DATASET_DELETED, {
                    "project": project,
                    "dataset_id": self.result_dataset_id,
                    "dataset_name": dataset.name,
                })
            return True
        except Exception as e:
            self.logger.error("Failed to undo analyze-chart-series: %s", e, exc_info=True)
            return False

    @override
    def redo(self) -> bool:
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the cached resolved x/y series once this command is
        dropped from the stacks for good (see Command.cleanup)."""
        self._resolved_xy_cache = None
