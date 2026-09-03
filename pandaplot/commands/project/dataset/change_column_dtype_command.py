from typing import Any, Dict, Union, override

import numpy as np
import pandas as pd

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_data import DatasetDataChangedData
from pandaplot.models.events.event_types import DatasetEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState


class ChangeColumnDtypeCommand(Command):
    """
    Command to change the data type of a column in a dataset.
    Handles data conversion and removes values that cannot be converted.
    """

    def __init__(self, app_context: AppContext, dataset_id: str, 
                 column_index: int, target_dtype: str):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        
        self.dataset_id = dataset_id
        self.column_index = column_index
        self.target_dtype = target_dtype
        
        # Store state for undo
        self.original_data = None
        self.original_dtype = None
        self.column_name = None
        self.conversion_report = {}
        self.project = None
        self.dataset = None

    @override
    def execute(self) -> CommandResult:
        """Execute the change column dtype command."""
        try:
            self.logger.info(f"Executing ChangeColumnDtypeCommand for column {self.column_index} to {self.target_dtype}")
            
            if not self.app_state.has_project:
                self.logger.warning("ChangeColumnDtypeCommand.execute: no project is currently loaded")
                self.ui_controller.show_warning_message(
                    "Change Column Type",
                    "Please open or create a project first."
                )
                return CommandResult.FAILURE

            self.project = self.app_state.current_project
            if not self.project:
                self.logger.warning("ChangeColumnDtypeCommand.execute: has_project is True but current_project is None")
                return CommandResult.FAILURE

            # Find the dataset
            found_item = self.project.find_item(self.dataset_id)
            if not found_item:
                self.logger.warning(
                    "ChangeColumnDtypeCommand.execute: dataset '%s' not found", self.dataset_id,
                )
                self.ui_controller.show_error_message(
                    "Change Column Type",
                    f"Dataset with ID '{self.dataset_id}' not found."
                )
                return CommandResult.FAILURE

            if not isinstance(found_item, Dataset):
                self.logger.warning(
                    "ChangeColumnDtypeCommand.execute: item '%s' is not a Dataset (got %s)",
                    self.dataset_id, type(found_item).__name__,
                )
                self.ui_controller.show_error_message(
                    "Change Column Type",
                    "Selected item is not a dataset."
                )
                return CommandResult.FAILURE

            self.dataset = found_item

            # Validate dataset has data
            if self.dataset.data is None or self.dataset.data.empty:
                self.logger.warning(
                    "ChangeColumnDtypeCommand.execute: dataset '%s' has no data (empty dataset)", self.dataset_id,
                )
                self.ui_controller.show_warning_message(
                    "Change Column Type",
                    "Cannot change column type in empty dataset."
                )
                return CommandResult.FAILURE

            # Validate column index
            if self.column_index < 0 or self.column_index >= len(self.dataset.data.columns):
                self.logger.warning(
                    "ChangeColumnDtypeCommand.execute: column_index %s out of range for dataset '%s' (%d columns)",
                    self.column_index, self.dataset_id, len(self.dataset.data.columns),
                )
                self.ui_controller.show_error_message(
                    "Change Column Type",
                    f"Column index {self.column_index} is out of range."
                )
                return CommandResult.FAILURE

            # Get column information
            self.column_name = self.dataset.data.columns[self.column_index]
            self.original_data = self.dataset.data[self.column_name].copy()
            self.original_dtype = str(self.dataset.data[self.column_name].dtype)
            
            # Check if conversion is needed
            if self.original_dtype == self.target_dtype:
                self.ui_controller.show_info_message(
                    "Change Column Type", 
                    f"Column '{self.column_name}' is already of type {self.target_dtype}."
                )
                return CommandResult.NOOP

            # Perform the conversion
            conversion_result = self._convert_column_dtype()

            if not conversion_result:
                self.logger.warning(
                    "ChangeColumnDtypeCommand.execute: conversion to '%s' failed for column '%s' in dataset '%s'",
                    self.target_dtype, self.column_name, self.dataset_id,
                )
                return CommandResult.FAILURE
                
            # Apply the converted data
            self.dataset.data[self.column_name] = conversion_result["converted_data"]
            
            # Show conversion report if there were issues
            if conversion_result["errors_count"] > 0:
                self.ui_controller.show_warning_message(
                    "Column Type Changed", 
                    f"Column '{self.column_name}' type changed from {self.original_dtype} to {self.target_dtype}.\n"
                    f"{conversion_result['errors_count']} values could not be converted and were set to NaN/None."
                )
            else:
                self.ui_controller.show_info_message(
                    "Column Type Changed", 
                    f"Column '{self.column_name}' type successfully changed from {self.original_dtype} to {self.target_dtype}."
                )

            # Store conversion report for undo
            self.conversion_report = conversion_result

            # Emit event for data change
            self.app_context.event_bus.emit(
                DatasetEvents.DATASET_DATA_CHANGED, 
                DatasetDataChangedData(
                    dataset_id=self.dataset_id, 
                    start_index=(0, self.column_index), 
                    end_index=(len(self.dataset.data) - 1, self.column_index)
                ).to_dict()
            )

            return CommandResult.SUCCESS
            
        except Exception as e:
            error_msg = f"Failed to change column type for column {self.column_index}: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Change Column Type Error", error_msg)
            return CommandResult.FAILURE

    def _convert_column_dtype(self) -> Union[Dict[str, Any], None]:
        """
        Convert column data to target dtype with error handling.
        Returns dict with converted_data and conversion stats, or None if failed.
        """
        try:
            if self.dataset is None or self.dataset.data is None or self.column_name is None:
                return None
                
            original_series = self.dataset.data[self.column_name]
            errors_count = 0
            converted_data = None
            
            if self.target_dtype == "int64":
                # Convert to integer
                converted_data = pd.to_numeric(original_series, errors="coerce").astype("Int64")
                errors_count = converted_data.isna().sum() - original_series.isna().sum()
                
            elif self.target_dtype == "float64":
                # Convert to float. pd.to_numeric alone is not enough: it picks
                # the tightest numeric dtype for the values, so a column of
                # whole numbers (e.g. 1, 2, 3) would stay int64 instead of
                # becoming float64.
                converted_data = pd.to_numeric(original_series, errors="coerce").astype("float64")
                errors_count = converted_data.isna().sum() - original_series.isna().sum()
                
            elif self.target_dtype == "object" or self.target_dtype == "string":
                # Convert to string - should always work
                converted_data = original_series.astype("string")
                errors_count = 0
                
            elif self.target_dtype == "bool":
                # Convert to boolean
                # Try to interpret common boolean representations
                def convert_to_bool(value):
                    if pd.isna(value):
                        return np.nan
                    if isinstance(value, bool):
                        return value
                    if isinstance(value, (int, float)):
                        return bool(value)
                    if isinstance(value, str):
                        lower_val = value.lower().strip()
                        if lower_val in ["true", "1", "yes", "y", "t"]:
                            return True
                        elif lower_val in ["false", "0", "no", "n", "f"]:
                            return False
                    return np.nan
                
                converted_data = original_series.apply(convert_to_bool)
                errors_count = converted_data.isna().sum() - original_series.isna().sum()
                
            elif self.target_dtype == "datetime64[ns]":
                # Convert to datetime
                converted_data = pd.to_datetime(original_series, errors="coerce")
                errors_count = converted_data.isna().sum() - original_series.isna().sum()
                
            else:
                self.ui_controller.show_error_message(
                    "Change Column Type", 
                    f"Unsupported target data type: {self.target_dtype}"
                )
                return None
            
            return {
                "converted_data": converted_data,
                "errors_count": errors_count,
                "original_dtype": self.original_dtype,
                "target_dtype": self.target_dtype
            }
            
        except Exception as e:
            self.logger.error(f"Error converting column data: {e}", exc_info=True)
            return None

    def undo(self) -> CommandResult:
        """Restore the original column data and dtype."""
        if (self.original_data is not None and self.dataset and
            self.dataset.data is not None and self.column_name):

            self.dataset.data[self.column_name] = self.original_data

            # Emit event for data change
            self.app_context.event_bus.emit(
                DatasetEvents.DATASET_DATA_CHANGED,
                DatasetDataChangedData(
                    dataset_id=self.dataset_id,
                    start_index=(0, self.column_index),
                    end_index=(len(self.dataset.data) - 1, self.column_index)
                ).to_dict()
            )
            return CommandResult.SUCCESS

        self.logger.warning(
            "ChangeColumnDtypeCommand.undo: cannot undo for dataset '%s' (original_data set=%s, dataset found=%s, column_name set=%s)",
            self.dataset_id, self.original_data is not None, self.dataset is not None, bool(self.column_name),
        )
        return CommandResult.FAILURE

    def redo(self) -> CommandResult:
        """Reapply the column dtype change."""
        if (self.conversion_report and self.dataset and
            self.dataset.data is not None and self.column_name):

            # Re-execute the conversion
            conversion_result = self._convert_column_dtype()
            if conversion_result:
                self.dataset.data[self.column_name] = conversion_result["converted_data"]

                # Emit event for data change
                self.app_context.event_bus.emit(
                    DatasetEvents.DATASET_DATA_CHANGED,
                    DatasetDataChangedData(
                        dataset_id=self.dataset_id,
                        start_index=(0, self.column_index),
                        end_index=(len(self.dataset.data) - 1, self.column_index)
                    ).to_dict()
                )
                return CommandResult.SUCCESS
            self.logger.warning(
                "ChangeColumnDtypeCommand.redo: re-conversion to '%s' failed for column '%s' in dataset '%s'",
                self.target_dtype, self.column_name, self.dataset_id,
            )
            return CommandResult.FAILURE

        self.logger.warning(
            "ChangeColumnDtypeCommand.redo: cannot redo for dataset '%s' (conversion_report set=%s, dataset found=%s, column_name set=%s)",
            self.dataset_id, bool(self.conversion_report), self.dataset is not None, bool(self.column_name),
        )
        return CommandResult.FAILURE

    @override
    def cleanup(self) -> None:
        """Release the original-data snapshot held for undo once this
        command is dropped from the stacks for good (see Command.cleanup)."""
        self.original_data = None