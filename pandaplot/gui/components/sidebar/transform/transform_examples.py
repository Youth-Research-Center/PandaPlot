"""
Transform examples and help text for the transform panel.
Extracted from transform_tab.py for reuse in the sidebar interface.
"""

from typing import Dict, List

# Column Operation Examples
COLUMN_OPERATION_EXAMPLES = """Column Operation Examples:
• value + 2                    # Add 2 to each value
• value * 2                    # Multiply by 2
• value ** 2                   # Square each value
• abs(value)                   # Absolute value
• round(value, 2)              # Round to 2 decimal places
• value if value > 0 else 0    # Set negative values to 0
• np.sqrt(value)               # Square root
• np.log(value)                # Natural logarithm
• value.str.upper()            # Uppercase (for strings)
• value.str.strip()            # Remove whitespace (for strings)
• pd.to_datetime(value)        # Convert to datetime
• (value - value.mean()) / value.std()  # Standardize (z-score)"""

# Row Operation Examples  
ROW_OPERATION_EXAMPLES = """Row Operation Examples:
• row['column1'] + row['column2']     # Sum two columns
• row['column1'] * row['column2']     # Multiply two columns
• row.sum()                           # Sum all numeric columns in row
• row.mean()                          # Mean of all numeric columns in row
• row['column1'] / row['column2'] if row['column2'] != 0 else 0  # Safe division
• row.max() - row.min()               # Range of values in row
• row.std()                           # Standard deviation of row values
• len([x for x in row if pd.notna(x)]) # Count non-null values in row"""

# Multi-Column Operation Examples
MULTI_COLUMN_OPERATION_EXAMPLES = """Multi-Column Operation Examples:
• cols.sum(axis=1)                    # Sum selected columns row-wise
• cols.mean(axis=1)                   # Mean of selected columns row-wise
• cols.max(axis=1)                    # Maximum value in selected columns per row
• cols.std(axis=1)                    # Standard deviation of selected columns per row
• cols.iloc[:, 0] + cols.iloc[:, 1]   # Add first two selected columns
• cols.prod(axis=1)                   # Product of selected columns
• cols.median(axis=1)                 # Median of selected columns
• (cols.iloc[:, 0] - cols.iloc[:, 1]).abs()  # Absolute difference between first two columns"""

# Help text for different transform types
HELP_TEXT = {
    "Custom Function": """
Custom Function Help:
- Use 'value', 'x', 'column', or 'data' to reference the source column
- Available functions: pandas (pd), numpy (np), math functions
- Examples: value * 2, np.sqrt(value), value.str.upper()
- Use conditional expressions: value if value > 0 else 0
""",
    
    "Math Operations": """
Math Operations Help:
- Basic operations: +, -, *, /, **, %
- Functions: abs(), round(), min(), max()
- Numpy: np.sqrt(), np.log(), np.exp(), np.sin(), np.cos()
- Statistics: (value - value.mean()) / value.std()
- Examples: value ** 2, np.sqrt(abs(value)), round(value * 100, 2)
""",
    
    "String Operations": """
String Operations Help:
- Case: value.str.upper(), value.str.lower(), value.str.title()
- Whitespace: value.str.strip(), value.str.lstrip(), value.str.rstrip()
- Replace: value.str.replace('old', 'new')
- Extract: value.str.extract(r'(\\d+)')  # Extract numbers
- Length: value.str.len()
- Split: value.str.split(',').str[0]  # Get first part
""",
    
    "Date/Time Operations": """
Date/Time Operations Help:
- Parse: pd.to_datetime(value)
- Format: pd.to_datetime(value).dt.strftime('%Y-%m-%d')
- Extract: .dt.year, .dt.month, .dt.day, .dt.dayofweek
- Operations: pd.to_datetime(value) + pd.Timedelta(days=1)
- Age calculation: (pd.Timestamp.now() - pd.to_datetime(value)).dt.days
""",
    
    "Statistical Operations": """
Statistical Operations Help:
- Ranking: value.rank(), value.rank(pct=True)
- Moving: value.rolling(3).mean(), value.rolling(5).std()
- Cumulative: value.cumsum(), value.cumprod(), value.cummax()
- Shifting: value.shift(1), value.shift(-1)
- Standardization: (value - value.mean()) / value.std()
- Percentiles: value.quantile(0.95)
"""
}

