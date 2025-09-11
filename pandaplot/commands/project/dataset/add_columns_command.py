"""
Command to add multiple columns to a dataset at once.

This version supports adding columns relative to existing positions with intuitive semantics:
- Insert columns to the left or right of specified reference positions
- Handle multiple insertions efficiently without complex position calculations
- Support both single and multiple column insertions

Usage examples:

# Insert single column to the right of position 1
AddColumnsCommand(app_context, dataset_id, ['NewCol'], [1], side='right')

# Insert multiple columns to the right of position 1 (they will be inserted consecutively)
AddColumnsCommand(app_context, dataset_id, ['Col1', 'Col2'], [1, 1], side='right')

# Insert columns to the left of different positions
AddColumnsCommand(app_context, dataset_id, ['Col1', 'Col2'], [2, 5], side='left')
"""

from typing import Optional, List, Any, Literal, override
from enum import Enum

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_data import DatasetColumnsAddedData, DatasetColumnsRemovedData
from pandaplot.models.events.event_types import DatasetOperationEvents
from pandaplot.models.state import AppState, AppContext
from pandaplot.models.project.items import Dataset
import pandas as pd


class InsertionSide(Enum):
    """Enum for specifying where to insert columns relative to reference positions."""
    LEFT = "left"
    RIGHT = "right"


