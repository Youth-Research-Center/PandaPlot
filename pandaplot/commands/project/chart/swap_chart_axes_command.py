"""Command for swapping a chart's X and Y axes (#266)."""

from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.chart.chart_finder import ChartFinder
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events import ChartEvents
from pandaplot.models.state import AppContext


class SwapChartAxesCommand(Command):
    """Command that swaps a chart's X and Y axes via `Chart.swap_axes`.

    The swap is its own inverse, so undo and redo both just swap again.
    """

    def __init__(self, app_context: AppContext, chart_id: str):
        super().__init__()
        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.chart_id = chart_id
        self._chart_finder = ChartFinder(app_context)

    def _swap(self, *, report_errors: bool) -> CommandResult:
        chart = self._chart_finder.find(self.chart_id)
        if not chart:
            self.logger.warning("SwapChartAxesCommand: chart '%s' not found", self.chart_id)
            if report_errors:
                self.ui_controller.show_error_message("Swap Axes Error", f"Chart '{self.chart_id}' not found.")
            return CommandResult.FAILURE

        blocker = chart.swap_axes_blocker()
        if blocker is not None:
            self.logger.warning("SwapChartAxesCommand: cannot swap chart '%s': %s", self.chart_id, blocker)
            if report_errors:
                self.ui_controller.show_error_message("Swap Axes Error", blocker)
            return CommandResult.FAILURE

        chart.swap_axes()
        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            "chart_id": self.chart_id,
            "update_type": "axes_swapped",
            "chart": chart,
        })
        return CommandResult.SUCCESS

    @override
    def execute(self) -> CommandResult:
        return self._swap(report_errors=True)

    @override
    def undo(self) -> CommandResult:
        result = self._swap(report_errors=False)
        return CommandResult.ABORTED if result is CommandResult.FAILURE else result

    @override
    def redo(self) -> CommandResult:
        result = self._swap(report_errors=False)
        return CommandResult.ABORTED if result is CommandResult.FAILURE else result
