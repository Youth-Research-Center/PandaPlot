"""Command that looks up an analysis result dataset by ID and adds its result as a series to a chart."""

from typing import Optional, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.chart.add_series_command import AddSeriesCommand
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.models.chart.chart_type_spec import get_chart_type_spec
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart, DataSeries
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state import AppContext


class AddAnalysisSeriesCommand(Command):
    """Command that extracts a result dataset ID from a completed analysis command
    and adds the dataset's result as a new data series on a specified chart.
    """

    def __init__(self, app_context: AppContext, chart_id: str, dataset_command: Command):
        super().__init__()
        self.app_context = app_context
        self.chart_id = chart_id
        self.dataset_command = dataset_command
        self._delegate: Optional[AddSeriesCommand] = None

    @override
    def execute(self) -> CommandResult:
        dataset_id = getattr(self.dataset_command, "result_dataset_id", None)
        if not dataset_id:
            self.logger.warning("AddAnalysisSeriesCommand: no result_dataset_id on dataset_command")
            return CommandResult.FAILURE

        project = get_current_project(self.app_context)
        if project is None:
            self.logger.warning("AddAnalysisSeriesCommand: no project loaded")
            return CommandResult.FAILURE

        dataset = project.find_item(dataset_id)
        if not isinstance(dataset, Dataset) or dataset.data is None:
            self.logger.warning("AddAnalysisSeriesCommand: dataset '%s' not found or invalid", dataset_id)
            return CommandResult.FAILURE

        chart = project.find_item(self.chart_id)
        if not isinstance(chart, Chart):
            self.logger.warning("AddAnalysisSeriesCommand: chart '%s' not found or invalid", self.chart_id)
            return CommandResult.FAILURE

        cols = list(dataset.data.columns)
        if len(cols) >= 2:
            x_name, y_name = cols[0], cols[1]
        elif len(cols) == 1:
            x_name, y_name = "", cols[0]
        else:
            self.logger.warning("AddAnalysisSeriesCommand: dataset '%s' has no columns", dataset_id)
            return CommandResult.FAILURE

        x_id = dataset.column_id(x_name) if x_name else ""
        y_id = dataset.column_id(y_name) if y_name else ""

        spec = get_chart_type_spec(chart.chart_type)
        if SeriesType.LINE in spec.allowed_series_types:
            series_type = SeriesType.LINE
        elif SeriesType.SCATTER in spec.allowed_series_types:
            series_type = SeriesType.SCATTER
        else:
            series_type = spec.default_series_type

        series = DataSeries(
            dataset_id=dataset.id,
            x_column_id=x_id or "",
            y_column_id=y_id or "",
            x_column=x_name,
            y_column=y_name,
            label=y_name,
            series_type=series_type,
        )

        self._delegate = AddSeriesCommand(
            app_context=self.app_context,
            chart_id=self.chart_id,
            series=series,
        )
        return self._delegate.execute()

    @override
    def undo(self) -> CommandResult:
        if self._delegate:
            return self._delegate.undo()
        return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        if self._delegate:
            return self._delegate.redo()
        return CommandResult.FAILURE

    @override
    def cleanup(self) -> None:
        if self._delegate:
            self._delegate.cleanup()
            self._delegate = None
