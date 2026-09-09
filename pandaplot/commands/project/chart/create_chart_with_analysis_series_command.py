"""Command that creates a new chart for an analysis result and plots the
result on it -- the "Plot result" destination picker's "New chart" option."""

from typing import Optional, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.composite_command import CompositeCommand
from pandaplot.commands.project.chart.add_analysis_series_command import AddAnalysisSeriesCommand
from pandaplot.commands.project.chart.create_chart_command import CreateChartCommand
from pandaplot.commands.project.chart.series_xy import unique_sibling_name
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state import AppContext


class CreateChartWithAnalysisSeriesCommand(Command):
    """Creates a new ChartType.LINE chart in `folder_id`, named after
    `dataset_command`'s result dataset, and plots that dataset's result on
    it -- both steps composed atomically via CompositeCommand.

    Used by the "Plot result" destination picker's "New chart" option, as
    an alternative to AddAnalysisSeriesCommand (which targets an existing
    chart instead). The chart's name can only be resolved once the result
    dataset actually exists (unique_sibling_name needs to see it as an
    existing sibling to avoid colliding with it), so the inner
    CompositeCommand is built lazily on first execute(), once
    `dataset_command` has already run -- mirroring how AddAnalysisSeriesCommand
    itself resolves `dataset_command.result_dataset_id` at execute time
    rather than at construction.
    """

    def __init__(self, app_context: AppContext, folder_id: Optional[str], dataset_command: Command):
        super().__init__()
        self.app_context = app_context
        self.folder_id = folder_id
        self.dataset_command = dataset_command
        self._composite: Optional[CompositeCommand] = None
        self.created_chart_id: Optional[str] = None

    @override
    def execute(self) -> CommandResult:
        if self._composite is None:
            dataset_id = getattr(self.dataset_command, "result_dataset_id", None)
            if not dataset_id:
                self.logger.warning(
                    "CreateChartWithAnalysisSeriesCommand: no result_dataset_id on dataset_command"
                )
                return CommandResult.FAILURE

            project = get_current_project(self.app_context)
            if project is None:
                self.logger.warning("CreateChartWithAnalysisSeriesCommand: no project loaded")
                return CommandResult.FAILURE

            dataset = project.find_item(dataset_id)
            if not isinstance(dataset, Dataset):
                self.logger.warning(
                    "CreateChartWithAnalysisSeriesCommand: dataset '%s' not found or invalid", dataset_id
                )
                return CommandResult.FAILURE

            chart_name = unique_sibling_name(project, self.folder_id, dataset.name)
            chart = Chart(name=chart_name, chart_type=ChartType.LINE)
            self.created_chart_id = chart.id

            create_chart_cmd = CreateChartCommand(self.app_context, chart, parent_id=self.folder_id)
            add_series_cmd = AddAnalysisSeriesCommand(
                app_context=self.app_context,
                chart_id=chart.id,
                dataset_command=self.dataset_command,
            )
            self._composite = CompositeCommand([create_chart_cmd, add_series_cmd])

        return self._composite.execute()

    @override
    def undo(self) -> CommandResult:
        if self._composite is None:
            return CommandResult.FAILURE
        return self._composite.undo()

    @override
    def redo(self) -> CommandResult:
        if self._composite is None:
            return CommandResult.FAILURE
        return self._composite.redo()

    @override
    def cleanup(self) -> None:
        if self._composite is not None:
            self._composite.cleanup()


def build_quick_plot_command(
    app_context: AppContext,
    dataset_command: Command,
    *,
    target_chart_id: Optional[str],
    folder_id: Optional[str],
) -> Command:
    """Return the command to compose alongside `dataset_command` for the
    "Plot result" destination picker: `target_chart_id` is the destination
    combo's current data -- None for "New chart"
    (CreateChartWithAnalysisSeriesCommand), otherwise an existing chart's id
    (AddAnalysisSeriesCommand). Shared by all three quick-plot call sites
    (ChartAnalysisPanel.apply(), ChartSignalAnalysisPanel's cached
    add_results_to_project() path, and
    ChartSignalAnalysisCommand._on_commit_computed()) so the choice is made
    identically everywhere.
    """
    if target_chart_id is None:
        return CreateChartWithAnalysisSeriesCommand(
            app_context, folder_id=folder_id, dataset_command=dataset_command,
        )
    return AddAnalysisSeriesCommand(
        app_context=app_context, chart_id=target_chart_id, dataset_command=dataset_command,
    )
