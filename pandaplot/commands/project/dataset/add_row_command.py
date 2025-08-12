"""
Command to add a new row to a dataset.
"""

import logging
from typing import Optional, override
import pandas as pd
from pandaplot.commands.base_command import Command
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.gui.controllers.ui_controller import UIController


class AddRowCommand(Command):
    """
    Command to add a new row to an existing dataset.
    """

    def __init__(self, app_context: AppContext, dataset_id: str, row_position: Optional[int] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        
        self.dataset_id = dataset_id
        self.row_position = row_position  # None means append at end
        
        # Store state for undo
        self.original_data = None
        self.project = None
        self.dataset = None  # Will be cast to Dataset when found
        self.inserted_at = None

    @override
    def execute(self) -> bool:
        """Execute the add row command."""
        try:
            self.logger.info("Executing AddRowCommand")
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Add Row", 
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
                    "Add Row", 
                    f"Dataset with ID '{self.dataset_id}' not found."
                )
                return False
            
            # Import Dataset here to avoid circular imports
            from pandaplot.models.project.items.dataset import Dataset
            if not isinstance(found_item, Dataset):
                self.ui_controller.show_error_message(
                    "Add Row", 
                    "Selected item is not a dataset."
                )
                return False
                
            self.dataset = found_item
            
            # Get current data
            if self.dataset.data is None:
                self.ui_controller.show_warning_message(
                    "Add Row", 
                    "Cannot add row to dataset without structure."
                )
                return False
            
            # Store original data for undo
            self.original_data = self.dataset.data.copy()
            
            # Create new row with appropriate default values
            new_row_data = {}
            for column in self.dataset.data.columns:
                col_dtype = self.dataset.data[column].dtype
                
                if pd.api.types.is_numeric_dtype(col_dtype):
                    # For numeric columns, use 0 or NaN
                    if pd.api.types.is_integer_dtype(col_dtype):
                        new_row_data[column] = 0
                    else:
                        new_row_data[column] = 0.0
                elif pd.api.types.is_bool_dtype(col_dtype):
                    new_row_data[column] = False
                else:
                    # For string/object columns, use empty string
                    new_row_data[column] = ""
            
            # Create new DataFrame with the added row
            new_data = self.dataset.data.copy()
            
            if self.row_position is None or self.row_position >= len(new_data):
                # Append at end
                new_row = pd.DataFrame([new_row_data])
                new_data = pd.concat([new_data, new_row], ignore_index=True)
                self.inserted_at = len(self.dataset.data)  # Original length
            else:
                # Insert at specific position
                position = max(0, min(self.row_position, len(new_data)))
                
                # Split the dataframe and insert the new row
                before = new_data.iloc[:position]
                after = new_data.iloc[position:]
                new_row = pd.DataFrame([new_row_data])
                
                new_data = pd.concat([before, new_row, after], ignore_index=True)
                self.inserted_at = position
            
            # Update dataset
            self.dataset.set_data(new_data)
            
            # Emit event
            self.app_state.event_bus.emit('dataset_row_added', {
                'project': self.project,
                'dataset_id': self.dataset_id,
                'dataset_name': self.dataset.name,
                'row_position': self.inserted_at,
                'dataset_data': self.dataset.data
            })

            print(f"AddRowCommand: Added row at position {self.inserted_at} to dataset '{self.dataset.name}' (ID: {self.dataset_id})")
            return True
            
        except Exception as e:
            error_msg = f"Failed to add row: {str(e)}"
            print(f"AddRowCommand Error: {error_msg}")
            self.ui_controller.show_error_message("Add Row Error", error_msg)
            return False

    def undo(self):
        """Undo the add row command."""
        try:
            if self.dataset and self.original_data is not None:
                # Restore original data
                self.dataset.set_data(self.original_data)
                
                # Emit event
                self.app_state.event_bus.emit('dataset_row_removed', {
                    'project': self.project,
                    'dataset_id': self.dataset_id,
                    'dataset_name': self.dataset.name,
                    'row_position': self.inserted_at,
                    'dataset_data': self.dataset.data
                })
                
                print(f"AddRowCommand: Undid adding row at position {self.inserted_at} to dataset '{self.dataset.name}'")
                return True
        except Exception as e:
            print(f"AddRowCommand Undo Error: {e}")
            return False

    def redo(self):
        """Redo the add row command."""
        # Re-execute with stored parameters
        return self.execute()
