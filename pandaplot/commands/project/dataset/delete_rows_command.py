from typing import List, override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_data import DatasetRowsAddedData, DatasetRowsRemovedData
from pandaplot.models.events.event_types import DatasetOperationEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState


class DeleteRowsCommand(Command):
    """
    Command to delete multiple rows from an existing dataset.
    """

    def __init__(self, app_context: AppContext, dataset_id: str, row_positions: List[int]):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        
        self.dataset_id = dataset_id
        self.row_positions = sorted(row_positions)  # Sort for consistent processing
        
        # Store state for undo
        self.original_data = None
        self.deleted_rows_data = None
        self.project = None
        self.dataset = None

    @override
    def execute(self) -> bool:
        """Execute the delete rows command."""
        try:
            self.logger.info(f"Executing DeleteRowsBatchCommand for {len(self.row_positions)} rows")
            
            # Validate input
            if not self.row_positions:
                self.ui_controller.show_warning_message(
                    "Delete Rows", 
                    "No rows specified for deletion."
                )
                return False
            
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Delete Rows", 
                    "Please open or create a project first."
                )
                return False
                
            self.project = self.app_state.current_project
            if not self.project:
                return False
            
            # Find the dataset
            found_item = self.project.find_item(self.dataset_id)
            if not found_item:
                self.ui_controller.show_error_message(
                    "Delete Rows", 
                    f"Dataset with ID '{self.dataset_id}' not found."
                )
                return False
            
            if not isinstance(found_item, Dataset):
                self.ui_controller.show_error_message(
                    "Delete Rows", 
                    "Selected item is not a dataset."
                )
                return False
                
            self.dataset = found_item
            
            # Get current data
            if self.dataset.data is None or self.dataset.data.empty:
                self.ui_controller.show_warning_message(
                    "Delete Rows", 
                    "Cannot delete rows from empty dataset."
                )
                return False
            
            # Validate row positions
            max_row = len(self.dataset.data) - 1
            invalid_positions = [pos for pos in self.row_positions if pos < 0 or pos > max_row]
            if invalid_positions:
                self.ui_controller.show_error_message(
                    "Delete Rows", 
                    f"Invalid row positions: {invalid_positions}. Dataset has {len(self.dataset.data)} rows (0-{max_row})."
                )
                return False
            
            # Check for duplicate positions
            if len(set(self.row_positions)) != len(self.row_positions):
                self.ui_controller.show_warning_message(
                    "Delete Rows", 
                    "Duplicate row positions found in the deletion list."
                )
                return False
            
            # Store original data for undo
            self.original_data = self.dataset.data.copy()
            
            # Store the deleted rows data for potential restoration
            self.deleted_rows_data = self.dataset.data.iloc[self.row_positions].copy()
            
            # Create new DataFrame with the rows removed
            # Sort positions in reverse order to avoid index shifting issues
            new_data = self.dataset.data.copy()
            for position in sorted(self.row_positions, reverse=True):
                new_data = new_data.drop(new_data.index[position])
            
            # Reset index after deletion
            new_data = new_data.reset_index(drop=True)
            
            # Update dataset
            self.dataset.set_data(new_data)
            
            # Emit event
            self.app_state.event_bus.emit(DatasetOperationEvents.DATASET_ROW_REMOVED, 
                 DatasetRowsRemovedData(dataset_id=self.dataset_id, row_positions=self.row_positions).to_dict()
            )

            self.logger.info(f"Deleted {len(self.row_positions)} rows from dataset '{self.dataset.name}' (ID: {self.dataset_id})")
            return True
            
        except Exception as e:
            error_msg = f"Failed to delete {len(self.row_positions) if self.row_positions else 0} rows: {str(e)}"
            self.logger.error(error_msg)
            self.ui_controller.show_error_message("Delete Rows Error", error_msg)
            return False

    def undo(self):
        """Undo the delete rows command by restoring the original data."""
        try:
            if self.dataset and self.original_data is not None:
                # Restore original data
                self.dataset.set_data(self.original_data)
                
                # Emit event
                self.app_state.event_bus.emit(DatasetOperationEvents.DATASET_ROW_ADDED, DatasetRowsAddedData(
                    dataset_id=self.dataset_id,
                    row_positions=self.row_positions
                ).to_dict())

                self.logger.info(f"Undid deleting {len(self.row_positions)} rows from dataset '{self.dataset.name}'")
                return True
        except Exception as e:
            self.logger.error(f"DeleteRowsBatchCommand Undo Error: {e}")
            return False

    def redo(self):
        """Redo the delete rows command."""
        # Re-execute with stored parameters
        return self.execute()
