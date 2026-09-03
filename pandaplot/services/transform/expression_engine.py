"""Shared safe-expression engine for transform-style features.

Used by the dataset Transform panel (TransformController) and the chart
Transform panel (TransformChartSeriesCommand, #268) so both validate and
evaluate expressions through one implementation instead of two.
"""

import re
from typing import Any, Dict, List

import numpy as np
import pandas as pd

_DANGEROUS_PATTERNS = [
    r"\bimport\b", r"\bexec\b", r"\beval\b", r"\b__.*__\b",
    r"\bopen\b", r"\bfile\b", r"\bwith\b.*open",
    r"\bos\.\b", r"\bsys\.\b", r"\bsubprocess\b",
    r"\bglobals\b", r"\blocals\b", r"\bvars\b",
    r"\bdir\b", r"\bgetattr\b", r"\bsetattr\b", r"\bdelattr\b",
]

_PANDAS_FUNCTIONS = [
    "to_datetime", "to_numeric", "isna", "notna", "cut", "qcut",
    "concat", "merge", "pivot_table", "crosstab",
]

_NUMPY_FUNCTIONS = [
    "sqrt", "log", "log10", "exp", "sin", "cos", "tan",
    "mean", "median", "std", "var", "percentile", "quantile",
    "floor", "ceil", "round", "absolute", "sign",
]


def build_safe_globals() -> Dict[str, Any]:
    """Build the globals dict used to eval() a transform expression."""
    safe_globals: Dict[str, Any] = {
        "pd": pd,
        "np": np,
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
    }
    for func_name in _PANDAS_FUNCTIONS:
        if hasattr(pd, func_name):
            safe_globals[func_name] = getattr(pd, func_name)
    for func_name in _NUMPY_FUNCTIONS:
        if hasattr(np, func_name):
            safe_globals[func_name] = getattr(np, func_name)
    return safe_globals


def validate_expression(expression: str) -> tuple[bool, str]:
    """Validate a transform expression for safety and syntax.

    Returns (is_valid, error_message); error_message is "" when valid.
    """
    if not expression.strip():
        return False, "Function code cannot be empty"

    for pattern in _DANGEROUS_PATTERNS:
        if re.search(pattern, expression, re.IGNORECASE):
            return False, f"Potentially unsafe operation detected: {pattern}"

    try:
        compile(expression, "<transform>", "eval")
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    except Exception as e:
        return False, f"Code validation error: {e}"

    return True, ""


def evaluate_expression(
    expression: str, local_vars: Dict[str, Any], safe_globals: Dict[str, Any] | None = None,
) -> Any:
    """Evaluate a transform expression against local_vars.

    Callers are expected to call validate_expression() first and to catch
    whatever exception this raises (e.g. NameError, TypeError) themselves.
    """
    if safe_globals is None:
        safe_globals = build_safe_globals()
    return eval(expression, safe_globals, local_vars)  # noqa: S307 - validated by validate_expression at every call site


def get_transformation_templates() -> Dict[str, List[Dict[str, str]]]:
    """Predefined transform-expression templates by category, used by the
    "Insert function" menu in both the dataset and chart Transform panels."""
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
        ],
    }
