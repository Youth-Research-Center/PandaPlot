"""
Panel condition functions for conditional sidebar panel visibility.
Provides reusable condition functions for different panel types.
"""

from typing import Optional

from PySide6.QtWidgets import QWidget


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

    class_name = type(tab_widget).__name__
    return class_name == "DatasetTab"


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

    class_name = type(tab_widget).__name__
    return class_name == "ChartTab"



