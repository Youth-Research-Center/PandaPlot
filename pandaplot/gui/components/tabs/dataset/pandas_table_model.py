"""
Pandas Table Model for efficient dataset display and editing.

This module provides a QAbstractTableModel implementation that directly
interfaces with pandas DataFrames for high-performance data display and editing.
"""

import logging
from typing import Any, override

import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from pandaplot.commands.project.dataset.edit_command import EditCommand
from pandaplot.models.events.event_data import (
    DatasetColumnRenamedData,
    DatasetColumnsAddedData,
    DatasetColumnsRemovedData,
    DatasetRowsAddedData,
    DatasetRowsRemovedData,
)
from pandaplot.models.events.event_types import DatasetEvents, DatasetOperationEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.utils.pandas import convert_value


class PandasTableModel(QAbstractTableModel):
    def __init__(self, app_context: AppContext, dataset: Dataset, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.app_context = app_context
        self._dataset = dataset
        # (event_type, handler) pairs this model has subscribed, so
        # unsubscribe_all() can remove exactly these -- mirrors
        # WidgetExtension's own tracking, since this model isn't one (it's a
        # QAbstractTableModel, not a widget) but needs the same "unsubscribe
        # before this gets torn down" support unsubscribe_widget_tree() gives
        # actual WidgetExtension descendants.
        self._subscriptions: list[tuple[str, Any]] = []
        self.setup_event_subscriptions()
    
    @override
    def rowCount(self, parent: QModelIndex | None = None) -> int:
        """Return the number of rows in the DataFrame."""
        return len(self._dataset.data)

    @override
    def columnCount(self, parent: QModelIndex | None = None) -> int:
        """Return the number of columns in the DataFrame."""
        return len(self._dataset.data.columns)
    
    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Return data for the given index and role.
        
        Args:
            index: The model index
            role: The data role
            
        Returns:
            The data for the given index and role
        """
        if not index.isValid():
            return None
        value = self._dataset.data.iloc[index.row(), index.column()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return "" if pd.isna(value) else str(value)
        return None
    
    def on_dataset_changed(self, event):
        self.logger.info("On dataset changed: start")
        start_index = self.index(event["start_index"][0], event["start_index"][1])
        end_index = self.index(event["end_index"][0], event["end_index"][1])
        self.dataChanged.emit(start_index, end_index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        self.logger.info("On dataset changed: end")

    def on_add_column_event(self, event):
        self.logger.info("On add column event")
        event_data = DatasetColumnsAddedData.from_dict(event)
        positions = event_data.column_positions
        self.beginInsertColumns(QModelIndex(), min(positions), max(positions))
        self.endInsertColumns()

    def on_remove_column_event(self, event):
        self.logger.info("On remove column event")
        event_data = DatasetColumnsRemovedData.from_dict(event)
        positions = event_data.column_positions
        self.beginRemoveColumns(QModelIndex(), min(positions), max(positions))

        self.endRemoveColumns()

    def on_rename_column_event(self, event):
        self.logger.info("On rename column event")
        event_data = DatasetColumnRenamedData.from_dict(event)
        self.headerDataChanged.emit(
            Qt.Orientation.Horizontal, event_data.column_index, event_data.column_index)

    def on_add_row_event(self, event):
        self.logger.info("On add row event")
        event_data = DatasetRowsAddedData.from_dict(event)
        positions = event_data.row_positions
        self.beginInsertRows(QModelIndex(), min(positions), max(positions))
        self.endInsertRows()
    
    def on_remove_row_event(self, event):
        self.logger.info("On remove row event")
        event_data = DatasetRowsRemovedData.from_dict(event)
        positions = event_data.row_positions
        self.beginRemoveRows(QModelIndex(), min(positions), max(positions))
        self.endRemoveRows()

    def setup_event_subscriptions(self):
        subscriptions = (
            (DatasetEvents.DATASET_DATA_CHANGED, self.on_dataset_changed),
            (DatasetOperationEvents.DATASET_COLUMN_ADDED, self.on_add_column_event),
            (DatasetOperationEvents.DATASET_COLUMN_REMOVED, self.on_remove_column_event),
            (DatasetOperationEvents.DATASET_COLUMN_RENAMED, self.on_rename_column_event),
            (DatasetOperationEvents.DATASET_ROW_ADDED, self.on_add_row_event),
            (DatasetOperationEvents.DATASET_ROW_REMOVED, self.on_remove_row_event),
        )
        for event_type, handler in subscriptions:
            self.app_context.event_bus.subscribe(event_type, handler)
            self._subscriptions.append((event_type, handler))

    def unsubscribe_all(self) -> None:
        """Unsubscribe from every event this model subscribed to in
        setup_event_subscriptions(). Called by unsubscribe_widget_tree() when
        the owning tab (e.g. DatasetTab) is torn down -- without this, a
        dataset event firing after the tab closes would still invoke this
        model's handlers (dataChanged.emit() etc.) against a model whose
        owning view/tab may already be gone."""
        for event_type, handler in self._subscriptions:
            self.app_context.event_bus.unsubscribe(event_type, handler)
        self._subscriptions.clear()

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        """
        Set data for the given index.
        
        Args:
            index: The model index
            value: The new value
            role: The data role
            
        Returns:
            True if the data was set successfully
        """
        if not index.isValid():
            self.logger.debug("setData failed - invalid index")
            return False
            
        if role != Qt.ItemDataRole.EditRole:
            self.logger.debug("setData failed - wrong role: %s", role)
            return False
        
        row = index.row()
        col = index.column()
        converted_value = convert_value(value, self._dataset.data.dtypes.iloc[col])
        #self._dataset.data.iloc[row, col] = converted_value
        editCommand = EditCommand(self.app_context, self._dataset.id, (row, col,), self._dataset.data.iloc[row, col], converted_value)
        self.app_context.command_executor.execute_command(editCommand)
        return True
    
    def headerData(self, section: int, orientation: Qt.Orientation, 
                   role: int = Qt.ItemDataRole.DisplayRole) -> Any:
        """
        Return header data for the given section and orientation.
        
        Args:
            section: The section number
            orientation: Horizontal or vertical orientation
            role: The data role
            
        Returns:
            The header data
        """
        if role != Qt.ItemDataRole.DisplayRole:
            return None

        if orientation == Qt.Orientation.Horizontal:
            return str(self._dataset.data.columns[section])
        else:
            return str(section + 1)  # 1-based row numbers like Excel
    
    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """
        Return the flags for the given index.
        
        Args:
            index: The model index
            
        Returns:
            The item flags
        """
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        
        # All valid cells are selectable, enabled, and editable (Excel-like)
        return (Qt.ItemFlag.ItemIsSelectable | 
                Qt.ItemFlag.ItemIsEnabled | 
                Qt.ItemFlag.ItemIsEditable)