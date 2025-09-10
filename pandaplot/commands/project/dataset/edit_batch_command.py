from typing import List, Any, override
from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_data import DatasetDataChangedData
from pandaplot.models.events.event_types import DatasetEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from tests.commands.project import dataset


class EditBatchCommand(Command):
    def __init__(self, app_context: AppContext, dataset_id: str, start_row: int, start_column: int, new_data: List[List[Any]]):
        super().__init__()
        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.dataset_id = dataset_id
        self.start_row = start_row
        self.start_column = start_column
        self.new_data = new_data
        self.end_row = start_row + len(new_data) - 1
        self.end_column = start_column + len(new_data[0]) - 1 if new_data else start_column
        self.old_data = None  # Will store the original data for undo

    @override
    def execute(self) -> bool:
        try:
            self.logger.info("Executing EditBatchCommand")
            if not self.app_context.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Batch Edit", 
                    "Please open or create a project first."
                )
                return False
                
            self.project = self.app_context.app_state.current_project
            if not self.project:
                return False

            # Find the dataset
            found_item = self.project.find_item(self.dataset_id)
            if not found_item:
                self.ui_controller.show_error_message(
                    "Batch Edit", 
                    f"Dataset with ID '{self.dataset_id}' not found."
                )
                return False
            
            if not isinstance(found_item, Dataset):
                self.ui_controller.show_error_message(
                    "Batch Edit", 
                    "Selected item is not a dataset."
                )
                return False

            self.dataset = found_item

            # Get current data
            if self.dataset.data is None:
                self.ui_controller.show_warning_message(
                    "Batch Edit", 
                    "Cannot edit cells in dataset without structure."
                )
                return False

            # Validate input data
            if not self.new_data:
                self.ui_controller.show_warning_message(
                    "Batch Edit", 
                    "No data provided for batch edit."
                )
                return False

            # Check if all rows have the same length
            expected_cols = len(self.new_data[0])
            for i, row in enumerate(self.new_data):
                if len(row) != expected_cols:
                    self.ui_controller.show_error_message(
                        "Batch Edit", 
                        f"Row {i} has {len(row)} columns, expected {expected_cols}. All rows must have the same length."
                    )
                    return False

            # Check if data fits in current dataframe dimensions
            current_rows, current_cols = self.dataset.data.shape
            
            # Check if we need to add rows
            if self.end_row >= current_rows:
                rows_to_add = self.end_row - current_rows + 1
                self.logger.info(f"Need to add {rows_to_add} rows")
                # TODO: Implement adding rows to accommodate new data
                self.ui_controller.show_warning_message(
                    "Batch Edit", 
                    f"Data extends beyond current rows. Adding {rows_to_add} rows is not yet implemented."
                )
                return False

            # Check if we need to add columns
            if self.end_column >= current_cols:
                cols_to_add = self.end_column - current_cols + 1
                self.logger.info(f"Need to add {cols_to_add} columns")
                # TODO: Implement adding columns to accommodate new data
                self.ui_controller.show_warning_message(
                    "Batch Edit", 
                    f"Data extends beyond current columns. Adding {cols_to_add} columns is not yet implemented."
                )
                return False

            # Store original data for undo
            self.old_data = self.dataset.data.iloc[
                self.start_row:self.end_row + 1, 
                self.start_column:self.end_column + 1
            ].copy()

            # Apply the batch edit
            for i, row_data in enumerate(self.new_data):
                for j, value in enumerate(row_data):
                    row_idx = self.start_row + i
                    col_idx = self.start_column + j
                    self.dataset.data.iloc[row_idx, col_idx] = value

            # Emit event for batch data change
            self.app_context.event_bus.emit(
                DatasetEvents.DATASET_DATA_CHANGED, 
                DatasetDataChangedData(
                    dataset_id=self.dataset_id, 
                    start_index=(self.start_row, self.start_column), 
                    end_index=(self.end_row, self.end_column)).to_dict()
            )

            return True
            
        except Exception as e:
            error_msg = f"Failed to perform batch edit at starting position ({self.start_row}, {self.start_column}): {str(e)}"
            self.logger.error(error_msg)
            self.ui_controller.show_error_message("Batch Edit Error", error_msg)
            return False

    def undo(self):
        """Restore the original data"""
        if self.old_data is not None and self.dataset and self.dataset.data is not None:
            self.dataset.data.iloc[
                self.start_row:self.end_row + 1, 
                self.start_column:self.end_column + 1
            ] = self.old_data
            
            self.app_context.event_bus.emit(DatasetEvents.DATASET_DATA_CHANGED, {
                "start_index": (self.start_row, self.start_column),
                "end_index": (self.end_row, self.end_column),
                "new_data": self.old_data.values.tolist(),
                "old_data": self.new_data
            })
    
    def redo(self):
        """Reapply the batch edit"""
        if self.dataset and self.dataset.data is not None:
            for i, row_data in enumerate(self.new_data):
                for j, value in enumerate(row_data):
                    row_idx = self.start_row + i
                    col_idx = self.start_column + j
                    self.dataset.data.iloc[row_idx, col_idx] = value
            
            self.app_context.event_bus.emit(DatasetEvents.DATASET_DATA_CHANGED, {
                "start_index": (self.start_row, self.start_column),
                "end_index": (self.end_row, self.end_column),
                "new_data": self.new_data,
                "old_data": self.old_data.values.tolist() if self.old_data is not None else None
            })
