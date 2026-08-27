"""Command for reordering a data series within a chart (controls z-index)."""

from typing import Optional, override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events import ChartEvents
from pandaplot.models.project.items.chart import Chart
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

    def _find_chart(self) -> Optional[Chart]:
        app_state = self.app_context.get_app_state()
        if not app_state.has_project or not app_state.current_project:
            return None
        return app_state.current_project.find_item(self.chart_id)

    def _move(self, from_index: int, to_index: int) -> bool:
        chart = self._find_chart()
        if not chart or not isinstance(chart, Chart):
            self.logger.warning(
                "ReorderSeriesCommand: chart '%s' not found or not a Chart (got %s)",
                self.chart_id, type(chart).__name__ if chart else None,
            )
            self.ui_controller.show_error_message(
                "Reorder Series Error", f"Chart '{self.chart_id}' not found."
            )
            return False

        if not chart.move_data_series(from_index, to_index):
            self.logger.warning(
                "ReorderSeriesCommand: move %d -> %d out of range for chart '%s' (%d series)",
                from_index, to_index, self.chart_id, len(chart.data_series),
            )
            self.ui_controller.show_error_message(
                "Reorder Series Error", "Series index out of range."
            )
            return False

        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            "chart_id": self.chart_id,
            "update_type": "series_reordered",
            "chart": chart,
        })
        return True

    @override
    def execute(self) -> bool:
        return self._move(self.from_index, self.to_index)

    @override
    def undo(self):
        self._move(self.to_index, self.from_index)

    @override
    def redo(self):
        return self.execute()
