"""
Command to add multiple rows to a dataset at once.
"""

from typing import Optional, List, Any, override
import pandas as pd

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import DatasetOperationEvents
from pandaplot.models.state import AppState, AppContext
from pandaplot.models.project.items import Dataset


class AddRowsBatchCommand(Command):
    """
    Command to add multiple rows to an existing dataset at a specified position.
    """

    def __init__(self, app_context: AppContext, dataset_id: str, num_rows: int, 
                 row_position: Optional[int] = None, default_values: Optional[List[Any]] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        
        self.dataset_id = dataset_id
        self.num_rows = num_rows
        self.row_position = row_position  # None means append at end
        self.default_values = default_values  # Optional default values for each column
        
        # Store state for undo
        self.original_data = None
        self.project = None
        self.dataset = None
        self.inserted_at = None

    @override
    def execute(self) -> bool:
        """Execute the add multiple rows command."""
        try:
            self.logger.info(f"Executing AddRowsBatchCommand: adding {self.num_rows} rows")
            
            # Validate input
            if self.num_rows <= 0:
                self.ui_controller.show_warning_message(
                    "Add Rows", 
                    "Number of rows must be greater than 0."
                )
                return False
            
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Add Rows", 
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
                    "Add Rows", 
                    f"Dataset with ID '{self.dataset_id}' not found."
                )
                return False
            
            if not isinstance(found_item, Dataset):
                self.ui_controller.show_error_message(
                    "Add Rows", 
                    "Selected item is not a dataset."
                )
                return False
                
            self.dataset = found_item
            
            # Get current data
            if self.dataset.data is None:
                self.ui_controller.show_warning_message(
                    "Add Rows", 
                    "Cannot add rows to dataset without structure."
                )
                return False
            
            # Store original data for undo
            self.original_data = self.dataset.data.copy()
            
            # Create default values for new rows
            new_rows_data = []
            for _ in range(self.num_rows):
                new_row_data = {}
                
                for i, column in enumerate(self.dataset.data.columns):
                    # Use provided default value if available
                    if self.default_values and i < len(self.default_values):
                        new_row_data[column] = self.default_values[i]
                    else:
                        # Generate appropriate default based on column type
                        col_dtype = self.dataset.data[column].dtype
                        
                        if pd.api.types.is_numeric_dtype(col_dtype):
                            if pd.api.types.is_integer_dtype(col_dtype):
                                new_row_data[column] = 0
                            else:
                                new_row_data[column] = 0.0
                        elif pd.api.types.is_bool_dtype(col_dtype):
                            new_row_data[column] = False
                        else:
                            new_row_data[column] = ""
                
                new_rows_data.append(new_row_data)
            
            # Create new DataFrame with the added rows
            new_data = self.dataset.data.copy()
            new_rows_df = pd.DataFrame(new_rows_data)
            
            if self.row_position is None or self.row_position >= len(new_data):
                # Append at end
                new_data = pd.concat([new_data, new_rows_df], ignore_index=True)
                self.inserted_at = len(self.dataset.data)  # Original length
            else:
                # Insert at specific position
                position = max(0, min(self.row_position, len(new_data)))
                
                # Split the dataframe and insert the new rows
                before = new_data.iloc[:position]
                after = new_data.iloc[position:]
                
                new_data = pd.concat([before, new_rows_df, after], ignore_index=True)
                self.inserted_at = position
            
            # Update dataset
            self.dataset.set_data(new_data)
            
            # Emit event
            self.app_state.event_bus.emit(DatasetOperationEvents.DATASET_ROW_ADDED, {
                'project': self.project,
                'dataset_id': self.dataset_id,
                'dataset_name': self.dataset.name,
                'row_position': self.inserted_at,
                'num_rows': self.num_rows,
                'dataset_data': self.dataset.data
            })

            self.logger.info(f"Added {self.num_rows} rows at position {self.inserted_at} to dataset '{self.dataset.name}' (ID: {self.dataset_id})")
            return True
            
        except Exception as e:
            error_msg = f"Failed to add {self.num_rows} rows: {str(e)}"
            self.logger.error(error_msg)
            self.ui_controller.show_error_message("Add Rows Error", error_msg)
            return False

    def undo(self):
        """Undo the add rows command."""
        try:
            if self.dataset and self.original_data is not None:
                # Restore original data
                self.dataset.set_data(self.original_data)
                
                # Emit event
                self.app_state.event_bus.emit(DatasetOperationEvents.DATASET_ROW_REMOVED, {
                    'project': self.project,
                    'dataset_id': self.dataset_id,
                    'dataset_name': self.dataset.name,
                    'row_position': self.inserted_at,
                    'num_rows': self.num_rows,
                    'dataset_data': self.dataset.data
                })
                
                self.logger.info(f"Undid adding {self.num_rows} rows at position {self.inserted_at} to dataset '{self.dataset.name}'")
                return True
        except Exception as e:
            self.logger.error(f"Undo Error: {e}")
            return False

    def redo(self):
        """Redo the add rows command."""
        # Re-execute with stored parameters
        return self.execute()
