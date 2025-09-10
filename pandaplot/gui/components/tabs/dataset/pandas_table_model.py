"""
Pandas Table Model for efficient dataset display and editing.

This module provides a QAbstractTableModel implementation that directly
interfaces with pandas DataFrames for high-performance data display and editing.
"""

import logging
from typing import Any, override
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from pandaplot.models.events.event_types import DatasetEvents, DatasetOperationEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.commands.project.dataset.edit_command import EditCommand
from pandaplot.utils.pandas import convert_value


class PandasTableModel(QAbstractTableModel):
    def __init__(self, app_context: AppContext, dataset: Dataset, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)

        self.app_context = app_context
        self._dataset = dataset
        self.setup_event_subscriptions()
    
    @override
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        """Return the number of rows in the DataFrame."""
        return len(self._dataset.data)
    
    @override
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
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
            return str(value) if value is not None else ""        
        return None
    
    def on_dataset_changed(self, event):
        self.logger.info("On dataset changed")
        index = self.index(event["index"][0], event["index"][1])
        self.dataChanged.emit(index, index, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

    def on_add_column_event(self, event):
        self.beginInsertColumns(QModelIndex(), len(self._dataset.data.columns)-1, len(self._dataset.data.columns)-1)
        # TODO update so we know exactly which rows are added 
        self.endInsertColumns()

    def setup_event_subscriptions(self):
        self.app_context.event_bus.subscribe(DatasetEvents.DATASET_DATA_CHANGED, self.on_dataset_changed)
        self.app_context.event_bus.subscribe(DatasetOperationEvents.DATASET_COLUMN_ADDED, self.on_add_column_event)

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
            print("DEBUG: setData failed - invalid index")
            return False
            
        if role != Qt.ItemDataRole.EditRole:
            print("DEBUG: setData failed - wrong role: {role}")
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
    
    def insertRow(self, row, row_data=None):
        self.beginInsertRows(QModelIndex(), row, row)
        if row_data is None:
            empty = {col: [None] for col in self._df.columns}
            new_row = pd.DataFrame(empty)
        else:
            new_row = pd.DataFrame([row_data])
        self._df = pd.concat(
            [self._df.iloc[:row], new_row, self._df.iloc[row:]]
        ).reset_index(drop=True)
        self.endInsertRows()

    def insertColumn(self, col, name=None, series=None):
        self.beginInsertColumns(QModelIndex(), col, col)
        new_col_name = name or self._generate_new_colname()
        if series is None:
            self._df.insert(col, new_col_name, [None] * len(self._df))
        else:
            self._df.insert(col, new_col_name, series.values)
        self.endInsertColumns()
        return new_col_name

    def removeRows(self, rows):
        for row in sorted(rows, reverse=True):
            self.beginRemoveRows(QModelIndex(), row, row)
            self._df.drop(index=row, inplace=True)
            self._df.reset_index(drop=True, inplace=True)
            self.endRemoveRows()

    def removeColumns(self, cols):
        for col in sorted(cols, reverse=True):
            self.beginRemoveColumns(QModelIndex(), col, col)
            self._df.drop(self._df.columns[col], axis=1, inplace=True)
            self.endRemoveColumns()

    def _generate_new_colname(self):
        base = "Novi stupac"
        name = base
        i = 1
        while name in self._df.columns:
            name = f"{base} {i}"
            i += 1
        return name