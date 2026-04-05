"""
Transform column command for applying data transformations with undo/redo support.
"""

from typing import Any, Dict, Optional, override

import pandas as pd

from pandaplot.commands.base_command import Command
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext


class TransformColumnCommand(Command):
    """
    Command to apply data transformation to a dataset column.
    Integrates with existing command system for undo/redo support.
    """

    def __init__(self, app_context: AppContext, dataset_id: str, transform_config: Dict[str, Any]):
        """
        Initialize transform command.

        Args:
            app_context: Application context
            dataset_id: ID of the dataset to transform
            transform_config: Configuration dictionary with:
                - new_column_name: str - name for the new/modified column
                - transform_type: str - 'column', 'row', 'multi_column'
                - source_columns: list - source column names
                - expression: str - transformation expression
                - replace_existing: bool - whether to replace existing column
        """
        super().__init__()
        self.app_context = app_context
        self.dataset_id = dataset_id
        self.transform_config = transform_config

        # State for undo/redo
        self.original_data = None
        self.column_existed_before = False
        self.dataset = None

        # Extract config
        self.new_column_name = transform_config["new_column_name"]
        self.transform_type = transform_config["transform_type"]
        self.source_columns = transform_config["source_columns"]
        self.expression = transform_config["expression"]
        self.replace_existing = transform_config.get("replace_existing", False)

    @override
    def execute(self) -> bool:
        """Execute the transformation and add new column to dataset."""
        try:
            self.logger.info("Executing TransformColumnCommand")
            # Get dataset from app context
            self.dataset = self._get_dataset()
            if not self.dataset:
                self.logger.warning(f"Dataset {self.dataset_id} not found")
                return False

            # Ensure we have a Dataset object
            if not isinstance(self.dataset, Dataset):
                self.logger.warning(
                    f"Retrieved item is not a Dataset: {type(self.dataset)}")
                return False

            # Validate inputs
            if not self._validate_inputs():
                return False

            # Get current dataframe
            if not hasattr(self.dataset, "data") or self.dataset.data is None:
                self.logger.warning("Dataset has no data")
                return False

            df = self.dataset.data.copy()  # Work with a copy

            # Store original state for undo
            self._store_original_state(df)

            # Execute transformation
            result_series = self._execute_transform_logic(df)
            if result_series is None:
                return False

            # Apply result to dataframe
            df[self.new_column_name] = result_series

            # Update dataset using proper method
            self.dataset.set_data(df)

            self.logger.info(
                f"Transform applied: '{self.new_column_name}' created from {self.source_columns}")
            return True

        except Exception as e:
            self.logger.error(f"Transform execution failed: {e}")
            return False

    @override
    def undo(self) -> bool:
        """Remove the added column from dataset or restore original data."""
        try:
            if not self.dataset or not isinstance(self.dataset, Dataset):
                return False

            if not hasattr(self.dataset, "data") or self.dataset.data is None:
                return False

            df = self.dataset.data.copy()

            if self.column_existed_before and self.original_data is not None:
                # Restore original column data
                df[self.new_column_name] = self.original_data
            elif self.new_column_name in df.columns:
                # Remove the new column
                df = df.drop(columns=[self.new_column_name])

            # Update dataset
            self.dataset.set_data(df)

            self.logger.info(f"Transform undone: '{self.new_column_name}' reverted")
            return True

        except Exception as e:
            self.logger.error(f"Transform undo failed: {e}")
            return False

    @override
    def redo(self) -> bool:
        """Re-execute the transformation."""
        return self.execute()

    def _get_dataset(self):
        """Get dataset from app context."""
        try:
            if self.app_context and hasattr(self.app_context, "app_state"):
                current_project = self.app_context.app_state.current_project
                if current_project:
                    return current_project.find_item(self.dataset_id)
            return None
        except Exception as e:
            self.logger.error(f"Error getting dataset: {e}")
            return None

    def _validate_inputs(self) -> bool:
        """Validate all required inputs are present and valid."""
        if not self.new_column_name.strip():
            self.logger.error("New column name cannot be empty")
            return False

        if not self.expression.strip():
            self.logger.error("Transform expression cannot be empty")
            return False

        if not self.source_columns:
            self.logger.error("At least one source column must be selected")
            return False

        # Check if dataset is available
        if not self.dataset or not isinstance(self.dataset, Dataset):
            self.logger.error("Dataset not available for validation")
            return False

        # Get dataframe for validation
        try:
            if not hasattr(self.dataset, "data") or self.dataset.data is None:
                self.logger.error("Dataset has no data")
                return False
            df = self.dataset.data
        except Exception as e:
            self.logger.error(f"Cannot access dataset dataframe: {e}")
            return False

        # Check if source columns exist
        missing_columns = [
            col for col in self.source_columns if col not in df.columns]
        if missing_columns:
            self.logger.error(f"Source columns not found: {missing_columns}")
            return False

        # Check if target column exists and handle accordingly
        if self.new_column_name in df.columns and not self.replace_existing:
            self.logger.error(f"Column '{self.new_column_name}' already exists. Enable replace option or choose different name.")
            return False

        return True

    def _store_original_state(self, df: pd.DataFrame):
        """Store original state for undo operations."""
        if self.new_column_name in df.columns:
            self.column_existed_before = True
            self.original_data = df[self.new_column_name].copy()
        else:
            self.column_existed_before = False
            self.original_data = None

    def _execute_transform_logic(self, df: pd.DataFrame) -> Optional[pd.Series]:
        """Execute transformation using safe evaluation."""
        try:
            # Create safe execution environment
            safe_globals = self._create_safe_execution_environment()

            if self.transform_type == "column":
                return self._execute_column_operation(df, safe_globals)
            elif self.transform_type == "row":
                return self._execute_row_operation(df, safe_globals)
            elif self.transform_type == "multi_column":
                return self._execute_multi_column_operation(df, safe_globals)
            else:
                self.logger.error(f"Unknown transform type: {self.transform_type}")
                return None

        except Exception as e:
            self.logger.error(f"Transform logic execution failed: {e}")
            return None

    def _execute_column_operation(self, df: pd.DataFrame, safe_globals: dict) -> pd.Series:
        """Execute column-based transformation (operates on single column)."""
        source_column = self.source_columns[0]  # Column operations use first source column
        source_data = df[source_column]

        # Create local variables for evaluation
        local_vars = {
            "value": source_data,
            "x": source_data,  # Alternative name
            "column": source_data,
            "data": source_data
        }

        # Execute expression
        result = eval(self.expression, safe_globals, local_vars)

        # Ensure result is a pandas Series
        if not isinstance(result, pd.Series):
            # If result is scalar, broadcast to series
            if pd.api.types.is_scalar(result):
                result = pd.Series(
                    [result] * len(source_data), index=source_data.index)
            else:
                # Convert array-like to series
                result = pd.Series(result, index=source_data.index)

        return result

    def _execute_row_operation(self, df: pd.DataFrame, safe_globals: dict) -> pd.Series:
        """Execute row-based transformation (operates on entire rows)."""
        # For row operations, we apply the function to each row
        def row_transform(row):
            local_vars = {
                "row": row,
                "r": row  # Alternative name
            }
            return eval(self.expression, safe_globals, local_vars)

        result = df.apply(row_transform, axis=1)
        return result

    def _execute_multi_column_operation(self, df: pd.DataFrame, safe_globals: dict) -> pd.Series:
        """Execute multi-column transformation (operates on selected columns)."""
        # Get selected columns as dataframe
        selected_columns = df[self.source_columns]

        # Create local variables
        local_vars = {
            "cols": selected_columns,
            "columns": selected_columns,
            "data": selected_columns
        }

        # Execute expression
        result = eval(self.expression, safe_globals, local_vars)

        # Ensure result is a pandas Series
        if not isinstance(result, pd.Series):
            if pd.api.types.is_scalar(result):
                result = pd.Series([result] * len(df), index=df.index)
            else:
                result = pd.Series(result, index=df.index)

        return result

    def _create_safe_execution_environment(self) -> dict:
        """Create safe globals for eval() execution."""
        # Import required modules
        import math

        import numpy as np
        import pandas as pd

        # Create safe environment with commonly used functions
        safe_globals = {
            # Pandas and numpy
            "pd": pd,
            "np": np,
            "math": math,

            # Built-in functions (safe subset)
            "abs": abs,
            "min": min,
            "max": max,
            "sum": sum,
            "len": len,
            "round": round,
            "int": int,
            "float": float,
            "str": str,
            "bool": bool,
            "list": list,
            "dict": dict,
            "range": range,
            "enumerate": enumerate,
            "zip": zip,

            # Math functions
            "sqrt": math.sqrt,
            "log": math.log,
            "log10": math.log10,
            "exp": math.exp,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "floor": math.floor,
            "ceil": math.ceil,

            # Pandas functions
            "to_datetime": pd.to_datetime,
            "to_numeric": pd.to_numeric,
            "isna": pd.isna,
            "notna": pd.notna,
            "cut": pd.cut,
            "qcut": pd.qcut,

            # Numpy functions
            "mean": np.mean,
            "median": np.median,
            "std": np.std,
            "var": np.var,
            "percentile": np.percentile,
        }

        return safe_globals
