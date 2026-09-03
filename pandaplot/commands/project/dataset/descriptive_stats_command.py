"""
Command for computing descriptive statistics for a dataset's columns and
adding the results to the project (a stats table dataset and, optionally, a
written report note), with undo/redo support.
"""

import uuid
from typing import List, Optional, override

from pandaplot.analysis import DescriptiveStatsEngine, DescriptiveStatsResult
from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import DatasetEvents, ProjectEvents
from pandaplot.models.project.items import Dataset, Note
from pandaplot.models.state import AppContext, AppState


class DescriptiveStatsCommand(Command):
    """
    Computes descriptive statistics for the columns of a source dataset and
    stores the results as a new dataset (the stats table) and, optionally, a
    note (a human-readable report) in the project.
    """

    def __init__(
        self,
        app_context: AppContext,
        source_dataset_id: str,
        column_names: List[str],
        digits: int = 6,
        *,
        include_report: bool = True,
        result_name: Optional[str] = None,
        folder_id: Optional[str] = None,
    ):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.source_dataset_id = source_dataset_id
        self.column_names = column_names
        self.digits = digits
        self.include_report = include_report
        self.result_name = result_name
        self.folder_id = folder_id

        # State for undo/redo.
        self.result_dataset_id: Optional[str] = None
        self.report_note_id: Optional[str] = None
        self.result: Optional[DescriptiveStatsResult] = None

    def compute(self) -> DescriptiveStatsResult:
        """Compute the statistics and return the result without touching the project.

        Useful for previewing results in the UI before committing them.
        """
        source = self._get_source_dataset()
        if source is None or source.data is None:
            raise ValueError("Source dataset is not available.")

        missing = [c for c in self.column_names if c not in source.data.columns]
        if missing:
            raise ValueError(f"Columns not found in dataset: {', '.join(missing)}")

        columns = [source.data[c] for c in self.column_names]
        return DescriptiveStatsEngine.describe(columns, digits=self.digits)

    @override
    def execute(self) -> CommandResult:
        try:
            self.logger.info("Executing DescriptiveStatsCommand on %s", self.column_names)
            if not self.app_state.has_project or not self.app_state.current_project:
                message = "No project loaded; cannot compute descriptive statistics."
                self.logger.warning(message)
                self.ui_controller.show_error_message("Descriptive Statistics Error", message)
                return CommandResult.FAILURE

            project = self.app_state.current_project

            self.result = self.compute()

            # Place the results alongside the source dataset unless a folder was
            # explicitly requested.
            if self.folder_id is None:
                source = self._get_source_dataset()
                self.folder_id = source.parent_id if source else None

            # Stats table dataset.
            name = self.result_name or self.result.result_name()
            self.result_dataset_id = str(uuid.uuid4())
            dataset = Dataset(
                id=self.result_dataset_id,
                name=name,
                data=self.result.to_dataframe(),
                source_file=None,
            )
            project.add_item(dataset, parent_id=self.folder_id)
            self.app_state.event_bus.emit(DatasetEvents.DATASET_CREATED, {
                "project": project,
                "dataset_id": self.result_dataset_id,
                "dataset_name": name,
                "folder_id": self.folder_id,
                "dataset_data": dataset.data,
            })

            # Optional written report note.
            if self.include_report:
                report_name = self.result.report_name()
                self.report_note_id = str(uuid.uuid4())
                note = Note(
                    id=self.report_note_id,
                    name=report_name,
                    content=self.result.report(),
                )
                project.add_item(note, parent_id=self.folder_id)
                self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                    "project": project,
                    "note_id": self.report_note_id,
                    "note_name": report_name,
                    "folder_id": self.folder_id,
                    "note": note,
                })

            self.logger.info("Created descriptive stats results '%s' (%s)", name, self.result_dataset_id)
            return CommandResult.SUCCESS

        except Exception as e:
            self.logger.error("Descriptive statistics failed: %s", e, exc_info=True)
            self.ui_controller.show_error_message("Descriptive Statistics Error", str(e))
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        try:
            if not self.app_state.current_project:
                self.logger.warning(
                    "DescriptiveStatsCommand.undo: no project loaded; cannot undo results '%s'",
                    self.result_dataset_id,
                )
                return CommandResult.FAILURE
            project = self.app_state.current_project

            if self.report_note_id:
                note = project.find_item(self.report_note_id)
                if note:
                    project.remove_item(note)
                    self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
                        "project": project,
                        "note_id": self.report_note_id,
                        "note": note,
                    })

            if self.result_dataset_id:
                dataset = project.find_item(self.result_dataset_id)
                if dataset:
                    project.remove_item(dataset)
                    self.app_state.event_bus.emit(DatasetEvents.DATASET_DELETED, {
                        "project": project,
                        "dataset_id": self.result_dataset_id,
                        "dataset_name": dataset.name,
                    })

            self.logger.info("Undone descriptive stats results '%s'", self.result_dataset_id)
            return CommandResult.SUCCESS
        except Exception as e:
            self.logger.error("Failed to undo descriptive statistics: %s", e, exc_info=True)
            return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the created-dataset/note ids and stats-result snapshot
        held for undo once this command is dropped from the stacks for good
        (see Command.cleanup)."""
        self.result_dataset_id = None
        self.report_note_id = None
        self.result = None

    def _get_source_dataset(self) -> Optional[Dataset]:
        project = self.app_state.current_project
        if not project:
            return None
        item = project.find_item(self.source_dataset_id)
        if isinstance(item, Dataset):
            return item
        return None
