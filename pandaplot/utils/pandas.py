"""Pandaplot pandas utilities."""
import pandas as pd
import numpy as np
from typing import Any

def convert_value(value: Any, target_dtype: Any) -> Any:
    """
    Convert a value to the target data type.
    
    Args:
        value: The value to convert
        target_dtype: The target pandas dtype
        
    Returns:
        The converted value or None if conversion failed
    """
    # Handle empty strings
    if isinstance(value, str) and value.strip() == "":
        if pd.api.types.is_numeric_dtype(target_dtype):
            return np.nan
        else:
            return ""
    
    try:
        if pd.api.types.is_integer_dtype(target_dtype):
            if isinstance(value, str):
                # Handle potential decimal in string
                return int(float(value))
            return int(value)
        
        elif pd.api.types.is_float_dtype(target_dtype):
            return float(value)
        
        elif pd.api.types.is_bool_dtype(target_dtype):
            if isinstance(value, str):
                return value.lower() in ['true', '1', 'yes', 'y', 'on']
            return bool(value)
        
        elif pd.api.types.is_datetime64_any_dtype(target_dtype):
            return pd.to_datetime(value)
        
        else:
            # For object/string types, just convert to string
            return str(value)
            
    except (ValueError, TypeError, OverflowError):
        return None