# Quick function templates by category
QUICK_FUNCTIONS = {
    "Math Operations": [
        {"name": "Double", "code": "value * 2", "description": "Multiply by 2"},
        {"name": "Square", "code": "value ** 2", "description": "Square the values"},
        {"name": "Square Root", "code": "np.sqrt(value)", "description": "Square root"},
        {"name": "Absolute", "code": "abs(value)", "description": "Absolute value"},
        {"name": "Round", "code": "round(value, 2)", "description": "Round to 2 decimals"},
        {"name": "Percentage", "code": "value * 100", "description": "Convert to percentage"},
    ],
    
    "String Operations": [
        {"name": "Uppercase", "code": "value.str.upper()", "description": "Convert to uppercase"},
        {"name": "Lowercase", "code": "value.str.lower()", "description": "Convert to lowercase"},
        {"name": "Title Case", "code": "value.str.title()", "description": "Title case"},
        {"name": "Strip", "code": "value.str.strip()", "description": "Remove whitespace"},
        {"name": "Length", "code": "value.str.len()", "description": "String length"},
        {"name": "First Word", "code": "value.str.split().str[0]", "description": "Extract first word"},
    ],
    
    "Date/Time Operations": [
        {"name": "Parse Date", "code": "pd.to_datetime(value)", "description": "Convert to datetime"},
        {"name": "Year", "code": "pd.to_datetime(value).dt.year", "description": "Extract year"},
        {"name": "Month", "code": "pd.to_datetime(value).dt.month", "description": "Extract month"},
        {"name": "Day of Week", "code": "pd.to_datetime(value).dt.dayofweek", "description": "Day of week (0=Monday)"},
        {"name": "Format Date", "code": "pd.to_datetime(value).dt.strftime('%Y-%m-%d')", "description": "Format as YYYY-MM-DD"},
        {"name": "Days Since", "code": "(pd.Timestamp.now() - pd.to_datetime(value)).dt.days", "description": "Days since date"},
    ],
    
    "Statistical Operations": [
        {"name": "Z-Score", "code": "(value - value.mean()) / value.std()", "description": "Standardize values"},
        {"name": "Rank", "code": "value.rank()", "description": "Rank values"},
        {"name": "Percentile", "code": "value.rank(pct=True) * 100", "description": "Percentile rank"},
        {"name": "Rolling Mean", "code": "value.rolling(3).mean()", "description": "3-period moving average"},
        {"name": "Cumulative", "code": "value.cumsum()", "description": "Cumulative sum"},
        {"name": "Lag", "code": "value.shift(1)", "description": "Previous value"},
    ]
}


def get_examples_for_transform_type(transform_type: str) -> str:
    """Get example text for specific transform type."""
    examples_map = {
        "Custom Function": COLUMN_OPERATION_EXAMPLES,
        "Math Operations": COLUMN_OPERATION_EXAMPLES,
        "String Operations": COLUMN_OPERATION_EXAMPLES,  # Will be filtered by category
        "Date/Time Operations": COLUMN_OPERATION_EXAMPLES,  # Will be filtered by category
        "Statistical Operations": COLUMN_OPERATION_EXAMPLES,  # Will be filtered by category
    }
    
    return examples_map.get(transform_type, COLUMN_OPERATION_EXAMPLES)


def get_help_text_for_transform_type(transform_type: str) -> str:
    """Get help text for specific transform type."""
    return HELP_TEXT.get(transform_type, HELP_TEXT["Custom Function"])


def get_quick_functions_for_type(transform_type: str) -> List[Dict[str, str]]:
    """Get quick function templates for specific transform type."""
    if transform_type in QUICK_FUNCTIONS:
        return QUICK_FUNCTIONS[transform_type]
    else:
        # Return math operations as default
        return QUICK_FUNCTIONS["Math Operations"]


def get_all_transform_types() -> List[str]:
    """Get list of all available transform types."""
    return list(QUICK_FUNCTIONS.keys())


def search_functions(query: str) -> List[Dict[str, str]]:
    """Search for functions matching the query."""
    results = []
    query_lower = query.lower()
    
    for category, functions in QUICK_FUNCTIONS.items():
        for func in functions:
            if (query_lower in func["name"].lower() or 
                query_lower in func["description"].lower() or 
                query_lower in func["code"].lower()):
                
                result = func.copy()
                result["category"] = category
                results.append(result)
    
    return results


# Common validation patterns
VALIDATION_PATTERNS = {
    "dangerous_imports": [
        r"\bimport\s+os\b", r"\bimport\s+sys\b", r"\bimport\s+subprocess\b",
        r"\bfrom\s+os\b", r"\bfrom\s+sys\b", r"\bfrom\s+subprocess\b"
    ],
    "dangerous_functions": [
        r"\beval\b", r"\bexec\b", r"\bopen\b", r"\bfile\b",
        r"\b__.*__\b", r"\bglobals\b", r"\blocals\b"
    ],
    "file_operations": [
        r"\bwith\s+open\b", r"\.read\(\)", r"\.write\(\)", r"\.delete\(\)"
    ]
}


def validate_expression_safety(expression: str) -> tuple[bool, str]:
    """
    Validate that an expression is safe to execute.
    
    Returns:
        Tuple of (is_safe, error_message)
    """
    import re
    
    if not expression.strip():
        return False, "Expression cannot be empty"
    
    # Check for dangerous patterns
    for pattern_type, patterns in VALIDATION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, expression, re.IGNORECASE):
                return False, f"Potentially unsafe operation detected: {pattern_type}"
    
    # Try to compile the expression
    try:
        compile(expression, "<expression>", "eval")
        return True, ""
    except SyntaxError as e:
        return False, f"Syntax error: {e}"
    except Exception as e:
        return False, f"Invalid expression: {e}"
