"""
Command for running a signal analysis and adding the results to the project
as a new dataset, with undo/redo support.
"""

import uuid
from typing import Any, Dict, Optional, override

from pandaplot.analysis import (
    SignalAnalysisResult,
    SignalAnalysisType,
    SignalEngine,
)
from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import DatasetEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.state import AppContext, AppState


class SignalAnalysisCommand(Command):
    """
    Runs a signal analysis on a source dataset column and stores the result
    as a new dataset in the project.
    """

    def __init__(
        self,
        app_context: AppContext,
        source_dataset_id: str,
        analysis_type: SignalAnalysisType,
        column_name: str,
        sampling_rate: Optional[float] = None,
        parameters: Optional[Dict[str, Any]] = None,
        result_name: Optional[str] = None,
        folder_id: Optional[str] = None,
    ):
        super().__init__()

        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.source_dataset_id = source_dataset_id
        self.analysis_type = analysis_type
        self.column_name = column_name
        self.sampling_rate = sampling_rate
        self.parameters = parameters or {}

        self.result_name = result_name
        self.folder_id = folder_id

        # Undo/redo state
        self.result_dataset_id: Optional[str] = None
        self.result: Optional[SignalAnalysisResult] = None

    def run_analysis(self) -> SignalAnalysisResult:
        """
        Run analysis and return result without modifying project.

        Used for previewing results in UI.
        """

        source = self._get_source_dataset()

        if source is None or source.data is None:
            raise ValueError(
                "Source dataset is not available."
            )

        if self.column_name not in source.data.columns:
            raise ValueError(
                f"Column not found: {self.column_name}"
            )

        column = source.data[self.column_name]

        return SignalEngine.run_analysis(
            analysis_type=self.analysis_type,
            column=column,
            sampling_rate=self.sampling_rate,
            **self.parameters,
        )

    @override
    def execute(self) -> bool:
        try:
            self.logger.info(
                "Executing SignalAnalysisCommand (%s)",
                self.analysis_type.value,
            )

            if (
                not self.app_state.has_project
                or not self.app_state.current_project
            ):
                message = "No project loaded; cannot run signal analysis."
                self.logger.warning(message)
                self.ui_controller.show_error_message("Signal Analysis Error", message)
                return False

            project = self.app_state.current_project

            self.result = self.run_analysis()

            results_df = self.result.data

            name = (
                self.result_name
                or self.result.result_name()
            )

            self.result_dataset_id = str(uuid.uuid4())

            dataset = Dataset(
                id=self.result_dataset_id,
                name=name,
                data=results_df,
                source_file=None,
            )

            project.add_item(
                dataset,
                parent_id=self.folder_id,
            )

            self.app_state.event_bus.emit(
                DatasetEvents.DATASET_CREATED,
                {
                    "project": project,
                    "dataset_id": self.result_dataset_id,
                    "dataset_name": name,
                    "folder_id": self.folder_id,
                    "dataset_data": dataset.data,
                },
            )

            self.logger.info(
                "Created signal analysis dataset '%s' (%s)",
                name,
                self.result_dataset_id,
            )

            return True

        except Exception as e:
            self.logger.error(
                "Signal analysis failed: %s",
                e,
                exc_info=True,
            )
            self.ui_controller.show_error_message("Signal Analysis Error", str(e))
            return False

    @override
    def undo(self) -> bool:
        try:
            if (
                not self.result_dataset_id
                or not self.app_state.current_project
            ):
                self.logger.warning(
                    "SignalAnalysisCommand.undo: cannot undo (result_dataset_id=%s, project loaded=%s)",
                    self.result_dataset_id, bool(self.app_state.current_project),
                )
                return False

            project = self.app_state.current_project

            dataset = project.find_item(
                self.result_dataset_id
            )

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

            return True

        except Exception as e:
            self.logger.error(
                "Failed to undo signal analysis: %s",
                e,
                exc_info=True,
            )
            return False

    @override
    def redo(self) -> bool:
        return self.execute()

    def _get_source_dataset(self) -> Optional[Dataset]:
        project = self.app_state.current_project

        if not project:
            return None

        item = project.find_item(
            self.source_dataset_id
        )

        if isinstance(item, Dataset):
            return item

        return None