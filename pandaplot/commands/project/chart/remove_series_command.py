"""Command for removing a data series from a chart."""

import copy
from typing import Optional, override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events import ChartEvents
from pandaplot.models.project.items.chart import Chart, DataSeries
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

    def _find_chart(self) -> Optional[Chart]:
        app_state = self.app_context.get_app_state()
        if not app_state.has_project or not app_state.current_project:
            return None
        return app_state.current_project.find_item(self.chart_id)

    @override
    def execute(self) -> bool:
        chart = self._find_chart()
        if not chart or not isinstance(chart, Chart):
            self.logger.warning(
                "RemoveSeriesCommand.execute: chart '%s' not found or not a Chart (got %s)",
                self.chart_id, type(chart).__name__ if chart else None,
            )
            self.ui_controller.show_error_message(
                "Remove Series Error", f"Chart '{self.chart_id}' not found."
            )
            return False

        if self.series_index < 0 or self.series_index >= len(chart.data_series):
            self.logger.warning(
                "RemoveSeriesCommand.execute: series_index %s out of range for chart '%s' (%d series)",
                self.series_index, self.chart_id, len(chart.data_series),
            )
            self.ui_controller.show_error_message(
                "Remove Series Error", f"Series index {self.series_index} is out of range."
            )
            return False

        # Snapshot the series before removing
        series = chart.data_series[self.series_index]
        self.removed_series_data = copy.deepcopy(series)

        chart.remove_data_series(self.series_index)

        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            "chart_id": self.chart_id,
            "update_type": "series_removed",
            "chart": chart,
        })
        return True

    @override
    def undo(self):
        chart = self._find_chart()
        if not chart or self.removed_series_data is None:
            self.logger.warning(
                "RemoveSeriesCommand.undo: cannot undo for chart '%s' (chart found=%s, removed_series_data set=%s)",
                self.chart_id, chart is not None, self.removed_series_data is not None,
            )
            return

        # Re-create and insert at original position
        series = copy.deepcopy(self.removed_series_data)
        chart.data_series.insert(self.series_index, series)
        chart.update_modified_time()

        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            "chart_id": self.chart_id,
            "update_type": "series_added",
            "chart": chart,
        })

    @override
    def redo(self):
        self.execute()
