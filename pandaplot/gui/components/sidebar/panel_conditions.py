"""
Panel condition functions for conditional sidebar panel visibility.
Provides reusable condition functions for different panel types.
"""

from typing import Optional
import logging
from PySide6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


def is_dataset_tab_active(tab_widget: Optional[QWidget]) -> bool:
    """
    Check if current tab is a dataset tab.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if the tab is a dataset tab, False otherwise
    """
    if tab_widget is None:
        return False
    
    # Check by class name (avoid circular imports)
    class_name = type(tab_widget).__name__
    return class_name == 'DatasetTab'


def is_chart_tab_active(tab_widget: Optional[QWidget]) -> bool:
    """
    Check if current tab is a chart tab.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if the tab is a chart tab, False otherwise
    """
    if tab_widget is None:
        return False
    
    # Check by class name (avoid circular imports)
    class_name = type(tab_widget).__name__
    return class_name == 'ChartTab'


def is_note_tab_active(tab_widget: Optional[QWidget]) -> bool:
    """
    Check if current tab is a note tab.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if the tab is a note tab, False otherwise
    """
    if tab_widget is None:
        return False
    
    # Check by class name (avoid circular imports)
    class_name = type(tab_widget).__name__
    return class_name == 'NoteTab'


def is_welcome_tab_active(tab_widget: Optional[QWidget]) -> bool:
    """
    Check if current tab is a welcome tab.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if the tab is a welcome tab, False otherwise
    """
    if tab_widget is None:
        return False
    
    # Check by class name (avoid circular imports)
    class_name = type(tab_widget).__name__
    return class_name == 'WelcomeTab'


def has_numeric_columns(tab_widget: Optional[QWidget]) -> bool:
    """
    Check if current dataset has numeric columns (for analysis panels).
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if the dataset has numeric columns, False otherwise
    """
    if not is_dataset_tab_active(tab_widget):
        return False
    
    try:
        # Get dataset from tab
        if hasattr(tab_widget, 'dataset'):
            dataset = getattr(tab_widget, 'dataset', None)
            if dataset and hasattr(dataset, 'data') and dataset.data is not None:
                df = dataset.data
                # Check if any columns are numeric
                numeric_columns = df.select_dtypes(include=['number']).columns
                return len(numeric_columns) > 0
    except Exception as e:
        logger.error("Error checking numeric columns: %s", e, exc_info=True)
    
    return False


def has_sufficient_data_for_analysis(tab_widget: Optional[QWidget], min_rows: int = 10) -> bool:
    """
    Check if dataset has enough data points for meaningful analysis.
    
    Args:
        tab_widget: The current active tab widget
        min_rows: Minimum number of rows required for analysis
        
    Returns:
        True if the dataset has sufficient data, False otherwise
    """
    if not is_dataset_tab_active(tab_widget):
        return False
    
    try:
        # Get dataset from tab
        if hasattr(tab_widget, 'dataset'):
            dataset = getattr(tab_widget, 'dataset', None)
            if dataset and hasattr(dataset, 'data') and dataset.data is not None:
                df = dataset.data
                return len(df) >= min_rows
    except Exception as e:
        logger.error("Error checking data sufficiency: %s", e, exc_info=True)
    
    return False


def is_editable_dataset(tab_widget: Optional[QWidget]) -> bool:
    """
    Check if current dataset is in editable mode.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if the dataset is editable, False otherwise
    """
    if not is_dataset_tab_active(tab_widget):
        return False
    
    try:
        # Check if dataset tab has editing enabled
        if hasattr(tab_widget, 'is_editing_enabled'):
            return getattr(tab_widget, 'is_editing_enabled', False)
    except Exception as e:
        logger.error("Error checking dataset editability: %s", e, exc_info=True)
    
    return False


