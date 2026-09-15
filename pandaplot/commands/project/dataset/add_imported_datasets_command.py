"""Command that adds already-read Dataset object(s) to the project.

Split out of ImportDataCommand (#301): ImportDataCommand only dispatches the
background file read via TaskScheduler and is exempt from the undo/redo
stacks (see Command.occupies_undo_slot()), since its real effect -- the
dataset(s) actually landing in the project -- happens later, asynchronously,
in its on_result callback once the read finishes. This command is what
actually lands on the undo stack -- it owns the add/remove of a set of
already-built Dataset objects, independent of how they were produced.
"""

from typing import List, Optional, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.models.events.event_types import DatasetEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.state import AppContext, AppState


class AddImportedDatasetsCommand(Command):
    """Adds `datasets` to the project under `folder_id`; undoable/redoable."""

    def __init__(
        self,
        app_context: AppContext,
        datasets: List[Dataset],
        folder_id: Optional[str] = None,
        file_path: Optional[str] = None,
    ):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.datasets = datasets
        self.dataset_ids = [dataset.id for dataset in datasets]
        self.folder_id = folder_id
        self.file_path = file_path

    @override
    def execute(self) -> CommandResult:
        project = get_current_project(self.app_context)
        if project is None:
            self.logger.warning("AddImportedDatasetsCommand.execute: no project is currently loaded")
            return CommandResult.FAILURE
        try:
            for dataset in self.datasets:
                project.add_item(dataset, parent_id=self.folder_id)
                # TODO(#219): migrate to item created and create data class
                self.app_state.event_bus.emit(
                    DatasetEvents.DATASET_CREATED,
                    {
                        "project": project,
                        "dataset_id": dataset.id,
                        "dataset_name": dataset.name,
                        "folder_id": self.folder_id,
                        "dataset_data": dataset.data,
                        "file_path": self.file_path,
                        "dataframe": dataset.data,
                    },
                )
            self.logger.info("AddImportedDatasetsCommand: added %d dataset(s)", len(self.datasets))
            return CommandResult.SUCCESS
        except Exception as e:
            self.logger.error("AddImportedDatasetsCommand Execute Error: %s", str(e), exc_info=True)
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        project = get_current_project(self.app_context)
        if project is None:
            self.logger.warning("AddImportedDatasetsCommand.undo: no project is currently loaded")
            return CommandResult.FAILURE
        try:
            for dataset_id in self.dataset_ids:
                dataset = project.find_item(dataset_id)
                if dataset:
                    project.remove_item(dataset)
                self.app_state.event_bus.emit(
                    DatasetEvents.DATASET_DELETED,
                    {"project": project, "dataset_id": dataset_id, "dataset_data": None},
                )
            self.logger.info("AddImportedDatasetsCommand: undid addition of %d dataset(s)", len(self.dataset_ids))
            return CommandResult.SUCCESS
        except Exception as e:
            self.logger.error("AddImportedDatasetsCommand Undo Error: %s", str(e), exc_info=True)
            return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        return self.execute()

    @override
    def cleanup(self) -> None:
        """No undo-only state to release beyond the Dataset objects
        themselves -- redo() needs them to re-add, same as CreateChartCommand
        keeps `self.chart` alive for its own redo()."""
        return
