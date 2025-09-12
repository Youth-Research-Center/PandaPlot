"""
Command for creating empty datasets that can be filled in the app.
"""

import uuid
from typing import Optional, override

import pandas as pd

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
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

    @override
    def execute(self) -> bool:
        """Execute the create empty dataset command."""
        try:
            self.logger.info("Executing CreateEmptyDatasetCommand")
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Create Dataset",
                    "Please open or create a project first."
                )
                return False

            self.project = self.app_state.current_project
            if not self.project:
                return False

            # Get dataset name from user if not provided
            if self.dataset_name is None:
                self.dataset_name = self.ui_controller.get_text_input(
                    "Create New Dataset",
                    "Enter dataset name:",
                    "New Dataset"
                )

            if not self.dataset_name:
                return False  # User cancelled

            # Create empty DataFrame with basic structure
            empty_data = pd.DataFrame({
                'Column1': [''],
                'Column2': [''],
                'Column3': ['']
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
                'project': self.project,
                'dataset_id': self.dataset_id,
                'dataset_name': self.dataset_name,
                'folder_id': self.folder_id,
                'dataset_data': dataset.data
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

            return True

        except Exception as e:
            error_msg = f"Failed to create empty dataset: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message(
                "Create Dataset Error", error_msg)
            return False

    def undo(self):
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
                        'project': project,
                        'dataset_id': self.dataset_id,
                        'dataset_name': self.dataset_name
                    })

                    self.logger.info(
                        "Undone creation of dataset '%s'", self.dataset_id
                    )

        except Exception as e:
            error_msg = f"Failed to undo dataset creation: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)

    def redo(self):
        """Redo the create empty dataset command."""
        try:
            if self.dataset_name:
                return self.execute()
        except Exception as e:
            error_msg = f"Failed to redo dataset creation: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return False
