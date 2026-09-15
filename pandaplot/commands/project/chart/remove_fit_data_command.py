"""Command for removing fit data from a chart."""

import copy
from typing import Optional, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.chart.chart_finder import ChartFinder
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events import ChartEvents
from pandaplot.models.project.items.chart import FitData
from pandaplot.models.state import AppContext


class RemoveFitDataCommand(Command):
    """Command to remove fit data from an existing chart."""

    def __init__(self, app_context: AppContext, chart_id: str, fit_index: int):
        super().__init__()
        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.chart_id = chart_id
        self.fit_index = fit_index
        self.removed_fit_data: Optional[FitData] = None
        self._chart_finder = ChartFinder(app_context)

    @override
    def execute(self) -> CommandResult:
        chart = self._chart_finder.find(self.chart_id)
        if not chart:
            self.logger.warning(
                "RemoveFitDataCommand.execute: chart '%s' not found",
                self.chart_id,
            )
            self.ui_controller.show_error_message(
                "Remove Fit Error", f"Chart '{self.chart_id}' not found."
            )
            return CommandResult.FAILURE

        if self.fit_index < 0 or self.fit_index >= len(chart.fit_data):
            self.logger.warning(
                "RemoveFitDataCommand.execute: fit_index %s out of range for chart '%s' (%d fits)",
                self.fit_index, self.chart_id, len(chart.fit_data),
            )
            self.ui_controller.show_error_message(
                "Remove Fit Error", f"Fit index {self.fit_index} is out of range."
            )
            return CommandResult.FAILURE

        # Snapshot the fit data before removing
        fit = chart.fit_data[self.fit_index]
        self.removed_fit_data = copy.deepcopy(fit)

        chart.remove_fit_data(self.fit_index)

        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            "chart_id": self.chart_id,
            "update_type": "fit_removed",
            "chart": chart,
        })
        return CommandResult.SUCCESS

    @override
    def undo(self) -> CommandResult:
        chart = self._chart_finder.find(self.chart_id)
        if not chart or self.removed_fit_data is None:
            self.logger.warning(
                "RemoveFitDataCommand.undo: cannot undo for chart '%s' (chart found=%s, removed_fit_data set=%s)",
                self.chart_id, chart is not None, self.removed_fit_data is not None,
            )
            return CommandResult.FAILURE

        # Re-create and insert at original position
        fit = copy.deepcopy(self.removed_fit_data)
        chart.fit_data.insert(self.fit_index, fit)
        chart.update_modified_time()

        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            "chart_id": self.chart_id,
            "update_type": "fit_added",
            "chart": chart,
        })
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the removed fit-data snapshot held for undo once this
        command is dropped from the stacks for good (see Command.cleanup)."""
        self.removed_fit_data = None
