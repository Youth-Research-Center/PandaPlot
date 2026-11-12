"""Command that stores an already-computed analysis result as a new dataset,
with undo/redo support.

Counterpart of ApplyAnalysisResultCommand for results that do not belong on
the rows of the analyzed dataset. An interpolation resamples onto a new,
evenly spaced X grid, so its Y values only make sense next to that grid: the
result is a new (X, Y) dataset, like the one the Chart Analysis panel creates.
"""

from typing import override

import pandas as pd

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.chart.series_xy import (
    add_result_dataset,
    create_result_dataset,
    remove_result_dataset,
)
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext


class ApplyAnalysisDatasetResultCommand(Command):
    """Adds a precomputed analysis result to the project as a new dataset."""

    def __init__(
        self,
        app_context: AppContext,
        dataset_name: str,
        result_data: pd.DataFrame,
        *,
        folder_id: str | None = None,
    ):
        super().__init__()
        self.app_context = app_context
        self.app_state = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.dataset_name = dataset_name
        self.result_data = result_data
        self.folder_id = folder_id

        # Set once execute() has actually created the dataset, so redo() can
        # put the same dataset (same id and name) back.
        self.result_dataset: Dataset | None = None

    @override
    def execute(self) -> CommandResult:
        try:
            if get_current_project(self.app_context) is None:
                message = "No project loaded; cannot add the analysis result."
                self.logger.warning("ApplyAnalysisDatasetResultCommand.execute: %s", message)
                self.ui_controller.show_error_message("Analysis Error", message)
                return CommandResult.FAILURE

            self.result_dataset = create_result_dataset(self.app_state, self.folder_id, self.dataset_name, self.result_data)
            self.logger.info("Created analysis result dataset '%s' (%s)", self.result_dataset.name, self.result_dataset.id)
            return CommandResult.SUCCESS

        except Exception as e:
            self.logger.exception("ApplyAnalysisDatasetResultCommand execution failed")
            self.ui_controller.show_error_message("Analysis Error", "Couldn't add the analysis result to the project.", error=e)
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        try:
            project = get_current_project(self.app_context)
            live_dataset = (
                project.find_item(self.result_dataset.id)
                if self.result_dataset is not None and project is not None
                else None
            )
            if not isinstance(live_dataset, Dataset):
                self.logger.warning("Undo skipped: the analysis result dataset no longer exists")
                return CommandResult.ABORTED

            remove_result_dataset(self.app_state, live_dataset.id)
            self.result_dataset = live_dataset
            return CommandResult.SUCCESS

        except Exception:
            self.logger.exception("ApplyAnalysisDatasetResultCommand undo failed")
            return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        try:
            project = get_current_project(self.app_context)
            if self.result_dataset is None or project is None:
                self.logger.warning("Redo skipped: there is no analysis result dataset to restore")
                return CommandResult.ABORTED

            add_result_dataset(self.app_state, self.folder_id, self.result_dataset)
            return CommandResult.SUCCESS

        except Exception:
            self.logger.exception("ApplyAnalysisDatasetResultCommand redo failed")
            return CommandResult.FAILURE

    @override
    def cleanup(self) -> None:
        """Release the result table and dataset once this command is dropped
        from the stacks for good (see Command.cleanup)."""
        self.result_data = pd.DataFrame()
        self.result_dataset = None
