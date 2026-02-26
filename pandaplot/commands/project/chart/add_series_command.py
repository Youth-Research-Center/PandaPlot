"""Command for adding a data series to a chart."""

from typing import Optional, override

from pandaplot.commands.base_command import Command
from pandaplot.models.events import ChartEvents
from pandaplot.models.project.items.chart import Chart, DataSeries
from pandaplot.models.state import AppContext


class AddSeriesCommand(Command):
    """Command to add a new data series to an existing chart."""

    def __init__(self, app_context: AppContext, chart_id: str,
                 dataset_id: str, x_column: str, y_column: str,
                 label: str = "", color: str = "#1f77b4"):
        super().__init__()
        self.app_context = app_context
        self.chart_id = chart_id
        self.dataset_id = dataset_id
        self.x_column = x_column
        self.y_column = y_column
        self.label = label
        self.color = color
        self.added_index: Optional[int] = None

    def _find_chart(self) -> Optional[Chart]:
        app_state = self.app_context.get_app_state()
        if not app_state.has_project or not app_state.current_project:
            return None
        return app_state.current_project.find_item(self.chart_id)

    @override
    def execute(self) -> bool:
        chart = self._find_chart()
        if not chart or not isinstance(chart, Chart):
            return False

        chart.add_data_series(
            dataset_id=self.dataset_id,
            x_column=self.x_column,
            y_column=self.y_column,
            label=self.label,
            color=self.color,
        )
        self.added_index = len(chart.data_series) - 1

        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            'chart_id': self.chart_id,
            'update_type': 'series_added',
            'chart': chart,
        })
        return True

    @override
    def undo(self):
        chart = self._find_chart()
        if not chart or self.added_index is None:
            return

        chart.remove_data_series(self.added_index)
        self.app_context.event_bus.emit(ChartEvents.CHART_UPDATED, {
            'chart_id': self.chart_id,
            'update_type': 'series_removed',
            'chart': chart,
        })

    @override
    def redo(self):
        self.execute()
