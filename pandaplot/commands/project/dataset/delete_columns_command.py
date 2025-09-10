from typing import List, override
from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_data import DatasetColumnsAddedData, DatasetColumnsRemovedData
from pandaplot.models.events.event_types import DatasetOperationEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState


class DeleteColumnsCommand(Command):
    """
    Command to delete multiple columns from an existing dataset.
    """

    def __init__(self, app_context: AppContext, dataset_id: str, column_names: List[str]):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        
        self.dataset_id = dataset_id
        self.column_names = column_names
        
        # Store state for undo
        self.original_data = None
        self.deleted_columns_data = None
        self.column_positions = None
        self.project = None
        self.dataset = None

    @override
    def execute(self) -> bool:
        """Execute the delete columns command."""
        try:
            self.logger.info(f"Executing DeleteColumnsBatchCommand for {len(self.column_names)} columns")
            
            # Validate input
            if not self.column_names:
                self.ui_controller.show_warning_message(
                    "Delete Columns", 
                    "No columns specified for deletion."
                )
                return False
            
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Delete Columns", 
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
                    "Delete Columns", 
                    f"Dataset with ID '{self.dataset_id}' not found."
                )
                return False
            
            if not isinstance(found_item, Dataset):
                self.ui_controller.show_error_message(
                    "Delete Columns", 
                    "Selected item is not a dataset."
                )
                return False
                
            self.dataset = found_item
            
            # Get current data
            if self.dataset.data is None or self.dataset.data.empty:
                self.ui_controller.show_warning_message(
                    "Delete Columns", 
                    "Cannot delete columns from empty dataset."
                )
                return False
            
            # Check if all columns exist
            existing_columns = set(self.dataset.data.columns)
            missing_columns = [col for col in self.column_names if col not in existing_columns]
            if missing_columns:
                self.ui_controller.show_error_message(
                    "Delete Columns", 
                    f"The following columns do not exist: {', '.join(missing_columns)}"
                )
                return False
            
            # Check for duplicate column names
            if len(set(self.column_names)) != len(self.column_names):
                self.ui_controller.show_warning_message(
                    "Delete Columns", 
                    "Duplicate column names found in the deletion list."
                )
                return False
            
            # Check if we're trying to delete all columns
            remaining_columns = len(self.dataset.data.columns) - len(self.column_names)
            if remaining_columns <= 0:
                self.ui_controller.show_error_message(
                    "Delete Columns", 
                    "Cannot delete all columns from dataset. Dataset must have at least one column."
                )
                return False
            
            # Store original data for undo
            self.original_data = self.dataset.data.copy()
            
            # Store the column positions and data for potential restoration
            self.column_positions = {}
            self.deleted_columns_data = {}
            for col_name in self.column_names:
                self.column_positions[col_name] = list(self.dataset.data.columns).index(col_name)
                self.deleted_columns_data[col_name] = self.dataset.data[col_name].copy()
            
            # Create new DataFrame with the columns removed
            new_data = self.dataset.data.drop(columns=self.column_names)
            
            # Update dataset
            self.dataset.set_data(new_data)
            
            # Emit event
            self.app_state.event_bus.emit(DatasetOperationEvents.DATASET_COLUMN_REMOVED, 
                                          DatasetColumnsRemovedData(dataset_id=self.dataset_id, column_positions=list(self.column_positions.values())).to_dict()
            )

            self.logger.info(f"Deleted {len(self.column_names)} columns from dataset '{self.dataset.name}' (ID: {self.dataset_id})")
            return True
            
        except Exception as e:
            error_msg = f"Failed to delete {len(self.column_names) if self.column_names else 0} columns: {str(e)}"
            self.logger.error(error_msg)
            self.ui_controller.show_error_message("Delete Columns Error", error_msg)
            return False

    def undo(self):
        """Undo the delete columns command by restoring the original data."""
        try:
            if self.dataset and self.original_data is not None and self.column_positions is not None:
                # Restore original data
                self.dataset.set_data(self.original_data)
                
                # Emit event
                self.app_state.event_bus.emit(
                    DatasetOperationEvents.DATASET_COLUMN_ADDED, 
                    DatasetColumnsAddedData(dataset_id=self.dataset_id, column_positions=list(self.column_positions.values())).to_dict())
                  
                
                self.logger.info(f"Undid deleting {len(self.column_names)} columns from dataset '{self.dataset.name}'")
                return True
        except Exception as e:
            self.logger.error(f"DeleteColumnsBatchCommand Undo Error: {e}")
            return False

    def redo(self):
        """Redo the delete columns command."""
        # Re-execute with stored parameters
        return self.execute()
