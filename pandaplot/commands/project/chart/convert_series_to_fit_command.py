"""Command for converting a data series into a FIT-type DataSeries on a chart."""

import copy
from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.chart.chart_finder import ChartFinder
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.events import ChartEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import (
    DataSeries,
    resolve_manual_fit_source_data,
)
from pandaplot.models.state import AppContext


class ConvertSeriesToFitCommand(Command):
    """Command to convert an existing DataSeries into a SeriesType.FIT
    DataSeries (#298, unified onto DataSeries by #304).

    Snapshots the source dataset's X/Y (and optional confidence lower/
    upper) columns into precomputed_x_data/precomputed_y_data and
    style.confidence_lower/confidence_upper at the moment of conversion --
    matching ApplyFitCommand's existing behavior where a fit's data is a
    snapshot, not a live reference (unlike an ordinary DataSeries, which
    resolves column ids live). Error-bar/vector/Z columns configured on
    the source series are dropped -- a FIT series' style has no such
    concepts.
    """

    def __init__(
        self,
        app_context: AppContext,
        chart_id: str,
        series_index: int,
        confidence_lower_column_id: str = "",
        confidence_upper_column_id: str = "",
    ):
        super().__init__()
        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.chart_id = chart_id
        self.series_index = series_index
        self.confidence_lower_column_id = confidence_lower_column_id
        self.confidence_upper_column_id = confidence_upper_column_id

        # State for undo/redo, mirroring ApplyFitCommand's caching: the
        # FIT-type DataSeries is built once (first execute()) and reused
        # on redo, and the original series is snapshotted once so undo
        # can put it back in the same data_series slot.
        self.removed_series: DataSeries | None = None
        self._fit: DataSeries | None = None
        self._chart_finder = ChartFinder(app_context)

    def _find_dataset(self, dataset_id: str) -> Dataset | None:
        app_state = self.app_context.get_app_state()
        project = app_state.current_project if app_state.has_project else None
        if project is None:
            return None
        dataset = project.find_item(dataset_id)
        return dataset if isinstance(dataset, Dataset) else None

    def _build_fit(self, series: DataSeries) -> DataSeries | None:
        dataset = self._find_dataset(series.dataset_id)
        resolved = resolve_manual_fit_source_data(
            dataset,
            series.x_column_id,
            series.y_column_id,
            self.confidence_lower_column_id,
            self.confidence_upper_column_id,
        )
        if resolved is None:
            return None
        x_data, y_data, confidence_lower, confidence_upper = resolved

        style = FitStyle(
            fit_type="Custom",
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
            confidence_lower_column_id=self.confidence_lower_column_id,
            confidence_upper_column_id=self.confidence_upper_column_id,
            is_manual=True,
        )
        return DataSeries(
            dataset_id=series.dataset_id,
            x_column_id=series.x_column_id, y_column_id=series.y_column_id,
            x_column=series.x_column, y_column=series.y_column,
            label=series.label or "Custom Fit",
            visible=series.visible,
            y_axis=series.y_axis,
            alpha=series.alpha,
            series_type=SeriesType.FIT,
            style=style,
            precomputed_x_data=x_data, precomputed_y_data=y_data,
        )

    @override
    def execute(self) -> CommandResult:
        chart = self._chart_finder.find(self.chart_id)
        if chart is None:
            self.logger.warning(
                "ConvertSeriesToFitCommand.execute: chart '%s' not found or not a Chart",
                self.chart_id,
            )
            self.ui_controller.show_error_message(
                "Convert to Fit Error", f"Chart '{self.chart_id}' not found."
            )
            return CommandResult.FAILURE

        if self.series_index < 0 or self.series_index >= len(chart.data_series):
            self.logger.warning(
                "ConvertSeriesToFitCommand.execute: series_index %s out of range for "
                "chart '%s' (%d series)",
                self.series_index, self.chart_id, len(chart.data_series),
            )
            self.ui_controller.show_error_message(
                "Convert to Fit Error", f"Series index {self.series_index} is out of range."
            )
            return CommandResult.FAILURE

        series = chart.data_series[self.series_index]

        if series.series_type == SeriesType.FIT:
            # Re-converting would re-snapshot the fit's source columns and
            # silently replace its curve/fit_type/fit_params with raw data.
            # Checked before the allows_fit guard below: "already a fit" is
            # the more specific, more useful error even on a chart type
            # that also happens to disallow fits (round-2 review, Minor 5).
            self.logger.warning(
                "ConvertSeriesToFitCommand.execute: series at index %s on chart '%s' is already a fit",
                self.series_index, self.chart_id,
            )
            self.ui_controller.show_error_message("Convert to Fit Error", "That entry is already a fit.")
            return CommandResult.FAILURE

        spec = CHART_TYPE_SPECS[chart.chart_type]
        if not spec.allows_fit:
            self.logger.warning(
                "ConvertSeriesToFitCommand.execute: chart '%s' is a %s chart, which doesn't allow fits",
                self.chart_id, spec.display_name,
            )
            self.ui_controller.show_error_message(
                "Convert to Fit Error", f"Fits aren't available on {spec.display_name} charts."
            )
            return CommandResult.FAILURE

        if self._fit is None:
            fit = self._build_fit(series)
            if fit is None:
                self.logger.warning(
                    "ConvertSeriesToFitCommand.execute: could not resolve source data "
                    "for series at index %s on chart '%s'",
                    self.series_index, self.chart_id,
                )
                self.ui_controller.show_error_message(
                    "Convert to Fit Error", "Could not read the series' source data."
                )
                return CommandResult.FAILURE
            self._fit = fit
            self.removed_series = copy.deepcopy(series)

        # A straight slot swap, not remove+insert: the fit takes over the
        # series' position, so nothing else in data_series moves (and no
        # other series' fill_to_index needs remapping).
        chart.data_series[self.series_index] = self._fit
        chart.update_modified_time()

        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            "chart_id": self.chart_id,
            "update_type": "series_converted_to_fit",
            "chart": chart,
        })
        return CommandResult.SUCCESS

    @override
    def undo(self) -> CommandResult:
        chart = self._chart_finder.find(self.chart_id)
        if chart is None or self.removed_series is None or not (0 <= self.series_index < len(chart.data_series)):
            self.logger.warning(
                "ConvertSeriesToFitCommand.undo: cannot undo for chart '%s' (chart "
                "found=%s, removed_series set=%s, series_index=%s)",
                self.chart_id, chart is not None, self.removed_series is not None, self.series_index,
            )
            return CommandResult.FAILURE

        chart.data_series[self.series_index] = copy.deepcopy(self.removed_series)
        chart.update_modified_time()

        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            "chart_id": self.chart_id,
            "update_type": "fit_converted_to_series",
            "chart": chart,
        })
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        # Check the allows_fit guard *before* falling into execute()'s
        # shared logic: if the chart's type changed to a disallowed one
        # between the original execute/undo and this redo (round-2 review,
        # Minor 2), execute() would return FAILURE, which CommandExecutor
        # still pushes onto the undo stack -- a later undo of that phantom
        # entry would then act on self.series_index against whatever is
        # really at that position now. ABORTED instead leaves this command
        # on the redo stack untouched, as if this call never happened.
        chart = self._chart_finder.find(self.chart_id)
        if chart is not None:
            spec = CHART_TYPE_SPECS[chart.chart_type]
            if not spec.allows_fit:
                self.logger.warning(
                    "ConvertSeriesToFitCommand.redo: chart '%s' is now a %s chart, which doesn't allow fits -- refusing without touching it",
                    self.chart_id, spec.display_name,
                )
                self.ui_controller.show_error_message(
                    "Convert to Fit Error", f"Fits aren't available on {spec.display_name} charts."
                )
                return CommandResult.ABORTED
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the removed-series/fit bookkeeping held for undo
        once this command is dropped from the stacks for good (see
        Command.cleanup)."""
        self.removed_series = None
        self._fit = None
