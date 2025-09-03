"""
Transform controller for handling data transformation business logic.

Extracted from transform_tab.py to provide safe execution environment
and transformation logic for the transform panel.
"""

import logging
import pandas as pd
import numpy as np
import re
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QObject, Signal

from pandaplot.models.state.app_context import AppContext
from pandaplot.models.project.items.dataset import Dataset


class TransformController(QObject):
    """
    Business logic for data transformations, extracted from transform_tab.py.
    Handles safe execution environment and transformation logic.
    """
    # QObject inheritance is required for Qt signals to function properly. 
    
    # Signals
    transform_completed = Signal(str, str, object)  # dataset_id, column_name, result_data
    transform_failed = Signal(str, str)  # dataset_id, error_message
    preview_ready = Signal(str, object)  # dataset_id, preview_data

    def __init__(self, app_context: AppContext, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.app_context = app_context
        self.logger = logging.getLogger(__name__)
        
        # Safe execution environment
        self.safe_globals = {
            'pd': pd,
            'np': np,
            'abs': abs,
            'min': min,
            'max': max,
            'sum': sum,
            'len': len,
            'round': round,
            'int': int,
            'float': float,
            'str': str,
            'bool': bool,
            'list': list,
            'dict': dict,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
        }
        
        # Add pandas and numpy functions commonly used in transformations
        self._add_pandas_functions()
        self._add_numpy_functions()
    
    def _add_pandas_functions(self):
        """Add commonly used pandas functions to safe globals."""
        pandas_functions = [
            'to_datetime', 'to_numeric', 'isna', 'notna', 'cut', 'qcut',
            'concat', 'merge', 'pivot_table', 'crosstab'
        ]
        
        for func_name in pandas_functions:
            if hasattr(pd, func_name):
                self.safe_globals[func_name] = getattr(pd, func_name)
    
    def _add_numpy_functions(self):
        """Add commonly used numpy functions to safe globals."""
        numpy_functions = [
            'sqrt', 'log', 'log10', 'exp', 'sin', 'cos', 'tan',
            'mean', 'median', 'std', 'var', 'percentile', 'quantile',
            'floor', 'ceil', 'round', 'absolute', 'sign'
        ]
        
        for func_name in numpy_functions:
            if hasattr(np, func_name):
                self.safe_globals[func_name] = getattr(np, func_name)
    
    def validate_function_code(self, function_code: str) -> tuple[bool, str]:
        """
        Validate the function code for safety and syntax.
        
        Args:
            function_code: The transformation function code
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not function_code.strip():
            return False, "Function code cannot be empty"
        
        # Check for dangerous operations
        dangerous_patterns = [
            r'\bimport\b', r'\bexec\b', r'\beval\b', r'\b__.*__\b',
            r'\bopen\b', r'\bfile\b', r'\bwith\b.*open',
            r'\bos\.\b', r'\bsys\.\b', r'\bsubprocess\b',
            r'\bglobals\b', r'\blocals\b', r'\bvars\b',
            r'\bdir\b', r'\bgetattr\b', r'\bsetattr\b', r'\bdelattr\b'
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, function_code, re.IGNORECASE):
                return False, f"Potentially unsafe operation detected: {pattern}"
        
        # Try to compile the code
        try:
            compile(function_code, '<transform>', 'eval')
        except SyntaxError as e:
            return False, f"Syntax error: {e}"
        except Exception as e:
            return False, f"Code validation error: {e}"
        
        return True, ""
    
    def create_preview(self, dataset_id: str, source_column: str, 
                      function_code: str, preview_rows: int = 5) -> Optional[Dict[str, Any]]:
        """
        Create a preview of the transformation without modifying the dataset.
        
        Args:
            dataset_id: ID of the dataset
            source_column: Name of the source column
            function_code: Transformation function code
            preview_rows: Number of rows to preview
            
        Returns:
            Dictionary with preview data or None if failed
        """
        try:
            # Get dataset
            dataset = self._get_dataset(dataset_id)
            if not dataset or not isinstance(dataset, Dataset):
                return None
            
            if not hasattr(dataset, 'data') or dataset.data is None:
                return None
            
            df = dataset.data
            if source_column not in df.columns:
                return None
            
            # Validate function code
            is_valid, error_msg = self.validate_function_code(function_code)
            if not is_valid:
                return {'error': error_msg}
            
            # Get preview data
            preview_data = df[source_column].head(preview_rows)
            
            # Apply transformation to preview data
            local_vars = {'x': preview_data}
            result = eval(function_code, self.safe_globals, local_vars)
            
            # Create preview result
            preview_result = {
                'source_values': preview_data.tolist(),
                'transformed_values': result.tolist() if hasattr(result, 'tolist') else [result] * len(preview_data),
                'source_column': source_column,
                'function_code': function_code,
                'preview_rows': preview_rows
            }
            
            self.preview_ready.emit(dataset_id, preview_result)
            return preview_result
            
        except Exception as e:
            error_msg = f"Preview generation failed: {str(e)}"
            return {'error': error_msg}
    
    def apply_transformation(self, dataset_id: str, source_column: str, 
                           new_column_name: str, function_code: str, 
                           replace_existing: bool = False) -> bool:
        """
        Apply the transformation to the dataset.
        
        Args:
            dataset_id: ID of the dataset
            source_column: Name of the source column
            new_column_name: Name for the new column
            function_code: Transformation function code
            replace_existing: Whether to replace existing column
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get dataset
            dataset = self._get_dataset(dataset_id)
            if not dataset or not isinstance(dataset, Dataset):
                self.transform_failed.emit(dataset_id, "Dataset not found")
                return False
            
            if not hasattr(dataset, 'data') or dataset.data is None:
                self.transform_failed.emit(dataset_id, "Dataset has no data")
                return False
            
            df = dataset.data
            if source_column not in df.columns:
                self.transform_failed.emit(dataset_id, f"Column '{source_column}' not found")
                return False
            
            # Validate function code
            is_valid, error_msg = self.validate_function_code(function_code)
            if not is_valid:
                self.transform_failed.emit(dataset_id, error_msg)
                return False
            
            # Check if new column already exists and handle accordingly
            if new_column_name in df.columns and not replace_existing:
                self.transform_failed.emit(dataset_id, 
                    f"Column '{new_column_name}' already exists. Choose a different name or enable replace option.")
                return False
            
            # Apply transformation through command system
            from pandaplot.commands.project.dataset.transform_column_command import TransformColumnCommand
            
            # Create transform configuration
            transform_config = {
                'new_column_name': new_column_name,
                'transform_type': 'column',  # Default to column operation for now
                'source_columns': [source_column],
                'expression': function_code,
                'replace_existing': replace_existing
            }
            
            # Create and execute command
            command = TransformColumnCommand(self.app_context, dataset_id, transform_config)
            
            # TODO: Execute through app context command executor when available
            # For now, execute directly
            if command.execute():
                self.transform_completed.emit(dataset_id, new_column_name, None)
                return True
            else:
                self.transform_failed.emit(dataset_id, "Failed to execute transformation command")
                return False
                
        except Exception as e:
            error_msg = f"Transformation failed: {str(e)}"
            self.transform_failed.emit(dataset_id, error_msg)
            return False
    
    def get_suggested_column_name(self, source_column: str, function_code: str) -> str:
        """
        Generate a suggested name for the new column based on the transformation.
        
        Args:
            source_column: Name of the source column
            function_code: Transformation function code
            
        Returns:
            Suggested column name
        """
        # Simple heuristics for common transformations
        code_lower = function_code.lower()
        
        if 'upper' in code_lower:
            return f"{source_column}_upper"
        elif 'lower' in code_lower:
            return f"{source_column}_lower"
        elif 'strip' in code_lower:
            return f"{source_column}_stripped"
        elif '*' in function_code and '2' in function_code:
            return f"{source_column}_doubled"
        elif '**' in function_code and '2' in function_code:
            return f"{source_column}_squared"
        elif 'sqrt' in code_lower:
            return f"{source_column}_sqrt"
        elif 'log' in code_lower:
            return f"{source_column}_log"
        elif 'datetime' in code_lower:
            return f"{source_column}_datetime"
        elif 'mean' in code_lower or 'std' in code_lower:
            return f"{source_column}_normalized"
        else:
            return f"{source_column}_transformed"
    
    def get_transformation_templates(self) -> Dict[str, List[Dict[str, str]]]:
        """
        Get predefined transformation templates by category.
        
        Returns:
            Dictionary of transformation templates
        """
        return {
            "Math Operations": [
                {"name": "Multiply by 2", "code": "x * 2", "description": "Double the values"},
                {"name": "Square", "code": "x ** 2", "description": "Square the values"},
                {"name": "Square Root", "code": "np.sqrt(x)", "description": "Square root of values"},
                {"name": "Logarithm", "code": "np.log(x)", "description": "Natural logarithm"},
                {"name": "Normalize (Z-score)", "code": "(x - x.mean()) / x.std()", "description": "Standardize to mean=0, std=1"},
            ],
            "String Operations": [
                {"name": "Uppercase", "code": "x.str.upper()", "description": "Convert to uppercase"},
                {"name": "Lowercase", "code": "x.str.lower()", "description": "Convert to lowercase"},
                {"name": "Strip whitespace", "code": "x.str.strip()", "description": "Remove leading/trailing whitespace"},
                {"name": "Extract numbers", "code": "x.str.extract(r'(\\d+)').astype(float)", "description": "Extract numeric values"},
                {"name": "String length", "code": "x.str.len()", "description": "Length of each string"},
            ],
            "Date/Time Operations": [
                {"name": "Parse datetime", "code": "pd.to_datetime(x)", "description": "Convert to datetime"},
                {"name": "Extract year", "code": "pd.to_datetime(x).dt.year", "description": "Extract year component"},
                {"name": "Extract month", "code": "pd.to_datetime(x).dt.month", "description": "Extract month component"},
                {"name": "Day of week", "code": "pd.to_datetime(x).dt.dayofweek", "description": "Day of week (0=Monday)"},
                {"name": "Format date", "code": "pd.to_datetime(x).dt.strftime('%Y-%m-%d')", "description": "Format as YYYY-MM-DD"},
            ],
            "Statistical Operations": [
                {"name": "Rank", "code": "x.rank()", "description": "Rank values (1 = smallest)"},
                {"name": "Percentile rank", "code": "x.rank(pct=True)", "description": "Percentile rank (0-1)"},
                {"name": "Rolling mean", "code": "x.rolling(3).mean()", "description": "3-period rolling average"},
                {"name": "Cumulative sum", "code": "x.cumsum()", "description": "Cumulative sum"},
                {"name": "Lag/Shift", "code": "x.shift(1)", "description": "Shift values by 1 period"},
            ]
        }
    
    def _get_dataset(self, dataset_id: str):
        """Get dataset from app context."""
        try:
            # Use the app state to get the current project and find the dataset
            if self.app_context and hasattr(self.app_context, 'app_state'):
                app_state = self.app_context.app_state
                if app_state.current_project:
                    return app_state.current_project.find_item(dataset_id)
            return None
        except Exception as e:
            self.logger.error(f"Error getting dataset {dataset_id}: {e}")
            return None
    