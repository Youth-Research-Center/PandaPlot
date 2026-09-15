"""Command for removing a data series from a chart."""

import copy
from typing import Optional, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.chart.chart_finder import ChartFinder
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events import ChartEvents
from pandaplot.models.project.items.chart import DataSeries
from pandaplot.models.state import AppContext


class RemoveSeriesCommand(Command):
    """Command to remove a data series from an existing chart."""

    def __init__(self, app_context: AppContext, chart_id: str, series_index: int):
        super().__init__()
        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.chart_id = chart_id
        self.series_index = series_index
        self.removed_series_data: Optional[DataSeries] = None
        self._chart_finder = ChartFinder(app_context)

    @override
    def execute(self) -> CommandResult:
        chart = self._chart_finder.find(self.chart_id)
        if not chart:
            self.logger.warning(
                "RemoveSeriesCommand.execute: chart '%s' not found",
                self.chart_id,
            )
            self.ui_controller.show_error_message(
                "Remove Series Error", f"Chart '{self.chart_id}' not found."
            )
            return CommandResult.FAILURE

        if self.series_index < 0 or self.series_index >= len(chart.data_series):
            self.logger.warning(
                "RemoveSeriesCommand.execute: series_index %s out of range for chart '%s' (%d series)",
                self.series_index, self.chart_id, len(chart.data_series),
            )
            self.ui_controller.show_error_message(
                "Remove Series Error", f"Series index {self.series_index} is out of range."
            )
            return CommandResult.FAILURE

        # Snapshot the series before removing
        series = chart.data_series[self.series_index]
        self.removed_series_data = copy.deepcopy(series)

        chart.remove_data_series(self.series_index)

        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            "chart_id": self.chart_id,
            "update_type": "series_removed",
            "chart": chart,
        })
        return CommandResult.SUCCESS

    @override
    def undo(self) -> CommandResult:
        chart = self._chart_finder.find(self.chart_id)
        if not chart or self.removed_series_data is None:
            self.logger.warning(
                "RemoveSeriesCommand.undo: cannot undo for chart '%s' (chart found=%s, removed_series_data set=%s)",
                self.chart_id, chart is not None, self.removed_series_data is not None,
            )
            return CommandResult.FAILURE

        # Re-create and insert at original position
        series = copy.deepcopy(self.removed_series_data)
        chart.data_series.insert(self.series_index, series)
        chart.update_modified_time()

        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            "chart_id": self.chart_id,
            "update_type": "series_added",
            "chart": chart,
        })
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the removed series-data snapshot held for undo once this
        command is dropped from the stacks for good (see Command.cleanup)."""
        self.removed_series_data = None