def has_data_loaded(tab_widget: Optional[QWidget]) -> bool:
    """
    Check if current dataset tab has data loaded.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if data is loaded, False otherwise
    """
    if not is_dataset_tab_active(tab_widget):
        return False
    
    try:
        # Get dataset from tab
        if hasattr(tab_widget, 'dataset'):
            dataset = getattr(tab_widget, 'dataset', None)
            if dataset and hasattr(dataset, 'data'):
                data = getattr(dataset, 'data', None)
                return data is not None and not data.empty
    except Exception as e:
        logger.error("Error checking data loaded status: %s", e, exc_info=True)
    
    return False


def has_multiple_columns(tab_widget: Optional[QWidget], min_columns: int = 2) -> bool:
    """
    Check if dataset has multiple columns (for multi-column operations).
    
    Args:
        tab_widget: The current active tab widget
        min_columns: Minimum number of columns required
        
    Returns:
        True if the dataset has multiple columns, False otherwise
    """
    if not is_dataset_tab_active(tab_widget):
        return False
    
    try:
        # Get dataset from tab
        if hasattr(tab_widget, 'dataset'):
            dataset = getattr(tab_widget, 'dataset', None)
            if dataset and hasattr(dataset, 'data') and dataset.data is not None:
                df = dataset.data
                return len(df.columns) >= min_columns
    except Exception as e:
        logger.error("Error checking column count: %s", e, exc_info=True)
    
    return False


# Compound conditions
def is_dataset_with_numeric_data(tab_widget: Optional[QWidget]) -> bool:
    """
    Combined condition: dataset tab with numeric columns.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if it's a dataset tab with numeric data, False otherwise
    """
    return is_dataset_tab_active(tab_widget) and has_numeric_columns(tab_widget)


def is_dataset_with_sufficient_data(tab_widget: Optional[QWidget]) -> bool:
    """
    Combined condition: dataset tab with sufficient data for analysis.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if it's a dataset tab with sufficient data, False otherwise
    """
    return (is_dataset_tab_active(tab_widget) and 
            has_sufficient_data_for_analysis(tab_widget) and
            has_data_loaded(tab_widget))


def is_transformable_dataset(tab_widget: Optional[QWidget]) -> bool:
    """
    Combined condition: dataset tab that can be transformed.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if it's a dataset tab that can be transformed, False otherwise
    """
    return (is_dataset_tab_active(tab_widget) and 
            has_data_loaded(tab_widget) and
            has_multiple_columns(tab_widget, min_columns=1))  # At least 1 column for transformation


def is_multi_column_dataset(tab_widget: Optional[QWidget]) -> bool:
    """
    Combined condition: dataset tab with multiple columns for multi-column operations.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if it's a dataset tab with multiple columns, False otherwise
    """
    return (is_dataset_tab_active(tab_widget) and 
            has_data_loaded(tab_widget) and
            has_multiple_columns(tab_widget, min_columns=2))


def is_chart_with_dataset(tab_widget: Optional[QWidget]) -> bool:
    """
    Combined condition: chart tab that has an associated dataset.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if it's a chart tab with an associated dataset, False otherwise
    """
    if not is_chart_tab_active(tab_widget):
        return False
    
    try:
        # Check if chart has an associated dataset
        if hasattr(tab_widget, 'chart'):
            chart = getattr(tab_widget, 'chart', None)
            if chart and hasattr(chart, 'dataset_id'):
                dataset_id = getattr(chart, 'dataset_id', None)
                return dataset_id is not None
    except Exception as e:
        logger.error("Error checking chart dataset association: %s", e, exc_info=True)
    
    return False


