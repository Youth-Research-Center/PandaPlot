from typing import List, Union, override

from pandaplot.commands.project.dataset.dataset_command import DatasetCommand
from pandaplot.models.events.event_data import DatasetColumnsAddedData, DatasetColumnsRemovedData
from pandaplot.models.events.event_types import DatasetOperationEvents
from pandaplot.models.state.app_context import AppContext


class DeleteColumnsCommand(DatasetCommand):
    """
    Command to delete multiple columns from an existing dataset.
    Supports both column positions and column names for backward compatibility.
    """

    def __init__(self, app_context: AppContext, dataset_id: str,
                 column_specs: Union[List[int], List[str]]):
        super().__init__(app_context, dataset_id)

        self.column_specs = column_specs

        # These will be populated in execute() after we have access to the dataset
        self.column_names = []
        self.column_positions = []

        # Store state for undo
        self.original_data = None
        self.deleted_columns_data = None

    @override
    def execute(self) -> bool:
        """Execute the delete columns command."""
        try:
            self.logger.info(f"Executing DeleteColumnsCommand for {len(self.column_specs)} column specifications")
            
            # Validate input
            if not self.column_specs:
                self.ui_controller.show_warning_message(
                    "Delete Columns", 
                    "No columns specified for deletion."
                )
                return False
            
            if not self._validate_and_get_dataset("Delete Columns"):
                return False
            
            # Get current data
            if self.dataset.data is None or self.dataset.data.empty:
                self.ui_controller.show_warning_message(
                    "Delete Columns", 
                    "Cannot delete columns from empty dataset."
                )
                return False
            
            # Resolve column names and positions based on input type
            self._resolve_columns()
            
            # Validate resolved columns
            if not self.column_names:
                self.ui_controller.show_warning_message(
                    "Delete Columns", 
                    "No valid columns found for deletion."
                )
                return False
            
            # Check if all resolved columns exist
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
            
            # Store the deleted columns data for potential restoration
            self.deleted_columns_data = {}
            for col_name in self.column_names:
                self.deleted_columns_data[col_name] = self.dataset.data[col_name].copy()
            
            # Create new DataFrame with the columns removed
            new_data = self.dataset.data.drop(columns=self.column_names)
            
            # Update dataset
            self.dataset.set_data(new_data)
            
            # Emit event
            self.app_state.event_bus.emit(DatasetOperationEvents.DATASET_COLUMN_REMOVED, 
                                          DatasetColumnsRemovedData(dataset_id=self.dataset_id, column_positions=self.column_positions).to_dict()
            )

            self.logger.info(f"Deleted {len(self.column_names)} columns from dataset '{self.dataset.name}' (ID: {self.dataset_id})")
            return True
            
        except Exception as e:
            error_msg = f"Failed to delete {len(self.column_specs) if self.column_specs else 0} columns: {str(e)}"
            self.logger.error(error_msg)
            self.ui_controller.show_error_message("Delete Columns Error", error_msg)
            return False

    def _resolve_columns(self):
        """
        Resolve column names and positions based on the input specification.
        Supports both column positions (integers) and column names (strings).
        """
        if not self.column_specs or not self.dataset or self.dataset.data is None:
            return
        
        all_columns = list(self.dataset.data.columns)
        self.column_names = []
        self.column_positions = []
        
        for spec in self.column_specs:
            if isinstance(spec, int):
                # Position-based specification
                if 0 <= spec < len(all_columns):
                    column_name = all_columns[spec]
                    self.column_names.append(column_name)
                    self.column_positions.append(spec)
                else:
                    self.logger.warning(f"Column position {spec} is out of range (0-{len(all_columns)-1})")
            elif isinstance(spec, str):
                # Name-based specification (backward compatibility)
                if spec in all_columns:
                    position = all_columns.index(spec)
                    self.column_names.append(spec)
                    self.column_positions.append(position)
                else:
                    self.logger.warning(f"Column '{spec}' not found in dataset")
            else:
                self.logger.warning(f"Invalid column specification: {spec}")

    def undo(self):
        """Undo the delete columns command by restoring the original data."""
        try:
            if self.dataset and self.original_data is not None and self.column_positions:
                # Restore original data
                self.dataset.set_data(self.original_data)
                
                # Emit event
                self.app_state.event_bus.emit(
                    DatasetOperationEvents.DATASET_COLUMN_ADDED, 
                    DatasetColumnsAddedData(dataset_id=self.dataset_id, column_positions=self.column_positions).to_dict())
                
                self.logger.info(f"Undid deleting {len(self.column_names)} columns from dataset '{self.dataset.name}'")
                return True
        except Exception as e:
            self.logger.error(f"DeleteColumnsCommand Undo Error: {e}")
            return False

    def redo(self):
        """Redo the delete columns command."""
        # Re-execute with stored parameters
        return self.execute()