class AddColumnsCommand(Command):
    """
    Command to add multiple columns to an existing dataset.
    
    Supports adding columns to the left or right of specified reference positions.
    When multiple columns are added at the same reference position, they are inserted consecutively.
    """

    def __init__(self, app_context: AppContext, dataset_id: str, column_names: List[str],
                 reference_positions: List[int],
                 side: Literal['left', 'right'] = 'right',
                 default_values: Optional[List[Any]] = None):
        """
        Initialize the AddColumnsCommand.
        
        Args:
            app_context: Application context
            dataset_id: ID of the target dataset
            column_names: Names of columns to add
            reference_positions: Positions of existing columns to insert relative to
            side: Whether to insert 'left' or 'right' of reference positions
            default_values: Optional default values for new columns
        """
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.dataset_id = dataset_id
        self.column_names = column_names
        self.reference_positions = reference_positions
        self.side = InsertionSide(side)
        self.default_values = default_values or [None] * len(column_names)

        # Store state for undo
        self.original_data = None
        self.project = None
        self.dataset = None
        self.final_insertion_positions = []  # Store actual positions where columns were inserted

    @override
    def execute(self) -> bool:
        """Execute the add multiple columns command."""
        try:
            self.logger.info(f"Executing AddColumnsCommand: adding {len(self.column_names)} columns {self.side.value}")
            
            # Validate input
            if not self.column_names:
                self.ui_controller.show_warning_message(
                    "Add Columns", 
                    "No column names provided."
                )
                return False
            
            if len(self.column_names) != len(self.reference_positions):
                self.ui_controller.show_warning_message(
                    "Add Columns", 
                    "Number of column names must match number of reference positions."
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
            
            # Validate reference positions
            num_cols = len(self.dataset.data.columns)
            for i, pos in enumerate(self.reference_positions):
                if pos < 0 or pos >= num_cols:
                    self.ui_controller.show_error_message(
                        "Add Columns", 
                        f"Reference position {pos} for column '{self.column_names[i]}' is out of bounds (0-{num_cols-1})."
                    )
                    return False
            
            # Check for duplicate column names
            existing_columns = set(self.dataset.data.columns)
            duplicate_columns = [name for name in self.column_names if name in existing_columns]
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
            
            # Insert columns using the new logic
            new_data = self._insert_columns_with_new_logic()
            
            # Update dataset
            self.dataset.set_data(new_data)
            
            # Emit event with final insertion positions
            self.app_state.event_bus.emit(DatasetOperationEvents.DATASET_COLUMN_ADDED, DatasetColumnsAddedData(
                dataset_id=self.dataset_id,
                column_positions=self.final_insertion_positions
            ).to_dict())

            self.logger.info(f"Added {len(self.column_names)} columns to dataset '{self.dataset.name}' (ID: {self.dataset_id})")
            return True
            
        except Exception as e:
            error_msg = f"Failed to add columns: {str(e)}"
            self.logger.error(f"AddColumnsCommand Error: {error_msg}")
            self.ui_controller.show_error_message("Add Columns Error", error_msg)
            return False

    def _insert_columns_with_new_logic(self) -> pd.DataFrame:
        """
        Insert columns using the new intuitive logic.
        
        Groups consecutive reference positions and inserts corresponding columns
        after each group. Non-consecutive positions get individual insertions.
        
        Returns:
            New DataFrame with columns inserted
        """
        # Start with a copy of the current data
        result_data = self.dataset.data.copy()
        self.final_insertion_positions = []
        
        # Group consecutive positions
        consecutive_groups = self._group_consecutive_positions()
        
        # Process groups from right to left to avoid position shifts
        for group in reversed(consecutive_groups):
            group_positions = [item[0] for item in group]
            group_columns = [item[1] for item in group]
            group_defaults = [item[2] for item in group]
            group_indices = [item[3] for item in group]
            
            # Calculate insertion position for this group
            if self.side == InsertionSide.LEFT:
                # Insert before the first position in the group
                insertion_pos = min(group_positions)
            else:  # RIGHT
                # Insert after the last position in the group
                insertion_pos = max(group_positions) + 1
            
            # Insert all columns for this group as a block
            result_data = self._insert_column_block(result_data, insertion_pos, group_columns, group_defaults)
            
            # Track final positions for this group
            for i, original_idx in enumerate(group_indices):
                self.final_insertion_positions.append((insertion_pos + i, original_idx))
        
        # Sort final positions by original index to match the order of input column names
        self.final_insertion_positions.sort(key=lambda x: x[1])
        self.final_insertion_positions = [pos for pos, _ in self.final_insertion_positions]
        
        return result_data
    
    def _group_consecutive_positions(self):
        """
        Group consecutive reference positions with their corresponding column data.
        
        Returns:
            List of groups, where each group contains consecutive positions
        """
        # Create list of (reference_position, column_name, default_value, original_index)
        items = list(zip(self.reference_positions, self.column_names, self.default_values, range(len(self.column_names))))
        
        # Sort by reference position
        items.sort(key=lambda x: x[0])
        
        if not items:
            return []
        
        groups = []
        current_group = [items[0]]
        
        for i in range(1, len(items)):
            current_pos = items[i][0]
            prev_pos = items[i-1][0]
            
            # If positions are consecutive, add to current group
            if current_pos == prev_pos + 1:
                current_group.append(items[i])
            else:
                # Start a new group
                groups.append(current_group)
                current_group = [items[i]]
        
        # Don't forget the last group
        groups.append(current_group)
        
        return groups
    
    def _insert_column_block(self, data: pd.DataFrame, position: int, column_names: List[str], default_values: List[Any]) -> pd.DataFrame:
        """
        Insert multiple columns as a block at the specified position.
        
        Args:
            data: DataFrame to insert into
            position: Position to insert at (0-based)
            column_names: Names of the new columns
            default_values: Default values for the new columns
            
        Returns:
            New DataFrame with the columns inserted
        """
        import numpy as np
        
        # Clamp position to valid range
        position = max(0, min(position, len(data.columns)))
        
        # Prepare new columns data
        new_columns_data = {}
        num_rows = len(data)
        
        for col_name, default_val in zip(column_names, default_values):
            # Determine default value
            if default_val is not None:
                final_default = default_val
            else:
                # Try to infer a reasonable default based on existing data
                numeric_cols = data.select_dtypes(include=[np.number]).columns
                if len(numeric_cols) > 0:
                    final_default = 0
                else:
                    final_default = ""
            
            # Create the column series
            if isinstance(final_default, (int, float)):
                new_columns_data[col_name] = pd.Series([final_default] * num_rows, name=col_name, index=data.index)
            else:
                new_columns_data[col_name] = pd.Series([str(final_default)] * num_rows, name=col_name, index=data.index)
        
        if position >= len(data.columns):
            # Append at end
            new_df = pd.DataFrame(new_columns_data, index=data.index)
            result = pd.concat([data, new_df], axis=1)
        else:
            # Insert at specific position using pd.concat to avoid fragmentation
            columns = list(data.columns)
            
            # Split into before and after
            before_cols = columns[:position]
            after_cols = columns[position:]
            
            # Create DataFrames
            before_df = data[before_cols] if before_cols else pd.DataFrame(index=data.index)
            after_df = data[after_cols] if after_cols else pd.DataFrame(index=data.index)
            new_df = pd.DataFrame(new_columns_data, index=data.index)
            
            # Concatenate all parts at once to avoid fragmentation
            result = pd.concat([before_df, new_df, after_df], axis=1)
        
        return result

    def undo(self):
        """Undo the add columns command."""
        try:
            if self.dataset and self.original_data is not None:
                # Restore original data
                self.dataset.set_data(self.original_data)
                
                # Emit event
                self.app_state.event_bus.emit(DatasetOperationEvents.DATASET_COLUMN_REMOVED, DatasetColumnsRemovedData(
                    dataset_id=self.dataset_id,
                    column_positions=self.final_insertion_positions
                ).to_dict())

                self.logger.info(f"Undid adding {len(self.column_names)} columns to dataset '{self.dataset.name}'")
                return True
        except Exception as e:
            self.logger.error(f"AddColumnsCommand Undo Error: {e}")
            return False

    def redo(self):
        """Redo the add columns command."""
        # Re-execute with stored parameters
        return self.execute()
