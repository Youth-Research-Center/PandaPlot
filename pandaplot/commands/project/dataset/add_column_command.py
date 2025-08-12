"""
Command to add a new column to a dataset.
"""

import logging
from typing import Optional, override
import pandas as pd
import numpy as np
from pandaplot.commands.base_command import Command
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.gui.controllers.ui_controller import UIController


class AddColumnCommand(Command):
    """
    Command to add a new column to an existing dataset.
    """

    def __init__(self, app_context: AppContext, dataset_id: str, column_name: Optional[str] = None, default_value: str|int|float = ""):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        
        self.dataset_id = dataset_id
        self.column_name = column_name
        self.default_value = default_value
        
        # Store state for undo
        self.original_data = None
        self.project = None
        self.dataset = None  # Will be cast to Dataset when found

    @override
    def execute(self) -> bool:
        """Execute the add column command."""
        try:
            self.logger.info("Executing AddColumnCommand")
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Add Column", 
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
                    "Add Column", 
                    f"Dataset with ID '{self.dataset_id}' not found."
                )
                return False
            
            # Import Dataset here to avoid circular imports
            from pandaplot.models.project.items.dataset import Dataset
            if not isinstance(found_item, Dataset):
                self.ui_controller.show_error_message(
                    "Add Column", 
                    "Selected item is not a dataset."
                )
                return False
                
            self.dataset = found_item
            
            # Get current data
            if self.dataset.data is None or self.dataset.data.empty:
                self.ui_controller.show_warning_message(
                    "Add Column", 
                    "Cannot add column to empty dataset."
                )
                return False
            
            # Store original data for undo
            self.original_data = self.dataset.data.copy()
            
            # Get column name if not provided
            if self.column_name is None:
                self.column_name = self.ui_controller.get_text_input(
                    "Add Column", 
                    "Enter column name:",
                    default_text="New Column"
                )
                
            if not self.column_name:
                return False  # User cancelled
            
            # Check if column already exists
            if self.column_name in self.dataset.data.columns:
                self.ui_controller.show_warning_message(
                    "Add Column", 
                    f"Column '{self.column_name}' already exists."
                )
                return False
            
            # Determine default value
            if self.default_value is None:
                # Try to infer a reasonable default based on existing data
                numeric_cols = self.dataset.data.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    self.default_value = 0
                else:
                    self.default_value = ""
            
            # Add the new column
            num_rows = len(self.dataset.data)
            if isinstance(self.default_value, (int, float)):
                new_column = pd.Series([self.default_value] * num_rows, name=self.column_name)
            else:
                new_column = pd.Series([str(self.default_value)] * num_rows, name=self.column_name)
            
            # Create new DataFrame with the added column
            new_data = self.dataset.data.copy()
            new_data[self.column_name] = new_column
            
            # Update dataset
            self.dataset.set_data(new_data)
            
            # Emit event
            self.app_state.event_bus.emit('dataset_column_added', {
                'project': self.project,
                'dataset_id': self.dataset_id,
                'dataset_name': self.dataset.name,
                'column_name': self.column_name,
                'default_value': self.default_value,
                'dataset_data': self.dataset.data
            })

            print(f"AddColumnCommand: Added column '{self.column_name}' to dataset '{self.dataset.name}' (ID: {self.dataset_id})")
            return True
            
        except Exception as e:
            error_msg = f"Failed to add column: {str(e)}"
            print(f"AddColumnCommand Error: {error_msg}")
            self.ui_controller.show_error_message("Add Column Error", error_msg)
            return False

    def undo(self):
        """Undo the add column command."""
        try:
            if self.dataset and self.original_data is not None:
                # Restore original data
                self.dataset.set_data(self.original_data)
                
                # Emit event
                self.app_state.event_bus.emit('dataset_column_removed', {
                    'project': self.project,
                    'dataset_id': self.dataset_id,
                    'dataset_name': self.dataset.name,
                    'column_name': self.column_name,
                    'dataset_data': self.dataset.data
                })
                
                print(f"AddColumnCommand: Undid adding column '{self.column_name}' to dataset '{self.dataset.name}'")
                return True
        except Exception as e:
            print(f"AddColumnCommand Undo Error: {e}")
            return False

    def redo(self):
        """Redo the add column command."""
        # Re-execute with stored parameters
        return self.execute(column_name=self.column_name, default_value=self.default_value)

