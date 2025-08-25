"""
Panel condition functions for conditional sidebar panel visibility.
Provides reusable condition functions for different panel types.
"""

import logging
from typing import Optional

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


# Analysis-specific panel conditions
def is_dataset_with_analysis_data(tab_widget: Optional[QWidget]) -> bool:
    """
    Combined condition: dataset tab with data suitable for analysis.

    Args:
        tab_widget: The current active tab widget

    Returns:
        True if it's a dataset tab with data suitable for analysis, False otherwise
    """
    # TODO: not sure why is this needed and present in main window
    return (is_dataset_tab_active(tab_widget) and
            has_numeric_columns(tab_widget) and
            has_sufficient_data_for_analysis(tab_widget) and
            has_multiple_columns(tab_widget, min_columns=2))


def should_show_chart_properties(tab_widget: Optional[QWidget]) -> bool:
    """
    Determine if chart properties panel should be shown.

    Args:
        tab_widget: The current active tab widget

    Returns:
        True if chart properties panel should be visible, False otherwise
    """
    # Show for chart tabs always
    return is_chart_tab_active(tab_widget)


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
    return is_chart_tab_active(tab_widget)
