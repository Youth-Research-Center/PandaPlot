# pandaplot/commands/project/dataset/apply_signal_analysis_result_command.py
"""Command that stores an already-computed SignalAnalysisResult as a new
project dataset, with undo/redo support.

Split out of SignalAnalysisCommand so the background computation (dispatched
via TaskScheduler) and the actual, undo-tracked project mutation are separate
commands -- see analysis_command.py / apply_analysis_result_command.py for
the same pattern applied to AnalysisCommand.
"""

import uuid
from typing import Optional, override

from pandaplot.analysis import SignalAnalysisResult
from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.models.events.event_types import DatasetEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.state import AppContext, AppState


class ApplySignalAnalysisResultCommand(Command):
    """Stores a precomputed SignalAnalysisResult as a new dataset."""

    def __init__(
        self,
        app_context: AppContext,
        result_name: Optional[str],
        folder_id: Optional[str],
        result: SignalAnalysisResult,
    ):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.result_name = result_name
        self.folder_id = folder_id
        self.result = result

        self.result_dataset_id: Optional[str] = None
        self._dataset: Optional[Dataset] = None

    @override
    def execute(self) -> CommandResult:
        try:
            project = get_current_project(self.app_context)
            if project is None:
                self.logger.warning("ApplySignalAnalysisResultCommand.execute: no project loaded")
                return CommandResult.FAILURE

            # Built once (first execute()) and cached; a later redo() re-adds
            # this same object instead of minting a fresh id, so anything
            # that recorded the original id (e.g. a chart series sourcing
            # from this dataset) keeps working after an undo/redo
            # round-trip. Mirrors ApplyFitCommand._create_report().
            if self._dataset is None:
                name = self.result_name or self.result.result_name()
                self.result_dataset_id = str(uuid.uuid4())
                self._dataset = Dataset(
                    id=self.result_dataset_id,
                    name=name,
                    data=self.result.data,
                    source_file=None,
                )
            dataset = self._dataset

            project.add_item(dataset, parent_id=self.folder_id)

            self.app_state.event_bus.emit(
                DatasetEvents.DATASET_CREATED,
                {
                    "project": project,
                    "dataset_id": self.result_dataset_id,
                    "dataset_name": dataset.name,
                    "folder_id": self.folder_id,
                    "dataset_data": dataset.data,
                },
            )
            self.logger.info(
                "Created signal analysis dataset '%s' (%s)", dataset.name, self.result_dataset_id,
            )
            return CommandResult.SUCCESS

        except Exception as e:
            self.logger.error("Failed to apply signal analysis result: %s", e, exc_info=True)
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        try:
            project = get_current_project(self.app_context)
            if not self.result_dataset_id or project is None:
                self.logger.warning(
                    "ApplySignalAnalysisResultCommand.undo: cannot undo (result_dataset_id=%s, project loaded=%s)",
                    self.result_dataset_id, project is not None,
                )
                return CommandResult.FAILURE

            dataset = project.find_item(self.result_dataset_id)
            if dataset:
                project.remove_item(dataset)
                self.app_state.event_bus.emit(
                    DatasetEvents.DATASET_DELETED,
                    {
                        "project": project,
                        "dataset_id": self.result_dataset_id,
                        "dataset_name": dataset.name,
                    },
                )
            return CommandResult.SUCCESS

        except Exception as e:
            self.logger.error("Failed to undo signal analysis: %s", e, exc_info=True)
            return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        return self.execute()

    @override
    def cleanup(self) -> None:
        self.result_dataset_id = None
        self.result = None
        self._dataset = None
