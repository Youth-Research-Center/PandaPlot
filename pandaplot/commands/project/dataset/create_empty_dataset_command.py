"""
Command for creating empty datasets that can be filled in the app.
"""

import uuid
from typing import Optional, override

import pandas as pd
from PySide6.QtWidgets import QDialog

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.gui.dialogs.dataset.new_dataset_dialog import NewDatasetDialog
from pandaplot.models.events.event_types import DatasetEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.state import AppContext, AppState


class CreateEmptyDatasetCommand(Command):
    """
    Command to create a new empty dataset that can be filled in the app.
    """

    def __init__(self, app_context: AppContext, folder_id: Optional[str] = None, dataset_name: Optional[str] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.folder_id = folder_id
        self.dataset_name = dataset_name

        # Store state for undo
        self.dataset_id: Optional[str] = None
        self.project = None

        # Store the dataset shape/fill so redo() reuses the values chosen on
        # the first execute() instead of re-deriving (or re-prompting for) them.
        self.rows: Optional[int] = None
        self.cols: Optional[int] = None
        self.fill_value = None

    @override
    def execute(self) -> CommandResult:
        """Execute the create empty dataset command."""
        try:
            self.logger.info("Executing CreateEmptyDatasetCommand")
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.logger.warning("CreateEmptyDatasetCommand.execute: no project is currently loaded")
                self.ui_controller.show_warning_message(
                    "Create Dataset",
                    "Please open or create a project first."
                )
                return CommandResult.FAILURE

            self.project = self.app_state.current_project
            if not self.project:
                self.logger.warning("CreateEmptyDatasetCommand.execute: has_project is True but current_project is None")
                return CommandResult.FAILURE

            # Get dataset shape/name from the dialog if not provided programmatically
            if self.dataset_name is None:
                dialog = NewDatasetDialog(self.ui_controller.parent_widget)
                if dialog.exec() != QDialog.DialogCode.Accepted:
                    return CommandResult.FAILURE  # User cancelled

                self.dataset_name = dialog.get_dataset_name()
                self.rows = dialog.get_rows()
                self.cols = dialog.get_columns()
                self.fill_value = dialog.get_fill_value()
            elif self.rows is None:
                # First execute() with a programmatically-provided dataset_name (no dialog).
                self.rows, self.cols, self.fill_value = 1, 3, ""
            # else: this is a redo() -- self.rows/self.cols/self.fill_value already hold
            # the values chosen the first time this command ran; reuse them as-is.

            if not self.dataset_name:
                return CommandResult.FAILURE  # User cancelled

            assert self.rows is not None and self.cols is not None
            rows, cols = self.rows, self.cols

            # Create empty DataFrame with the chosen shape and fill value
            empty_data = pd.DataFrame({
                f"Column{i + 1}": [self.fill_value] * rows for i in range(cols)
            })

            # Create dataset ID
            self.dataset_id = str(uuid.uuid4())
            dataset = Dataset(
                id=self.dataset_id,
                name=self.dataset_name,
                data=empty_data,
                source_file=None  # No source file for manually created datasets
            )

            # Add dataset to project
            self.project.add_item(dataset, parent_id=self.folder_id)

            # Emit event
            self.app_state.event_bus.emit(DatasetEvents.DATASET_CREATED, {
                "project": self.project,
                "dataset_id": self.dataset_id,
                "dataset_name": self.dataset_name,
                "folder_id": self.folder_id,
                "dataset_data": dataset.data
            })

            if dataset.data is None:
                self.logger.warning("Created dataset '%s' has None data", self.dataset_name)
            else:
                self.logger.info(
                    "Created empty dataset '%s' with ID '%s' (rows=%d, cols=%d)",
                    self.dataset_name,
                    self.dataset_id,
                    dataset.data.shape[0],
                    dataset.data.shape[1],
                )

            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to create empty dataset: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message(
                "Create Dataset Error", error_msg)
            return CommandResult.FAILURE

    def undo(self) -> CommandResult:
        """Undo the create empty dataset command."""
        try:
            if self.dataset_id and self.app_state.has_project:
                project = self.app_state.current_project
                if project:
                    dataset = project.find_item(self.dataset_id)
                    if dataset:
                        project.remove_item(dataset)

                    # Emit event
                    self.app_state.event_bus.emit(DatasetEvents.DATASET_DELETED, {
                        "project": project,
                        "dataset_id": self.dataset_id,
                        "dataset_name": self.dataset_name
                    })

                    self.logger.info(
                        "Undone creation of dataset '%s'", self.dataset_id
                    )
                    return CommandResult.SUCCESS
            self.logger.warning(
                "CreateEmptyDatasetCommand.undo: cannot undo (dataset_id set=%s, has_project=%s)",
                bool(self.dataset_id), self.app_state.has_project,
            )
            return CommandResult.FAILURE

        except Exception as e:
            error_msg = f"Failed to undo dataset creation: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)
            return CommandResult.FAILURE

    def redo(self) -> CommandResult:
        """Redo the create empty dataset command."""
        try:
            if self.dataset_name:
                return self.execute()
            self.logger.warning(
                "CreateEmptyDatasetCommand.redo: cannot redo, no dataset_name recorded (execute() likely never succeeded)"
            )
            return CommandResult.FAILURE
        except Exception as e:
            error_msg = f"Failed to redo dataset creation: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return CommandResult.FAILURE

    @override
    def cleanup(self) -> None:
        """Release the created-dataset id and cached project reference held
        for undo once this command is dropped from the stacks for good (see
        Command.cleanup)."""
        self.dataset_id = None
        self.project = None
