"""
Command to add multiple columns to a dataset at once.
"""

from typing import Optional, List, Any, override
import pandas as pd
import numpy as np

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import DatasetOperationEvents
from pandaplot.models.state import AppState, AppContext
from pandaplot.models.project.items import Dataset


class AddColumnsBatchCommand(Command):
    """
    Command to add multiple columns to an existing dataset.
    """

    def __init__(self, app_context: AppContext, dataset_id: str, 
                 column_names: List[str], default_values: Optional[List[Any]] = None,
                 column_position: Optional[int] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.dataset_id = dataset_id
        self.column_names = column_names
        self.default_values = default_values or []
        self.column_position = column_position  # None means append at end

        # Store state for undo
        self.original_data = None
        self.project = None
        self.dataset = None
        self.inserted_columns = []

    @override
    def execute(self) -> bool:
        """Execute the add multiple columns command."""
        try:
            self.logger.info(f"Executing AddColumnsBatchCommand: adding {len(self.column_names)} columns")
            
            # Validate input
            if not self.column_names:
                self.ui_controller.show_warning_message(
                    "Add Columns", 
                    "No column names provided."
                )
                return False
            
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Add Columns", 
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
                    "Add Columns", 
                    f"Dataset with ID '{self.dataset_id}' not found."
                )
                return False
            
            if not isinstance(found_item, Dataset):
                self.ui_controller.show_error_message(
                    "Add Columns", 
                    "Selected item is not a dataset."
                )
                return False
                
            self.dataset = found_item
            
            # Get current data
            if self.dataset.data is None or self.dataset.data.empty:
                self.ui_controller.show_warning_message(
                    "Add Columns", 
                    "Cannot add columns to empty dataset."
                )
                return False
            
            # Store original data for undo
            self.original_data = self.dataset.data.copy()
            
            # Check for duplicate column names
            existing_columns = set(self.dataset.data.columns)
            duplicate_columns = [col for col in self.column_names if col in existing_columns]
            if duplicate_columns:
                self.ui_controller.show_warning_message(
                    "Add Columns", 
                    f"The following columns already exist: {', '.join(duplicate_columns)}"
                )
                return False
            
            # Check for duplicate names within the new columns
            if len(set(self.column_names)) != len(self.column_names):
                self.ui_controller.show_warning_message(
                    "Add Columns", 
                    "Duplicate column names found in the list of new columns."
                )
                return False
            
            # Create new DataFrame with the added columns
            new_data = self.dataset.data.copy()
            num_rows = len(new_data)
            
            # Create new columns data
            new_columns_data = {}
            for i, column_name in enumerate(self.column_names):
                # Use provided default value if available
                if i < len(self.default_values):
                    default_value = self.default_values[i]
                else:
                    # Try to infer a reasonable default based on existing data
                    numeric_cols = self.dataset.data.select_dtypes(include=[np.number]).columns
                    if len(numeric_cols) > 0:
                        default_value = 0
                    else:
                        default_value = ""
                
                # Create the column series
                if isinstance(default_value, (int, float)):
                    new_columns_data[column_name] = pd.Series([default_value] * num_rows, name=column_name)
                else:
                    new_columns_data[column_name] = pd.Series([str(default_value)] * num_rows, name=column_name)
            
            # Determine where to insert the columns
            if self.column_position is None or self.column_position >= len(new_data.columns):
                # Append at end
                for column_name, column_data in new_columns_data.items():
                    new_data[column_name] = column_data
                self.inserted_columns = list(new_columns_data.keys())
            else:
                # Insert at specific position
                position = max(0, min(self.column_position, len(new_data.columns)))
                
                # Get existing columns and insert new ones at the specified position
                existing_cols = list(new_data.columns)
                new_col_names = list(new_columns_data.keys())
                
                # Create the new column order
                new_column_order = (existing_cols[:position] + 
                                  new_col_names + 
                                  existing_cols[position:])
                
                # Add the new columns to the dataframe
                for column_name, column_data in new_columns_data.items():
                    new_data[column_name] = column_data
                
                # Reorder columns
                new_data = new_data[new_column_order]
                self.inserted_columns = new_col_names
            
            # Update dataset
            self.dataset.set_data(new_data)
            
            # Emit event
            self.app_state.event_bus.emit(DatasetOperationEvents.DATASET_COLUMN_ADDED, {
                'project': self.project,
                'dataset_id': self.dataset_id,
                'dataset_name': self.dataset.name,
                'column_names': self.column_names,
                'column_position': self.column_position,
                'default_values': self.default_values,
                'dataset_data': self.dataset.data
            })

            self.logger.info(f"Added {len(self.column_names)} columns to dataset '{self.dataset.name}' (ID: {self.dataset_id})")
            return True
            
        except Exception as e:
            error_msg = f"Failed to add columns: {str(e)}"
            self.logger.error(f"AddColumnsBatchCommand Error: {error_msg}")
            self.ui_controller.show_error_message("Add Columns Error", error_msg)
            return False

    def undo(self):
        """Undo the add columns command."""
        try:
            if self.dataset and self.original_data is not None:
                # Restore original data
                self.dataset.set_data(self.original_data)
                
                # Emit event
                self.app_state.event_bus.emit(DatasetOperationEvents.DATASET_COLUMN_REMOVED, {
                    'project': self.project,
                    'dataset_id': self.dataset_id,
                    'dataset_name': self.dataset.name,
                    'column_names': self.column_names,
                    'dataset_data': self.dataset.data
                })
                
                self.logger.info(f"Undid adding {len(self.column_names)} columns to dataset '{self.dataset.name}'")
                return True
        except Exception as e:
            self.logger.error(f"AddColumnsBatchCommand Undo Error: {e}")
            return False

    def redo(self):
        """Redo the add columns command."""
        # Re-execute with stored parameters
        return self.execute()
