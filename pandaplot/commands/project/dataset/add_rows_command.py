"""
Command to add multiple rows to a dataset at once.

This version supports adding rows relative to existing positions with intuitive semantics:
- Insert rows above or below specified reference positions
- Handle multiple insertions efficiently by grouping consecutive selections
- Support both single and multiple row insertions

Usage examples:

# Insert single row below position 1
AddRowsCommand(app_context, dataset_id, 1, ['NewRow'], side='below')

# Insert multiple rows below consecutive positions (they will be inserted as a block)
AddRowsCommand(app_context, dataset_id, [1, 2], ['Row1', 'Row2'], side='below')

# Insert rows above different positions 
AddRowsCommand(app_context, dataset_id, [2, 5], ['Row1', 'Row2'], side='above')
"""

from typing import List, Any, Literal, override
from enum import Enum

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_data import DatasetRowsAddedData, DatasetRowsRemovedData
from pandaplot.models.events.event_types import DatasetOperationEvents
from pandaplot.models.state import AppState, AppContext
from pandaplot.models.project.items import Dataset
import pandas as pd


class InsertionSide(Enum):
    """Enum for specifying where to insert rows relative to reference positions."""
    ABOVE = "above"
    BELOW = "below"


class AddRowsCommand(Command):
    """
    Command to add multiple rows to an existing dataset.
    
    Supports adding rows above or below specified reference positions.
    When multiple rows are added at consecutive reference positions, they are inserted as groups.
    """

    def __init__(self, app_context: AppContext, dataset_id: str,
                 reference_positions: List[int],
                 side: Literal['above', 'below'] = 'below'):
        """
        Initialize the AddRowsCommand.
        
        Args:
            app_context: Application context
            dataset_id: ID of the target dataset
            reference_positions: Positions of existing rows to insert relative to
            side: Whether to insert 'above' or 'below' reference positions
        """
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        
        self.dataset_id = dataset_id
        self.reference_positions = reference_positions
        self.side = InsertionSide(side)
        
        # Store state for undo
        self.original_data = None
        self.project = None
        self.dataset = None
        self.final_insertion_positions = []  # Store actual positions where rows were inserted

    @override
    def execute(self) -> bool:
        """Execute the add multiple rows command."""
        try:
            self.logger.info(f"Executing AddRowsCommand: adding {len(self.reference_positions)} rows {self.side.value}")
            
            # Validate input
            if not self.reference_positions:
                self.ui_controller.show_warning_message(
                    "Add Rows", 
                    "No reference positions provided."
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
            
            # Validate reference positions
            num_rows = len(self.dataset.data)
            for i, pos in enumerate(self.reference_positions):
                if pos < 0 or pos >= num_rows:
                    self.ui_controller.show_error_message(
                        "Add Rows", 
                        f"Reference position {pos} is out of bounds (0-{num_rows-1})."
                    )
                    return False
            
            # Insert rows using the new logic
            new_data = self._insert_rows_with_new_logic(self.dataset.data)
            
            # Update dataset
            self.dataset.set_data(new_data)
            
            # Emit event with final insertion positions
            self.app_state.event_bus.emit(DatasetOperationEvents.DATASET_ROW_ADDED, DatasetRowsAddedData(
                dataset_id=self.dataset_id,
                row_positions=self.final_insertion_positions
            ).to_dict())

            self.logger.info(f"Added {len(self.reference_positions)} rows to dataset '{self.dataset.name}' (ID: {self.dataset_id})")
            return True
            
        except Exception as e:
            error_msg = f"Failed to add rows: {str(e)}"
            self.logger.error(f"AddRowsCommand Error: {error_msg}")
            self.ui_controller.show_error_message("Add Rows Error", error_msg)
            return False

    def _insert_rows_with_new_logic(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Insert rows using the new intuitive logic.
        
        Groups consecutive reference positions and inserts rows after each group.
        
        Returns:
            New DataFrame with rows inserted
        """
        # Start with a copy of the current data
        result_data = data.copy()
        self.final_insertion_positions = []
        
        # Group consecutive positions
        consecutive_groups = self._group_consecutive_positions(self.reference_positions)
        
        # Process each group from bottom to top to avoid position shifts
        for group in reversed(consecutive_groups):
            # Determine insertion position for this group
            if self.side == InsertionSide.ABOVE:
                # Insert above the first row in the group
                insertion_pos = min(group)
            else:  # BELOW
                # Insert below the last row in the group
                insertion_pos = max(group) + 1
            
            # Insert one row per position in the group
            rows_to_insert = len(group)
            result_data = self._insert_row_block(result_data, insertion_pos, rows_to_insert)
            
            # Track the final positions
            for i in range(rows_to_insert):
                self.final_insertion_positions.append(insertion_pos + i)
        
        # Reverse the final positions since we processed groups in reverse order
        self.final_insertion_positions.reverse()
        
        return result_data
    
    def _group_consecutive_positions(self, positions: List[int]) -> List[List[int]]:
        """
        Group consecutive positions together.
        
        Args:
            positions: List of reference positions
            
        Returns:
            List of groups, where each group contains consecutive positions
        """
        if not positions:
            return []
        
        # Sort positions to handle them in order
        sorted_positions = sorted(set(positions))  # Remove duplicates and sort
        
        groups = []
        current_group = [sorted_positions[0]]
        
        for i in range(1, len(sorted_positions)):
            pos = sorted_positions[i]
            prev_pos = sorted_positions[i-1]
            
            # Check if this position is consecutive to the previous one
            if pos == prev_pos + 1:
                current_group.append(pos)
            else:
                groups.append(current_group)
                current_group = [pos]
        
        groups.append(current_group)
        return groups
    
    def _insert_row_block(self, data: pd.DataFrame, position: int, num_rows: int) -> pd.DataFrame:
        """
        Insert multiple rows as a block at the specified position.
        
        Args:
            data: DataFrame to insert into
            position: Position to insert at (0-based)
            num_rows: Number of rows to insert
            
        Returns:
            New DataFrame with the rows inserted
        """
        # Clamp position to valid range
        position = max(0, min(position, len(data)))
        
        # Create new rows with default values
        new_rows_data = []
        for _ in range(num_rows):
            new_row = {}
            for column in data.columns:
                new_row[column] = self._get_default_value_for_column(data, column)
            new_rows_data.append(new_row)
        
        # Create DataFrame for new rows
        new_rows_df = pd.DataFrame(new_rows_data, columns=data.columns)
        
        if position >= len(data):
            # Append at end
            result = pd.concat([data, new_rows_df], ignore_index=True)
        else:
            # Insert at specific position
            before = data.iloc[:position]
            after = data.iloc[position:]
            result = pd.concat([before, new_rows_df, after], ignore_index=True)
        
        return result
    
    def _get_default_value_for_column(self, data: pd.DataFrame, column: str) -> Any:
        """Generate appropriate default value based on column type."""
        col_dtype = data[column].dtype
        
        if pd.api.types.is_numeric_dtype(col_dtype):
            if pd.api.types.is_integer_dtype(col_dtype):
                return 0
            else:
                return 0.0
        elif pd.api.types.is_bool_dtype(col_dtype):
            return False
        else:
            return ""

    def undo(self):
        """Undo the add rows command."""
        try:
            if self.dataset and self.original_data is not None:
                # Restore original data
                self.dataset.set_data(self.original_data)
                
                # Emit event
                self.app_state.event_bus.emit(DatasetOperationEvents.DATASET_ROW_REMOVED, DatasetRowsRemovedData(
                    dataset_id=self.dataset_id,
                    row_positions=self.final_insertion_positions
                ).to_dict())

                self.logger.info(f"Undid adding {len(self.reference_positions)} rows to dataset '{self.dataset.name}'")
                return True
        except Exception as e:
            self.logger.error(f"AddRowsCommand Undo Error: {e}")
            return False

    def redo(self):
        """Redo the add rows command."""
        # Re-execute with stored parameters
        return self.execute()
