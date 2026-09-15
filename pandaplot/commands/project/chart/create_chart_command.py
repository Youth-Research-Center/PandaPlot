"""Command that adds an already-built Chart item to the project.

Split out of CreateChartFromWizardCommand (#185): the wizard command only
opens a non-blocking dialog and is exempt from the undo/redo stacks (see
Command.occupies_undo_slot()), since its real effect happens later,
asynchronously, once the wizard finishes. This command is what actually
lands on the undo stack -- it owns the add/remove of a fully-configured
Chart, independent of how that Chart was built.
"""

from typing import Optional, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.models.events import ChartEvents, ProjectEvents
from pandaplot.models.events.event_data import ChartCreatedData
from pandaplot.models.project.items import Chart
from pandaplot.models.state import AppContext, AppState


class CreateChartCommand(Command):
    """Adds `chart` to the project under `parent_id`; undoable/redoable."""

    def __init__(self, app_context: AppContext, chart: Chart, parent_id: Optional[str] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.chart = chart
        self.chart_id = chart.id
        self.parent_id = parent_id

    @override
    def execute(self) -> CommandResult:
        project = get_current_project(self.app_context)
        if project is None:
            self.logger.warning("CreateChartCommand.execute: no project is currently loaded")
            return CommandResult.FAILURE
        try:
            project.add_item(self.chart, parent_id=self.parent_id)
            self.app_context.event_bus.emit(ChartEvents.CHART_CREATED, ChartCreatedData(
                chart_id=self.chart_id
            ).to_dict())
            self.logger.info("CreateChartCommand: created chart '%s'", self.chart_id)
            return CommandResult.SUCCESS
        except Exception as e:
            self.logger.error("CreateChartCommand Execute Error: %s", str(e))
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        project = get_current_project(self.app_context)
        if project is None:
            self.logger.warning("CreateChartCommand.undo: no project is currently loaded")
            return CommandResult.FAILURE
        try:
            project.remove_item_by_id(self.chart_id)
            self.app_context.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
                "item_id": self.chart_id,
                "item_type": "chart",
            })
            self.logger.info("CreateChartCommand: undid creation of chart '%s'", self.chart_id)
            return CommandResult.SUCCESS
        except Exception as e:
            self.logger.error("CreateChartCommand Undo Error: %s", str(e))
            return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        return self.execute()

    @override
    def cleanup(self) -> None:
        """No undo-only state to release -- self.chart is needed by redo()
        (execute() re-adds it), so it must stay alive for as long as this
        command could still be on a stack. Nothing else is held."""
        return
