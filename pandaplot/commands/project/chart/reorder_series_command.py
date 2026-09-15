"""Command for reordering a data series within a chart (controls z-index)."""

from typing import override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.chart.chart_finder import ChartFinder
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events import ChartEvents
from pandaplot.models.state import AppContext


class ReorderSeriesCommand(Command):
    """Command to move a data series from one position to another within
    its chart's plotting order. A series later in the order draws on top
    of one earlier in it (see `Chart.move_data_series`), so this is how a
    series is brought to front/back relative to the others (#189)."""

    def __init__(self, app_context: AppContext, chart_id: str, from_index: int, to_index: int):
        super().__init__()
        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.chart_id = chart_id
        self.from_index = from_index
        self.to_index = to_index
        self._chart_finder = ChartFinder(app_context)

    def _move(self, from_index: int, to_index: int) -> CommandResult:
        chart = self._chart_finder.find(self.chart_id)
        if not chart:
            self.logger.warning(
                "ReorderSeriesCommand: chart '%s' not found",
                self.chart_id,
            )
            self.ui_controller.show_error_message(
                "Reorder Series Error", f"Chart '{self.chart_id}' not found."
            )
            return CommandResult.FAILURE

        if not chart.move_data_series(from_index, to_index):
            self.logger.warning(
                "ReorderSeriesCommand: move %d -> %d out of range for chart '%s' (%d series)",
                from_index, to_index, self.chart_id, len(chart.data_series),
            )
            self.ui_controller.show_error_message(
                "Reorder Series Error", "Series index out of range."
            )
            return CommandResult.FAILURE

        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            "chart_id": self.chart_id,
            "update_type": "series_reordered",
            "chart": chart,
        })
        return CommandResult.SUCCESS

    @override
    def execute(self) -> CommandResult:
        return self._move(self.from_index, self.to_index)

    @override
    def undo(self) -> CommandResult:
        return self._move(self.to_index, self.from_index)

    @override
    def redo(self):
        return self.execute()
