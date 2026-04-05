"""
Analysis types and data structures for mathematical analysis operations.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd


class AnalysisType(Enum):
    """Supported analysis types."""
    DERIVATIVE = "derivative"
    INTEGRAL = "integral"
    ARC_LENGTH = "arc_length"
    SMOOTHING = "smoothing"
    INTERPOLATION = "interpolation"

class DerivativeMethod(Enum):
    """Methods for derivative calculation."""
    FORWARD = "forward"
    BACKWARD = "backward"
    CENTRAL = "central"

class SmoothingMethod(Enum):
    """Methods for data smoothing."""
    SAVGOL = "savgol"
    LOWESS = "lowess"
    ROLLING_MEAN = "rolling_mean"

class InterpolationMethod(Enum):
    """Methods for data interpolation."""
    LINEAR = "linear"
    CUBIC = "cubic"
    QUADRATIC = "quadratic"
    NEAREST = "nearest"

@dataclass
class AnalysisParameters:
    """Parameters for analysis operations."""
    method: str = "central"
    start_index: int = 0
    end_index: int = -1
    window_length: Optional[int] = None
    polynomial_order: Optional[int] = None
    num_points: Optional[int] = None
    additional_params: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AnalysisResult:
    """Result of an analysis operation."""
    analysis_type: AnalysisType
    source_columns: List[str]
    x_data: pd.Series
    y_data: pd.Series
    result_data: Union[pd.Series, np.ndarray]
    parameters: AnalysisParameters
    metadata: Dict[str, Any] = field(default_factory=dict)
    statistics: Dict[str, float] = field(default_factory=dict)
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert result to DataFrame for easy integration."""
        if isinstance(self.result_data, pd.Series):
            return pd.DataFrame({
                "x": self.x_data,
                "result": self.result_data
            })
        else:
            return pd.DataFrame({
                "x": self.x_data,
                "result": self.result_data
            })
    
    def get_column_name(self) -> str:
        """Generate appropriate column name for the result."""
        source_col = self.source_columns[0] if self.source_columns else "data"
        return f"{source_col}_{self.analysis_type.value}"
