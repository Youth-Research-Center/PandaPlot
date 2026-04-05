"""
Analysis command for applying mathematical analysis operations with undo/redo support.
"""

from typing import Any, Dict, override

import pandas as pd

from pandaplot.analysis import AnalysisEngine, AnalysisType
from pandaplot.commands.base_command import Command
from pandaplot.models.project.items import Dataset
from pandaplot.models.state.app_context import AppContext


class AnalysisCommand(Command):
    """
    Command to apply mathematical analysis to dataset columns.
    """

    def __init__(self, app_context: AppContext, dataset_id: str, analysis_config: Dict[str, Any]):
        """
        Initialize analysis command.

        Args:
            app_context: Application context
            dataset_id: ID of the dataset to analyze
            analysis_config: Configuration dictionary with:
                - analysis_type: str - type of analysis ('derivative', 'integral', etc.)
                - x_column: str - X-axis column name
                - y_column: str - Y-axis column name
                - new_column_name: str - name for the result column
                - replace_existing: bool - whether to replace existing column
                - parameters: dict - analysis-specific parameters
        """
        super().__init__()
        self.app_context = app_context
        self.dataset_id = dataset_id
        self.analysis_config = analysis_config

        # State for undo/redo
        self.original_data = None
        self.column_existed_before = False
        self.dataset = None

        # Extract config
        self.analysis_type = AnalysisType(analysis_config["analysis_type"])
        self.x_column = analysis_config["x_column"]
        self.y_column = analysis_config["y_column"]
        self.new_column_name = analysis_config["new_column_name"]
        self.replace_existing = analysis_config.get("replace_existing", False)
        self.parameters = analysis_config.get("parameters", {})

    @override
    def execute(self) -> bool:
        """Execute the analysis and add result column to dataset."""
        try:
            self.logger.info("Executing AnalysisCommand")
            # Get dataset
            self.dataset = self._get_dataset()
            if not self.dataset:
                self.logger.warning(
                    f"Analysis execution failed: Dataset {self.dataset_id} not found")
                return False

            # Validate inputs
            if not self._validate_inputs():
                return False

            # Store original state for undo
            df = self.dataset.data
            if df is None:
                self.logger.warning(
                    "Analysis execution failed: Dataset is empty")
                return False
            self._store_original_state(df)

            # Execute analysis
            result = self._execute_analysis(df)
            if result is None:
                self.logger.warning(
                    "Analysis execution failed: Analysis returned no result")
                return False

            # Add result column to dataset
            df_copy = df.copy()

            # Handle result data alignment
            result_data_length = len(result.result_data)
            df_length = len(df)
            self.logger.info(
                f"Comparing lengths: result_data={result_data_length}, df={df_length}")

            if result_data_length == df_length:
                # Direct assignment if lengths match
                df_copy[self.new_column_name] = result.result_data
                self.logger.info(
                    f"Direct assignment: new column '{self.new_column_name}' added, shape now: {df_copy.shape}")
            else:
                # Handle cases where result data is shorter (e.g., derivatives, arc length)
                df_copy[self.new_column_name] = pd.NA
                df_copy.iloc[:len(result.result_data), df_copy.columns.get_loc(
                    self.new_column_name)] = result.result_data
                self.logger.info(
                    f"Partial assignment: new column '{self.new_column_name}' added, shape now: {df_copy.shape}")

            # Update dataset
            self.dataset.set_data(df_copy)
            return True

        except Exception as e:
            self.logger.error(f"Analysis execution failed: {e}")
            return False

    def undo(self) -> bool:
        """Remove the analysis result column or restore original data."""
        try:
            if not self.dataset or not isinstance(self.dataset, Dataset):
                self.logger.warning("Undo failed: Invalid dataset reference")
                return False

            df = self.dataset.data
            if df is None:
                self.logger.warning("Undo failed: No data in dataset")
                return False

            if self.column_existed_before and self.original_data is not None:
                # Restore original column data
                df_copy = df.copy()
                df_copy[self.new_column_name] = self.original_data
                self.dataset.set_data(df_copy)
            elif not self.column_existed_before and self.new_column_name in df.columns:
                # Remove the column we added
                df_copy = df.copy()
                df_copy = df_copy.drop(columns=[self.new_column_name])
                self.dataset.set_data(df_copy)

            self.logger.info(
                f"Analysis undone successfully: {self.new_column_name}")
            return True

        except Exception as e:
            self.logger.error(f"Analysis undo failed: {e}")
            return False

    def redo(self) -> bool:
        """Re-execute the analysis."""
        return self.execute()

    def _get_dataset(self) -> Dataset | None:
        """Get dataset from app context."""
        try:
            app_state = self.app_context.get_app_state()
            if app_state.has_project and app_state.current_project:
                project = app_state.current_project
                dataset_item = project.find_item(self.dataset_id)
                if dataset_item and hasattr(dataset_item, "data") and isinstance(dataset_item, Dataset):
                    return dataset_item  # Return the dataset object, not the data
            return None
        except Exception as e:
            self.logger.error(f"Error getting dataset: {e}")
            return None

    def _validate_inputs(self) -> bool:
        """Validate all required inputs are present and valid."""
        if not self.new_column_name.strip():
            self.logger.error("Error: New column name cannot be empty")
            return False

        if self.dataset is None or not hasattr(self.dataset, "data") or self.dataset.data is None:
            self.logger.error("Error: Dataset has no data")
            return False

        df = self.dataset.data

        # Check if source columns exist
        missing_columns = []
        if self.x_column not in df.columns:
            missing_columns.append(self.x_column)
        if self.y_column not in df.columns:
            missing_columns.append(self.y_column)

        if missing_columns:
            self.logger.error(
                f"Error: Source columns not found: {missing_columns}")
            return False

        # Check if new column already exists
        if self.new_column_name in df.columns and not self.replace_existing:
            self.logger.error(
                f"Error: Column '{self.new_column_name}' already exists")
            return False

        # Check data types for numeric operations
        if not pd.api.types.is_numeric_dtype(df[self.x_column]):
            self.logger.error(
                f"Error: X column '{self.x_column}' must be numeric")
            return False

        if not pd.api.types.is_numeric_dtype(df[self.y_column]):
            self.logger.error(
                f"Error: Y column '{self.y_column}' must be numeric")
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

    def _execute_analysis(self, df: pd.DataFrame):
        """Execute the specific analysis operation."""
        x_data = df[self.x_column]
        y_data = df[self.y_column]

        # Extract parameters
        start_index = self.parameters.get("start_index", 0)
        end_index = self.parameters.get("end_index", -1)
        method = self.parameters.get("method", "central")

        # Route to appropriate analysis method
        if self.analysis_type == AnalysisType.DERIVATIVE:
            return AnalysisEngine.calculate_derivative(
                x_data, y_data, method, start_index, end_index
            )
        elif self.analysis_type == AnalysisType.INTEGRAL:
            return AnalysisEngine.calculate_integral(
                x_data, y_data, start_index, end_index
            )
        elif self.analysis_type == AnalysisType.ARC_LENGTH:
            return AnalysisEngine.calculate_arc_length(
                x_data, y_data, start_index, end_index
            )
        elif self.analysis_type == AnalysisType.SMOOTHING:
            additional_params = {k: v for k, v in self.parameters.items()
                                 if k not in ["start_index", "end_index", "method"]}
            return AnalysisEngine.smooth_data(
                x_data, y_data, method, start_index, end_index, **additional_params
            )
        elif self.analysis_type == AnalysisType.INTERPOLATION:
            num_points = self.parameters.get("num_points", None)
            return AnalysisEngine.interpolate_data(
                x_data, y_data, method, num_points, start_index, end_index
            )
        else:
            self.logger.error(f"Unknown analysis type: {self.analysis_type}")
            return None
