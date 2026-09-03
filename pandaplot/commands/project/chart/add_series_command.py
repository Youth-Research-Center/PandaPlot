"""Command for adding a data series to a chart."""

from typing import Optional, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events import ChartEvents
from pandaplot.models.project.items.chart import Chart, DataSeries
from pandaplot.models.state import AppContext


class AddSeriesCommand(Command):
    """Command to add a new, fully-constructed data series to an existing chart."""

    def __init__(self, app_context: AppContext, chart_id: str, series: DataSeries):
        super().__init__()
        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.chart_id = chart_id
        self.series = series
        self.added_index: Optional[int] = None

    def _find_chart(self) -> Optional[Chart]:
        app_state = self.app_context.get_app_state()
        if not app_state.has_project or not app_state.current_project:
            return None
        return app_state.current_project.find_item(self.chart_id)

    @override
    def execute(self) -> CommandResult:
        chart = self._find_chart()
        if not chart or not isinstance(chart, Chart):
            self.logger.warning(
                "AddSeriesCommand.execute: chart '%s' not found or not a Chart (got %s)",
                self.chart_id, type(chart).__name__ if chart else None,
            )
            self.ui_controller.show_error_message(
                "Add Series Error", f"Chart '{self.chart_id}' not found."
            )
            return CommandResult.FAILURE

        chart.data_series.append(self.series)
        chart.update_modified_time()
        self.added_index = len(chart.data_series) - 1

        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            "chart_id": self.chart_id,
            "update_type": "series_added",
            "chart": chart,
        })
        return CommandResult.SUCCESS

    @override
    def undo(self) -> CommandResult:
        chart = self._find_chart()
        if not chart or self.added_index is None:
            return CommandResult.FAILURE

        chart.remove_data_series(self.added_index)
        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            "chart_id": self.chart_id,
            "update_type": "series_removed",
            "chart": chart,
        })
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the insertion-index bookkeeping held for undo once this
        command is dropped from the stacks for good (see Command.cleanup)."""
        self.added_index = None