# Utility functions for debugging and testing
def get_tab_info(tab_widget: Optional[QWidget]) -> dict:
    """
    Get detailed information about a tab widget for debugging.
    
    Args:
        tab_widget: The tab widget to analyze
        
    Returns:
        Dictionary with tab information
    """
    if tab_widget is None:
        return {'type': None, 'has_dataset': False, 'has_chart': False}
    
    info = {
        'type': type(tab_widget).__name__,
        'has_dataset': hasattr(tab_widget, 'dataset'),
        'has_chart': hasattr(tab_widget, 'chart'),
        'has_data': False,
        'column_count': 0,
        'row_count': 0,
        'numeric_columns': 0
    }
    
    # Add dataset information if available
    if info['has_dataset']:
        try:
            dataset = getattr(tab_widget, 'dataset', None)
            if dataset and hasattr(dataset, 'data') and dataset.data is not None:
                df = dataset.data
                info.update({
                    'has_data': True,
                    'column_count': len(df.columns),
                    'row_count': len(df),
                    'numeric_columns': len(df.select_dtypes(include=['number']).columns),
                    'dataset_id': getattr(dataset, 'id', None),
                    'dataset_name': getattr(dataset, 'name', None)
                })
        except Exception as e:
            info['error'] = str(e)
    
    # Add chart information if available
    if info['has_chart']:
        try:
            chart = getattr(tab_widget, 'chart', None)
            if chart:
                info.update({
                    'chart_id': getattr(chart, 'id', None),
                    'chart_name': getattr(chart, 'name', None),
                    'chart_dataset_id': getattr(chart, 'dataset_id', None)
                })
        except Exception as e:
            info['chart_error'] = str(e)
    
    return info


# Analysis-specific panel conditions
def is_dataset_with_analysis_data(tab_widget: Optional[QWidget]) -> bool:
    """
    Combined condition: dataset tab with data suitable for analysis.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if it's a dataset tab with data suitable for analysis, False otherwise
    """
    return (is_dataset_tab_active(tab_widget) and 
            has_numeric_columns(tab_widget) and
            has_sufficient_data_for_analysis(tab_widget) and
            has_multiple_columns(tab_widget, min_columns=2))


def has_xy_data(tab_widget: Optional[QWidget]) -> bool:
    """
    Check if dataset has at least 2 numeric columns for X-Y analysis.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if dataset has at least 2 numeric columns, False otherwise
    """
    try:
        if hasattr(tab_widget, 'dataset'):
            dataset = getattr(tab_widget, 'dataset', None)
            if dataset and hasattr(dataset, 'data') and dataset.data is not None:
                df = dataset.data
                numeric_columns = df.select_dtypes(include=['number']).columns
                return len(numeric_columns) >= 2
    except Exception as e:
        logger.error("Error checking XY data: %s", e, exc_info=True)
    
    return False


# Chart-specific panel conditions
def is_dataset_with_chart_data(tab_widget: Optional[QWidget]) -> bool:
    """
    Combined condition: dataset tab with data suitable for charting.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if it's a dataset tab with data suitable for charting, False otherwise
    """
    return (is_dataset_tab_active(tab_widget) and 
            has_data_loaded(tab_widget) and
            has_multiple_columns(tab_widget, min_columns=2))


def can_create_chart(tab_widget: Optional[QWidget]) -> bool:
    """
    Check if chart can be created from current context.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if chart can be created, False otherwise
    """
    return (is_dataset_tab_active(tab_widget) or is_chart_tab_active(tab_widget)) and has_data_loaded(tab_widget)


def should_show_chart_properties(tab_widget: Optional[QWidget]) -> bool:
    """
    Determine if chart properties panel should be shown.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if chart properties panel should be visible, False otherwise
    """
    # Show for chart tabs always
    if is_chart_tab_active(tab_widget):
        return True
    
    # Show for dataset tabs with chartable data
    return is_dataset_with_chart_data(tab_widget)


def should_show_fit_panel(tab_widget: Optional[QWidget]) -> bool:
    """
    Determine if the fit panel should be visible based on current tab.
    Fit panel should be visible for chart tabs with data to fit.
    
    Args:
        tab_widget: The current active tab widget
        
    Returns:
        True if fit panel should be visible, False otherwise
    """
    # Show for chart tabs (can perform fitting on chart data)
    if is_chart_tab_active(tab_widget):
        return True
    
    # Show for dataset tabs with numeric data suitable for fitting
    return is_dataset_with_chart_data(tab_widget)
