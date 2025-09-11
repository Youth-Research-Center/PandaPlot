"""
Custom Table View for dataset editing with Excel-like behavior.

This module provides a QTableView implementation optimized for dataset editing
with Excel-like keyboard navigation, editing behavior, and user interactions.
"""

import logging
from PySide6.QtWidgets import QTableView, QApplication, QMenu
from PySide6.QtGui import QKeySequence, QAction
from PySide6.QtCore import Qt
from random import random

from pandaplot.commands.project.dataset.add_columns_command import AddColumnsCommand
from pandaplot.commands.project.dataset.add_rows_command import AddRowsCommand
from pandaplot.commands.project.dataset.delete_columns_command import DeleteColumnsCommand
from pandaplot.commands.project.dataset.delete_rows_command import DeleteRowsCommand
from pandaplot.commands.project.dataset.edit_batch_command import EditBatchCommand
from pandaplot.gui.components.tabs.dataset.pandas_table_model import PandasTableModel
from pandaplot.models.state.app_context import AppContext
from pandaplot.utils.pandas import convert_value

class CellContextMenu(QMenu):
    def __init__(self, app_context, parent, dataset_id, indexes):
        super().__init__(parent)

        self.app_context = app_context
        self.dataset_id = dataset_id
        self.indexes = indexes
        
        self._init_ui()

    def _init_ui(self):
        self.setStyleSheet("""
            QMenu {
                background-color: #ffffff;
                color: black;
                border: 1px solid #cccccc;
            }
            QMenu::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QMenu::item:hover {
                background-color: #e5f3ff;
                color: black;
            }
        """)

        rows = list(set(index.row() for index in self.indexes))
        cols = list(set(index.column() for index in self.indexes))
        rows.sort()
        cols.sort()
        
        add_row_below_action = QAction("Add row(s) below", self)
        add_row_below_action.triggered.connect(
            lambda: self.app_context.command_executor.execute_command(AddRowsCommand(
                self.app_context, 
                self.dataset_id, 
                reference_positions=rows,  # Reference the selected rows
                side='below'  # Insert below selected rows
            ))
        )
        self.addAction(add_row_below_action)

        add_row_above_action = QAction("Add row(s) above", self)
        add_row_above_action.triggered.connect(
            lambda: self.app_context.command_executor.execute_command(AddRowsCommand(
                self.app_context, 
                self.dataset_id, 
                reference_positions=rows,  # Reference the selected rows
                side='above'  # Insert above selected rows
            ))
        )
        self.addAction(add_row_above_action)

        add_col_right_action = QAction("Add column(s) to the right", self)
        add_col_right_action.triggered.connect(
            lambda: self.app_context.command_executor.execute_command(AddColumnsCommand(
                self.app_context, 
                self.dataset_id, 
                column_names=[f"Column_{col+1}_{random()}" for col in cols], 
                reference_positions=cols,  # Reference the selected columns
                side='right'  # Insert to the right of selected columns
            ))
        )
        self.addAction(add_col_right_action)

        add_col_left_action = QAction("Add column(s) to the left", self)
        add_col_left_action.triggered.connect(
            lambda: self.app_context.command_executor.execute_command(AddColumnsCommand(
                self.app_context, 
                self.dataset_id, 
                column_names=[f"Column_{col}_{random()}" for col in cols], 
                reference_positions=cols,  # Reference the selected columns
                side='left'  # Insert to the left of selected columns
            ))
        )
        self.addAction(add_col_left_action)

        self.addSeparator()
        
        remove_rows_action = QAction("Delete selected rows", self)
        remove_rows_action.triggered.connect(
            lambda: self.app_context.command_executor.execute_command(DeleteRowsCommand(self.app_context, self.dataset_id, rows))
        )
        self.addAction(remove_rows_action)

        remove_cols_action = QAction("Delete selected columns", self)
        remove_cols_action.triggered.connect(
            lambda: self.app_context.command_executor.execute_command(DeleteColumnsCommand(self.app_context, self.dataset_id, cols))
        )
        self.addAction(remove_cols_action)
        

class DatasetTableView(QTableView):
    """
    A QTableView optimized for dataset editing with Excel-like behavior.
    
    Features:
    - Always editable (Excel-like behavior)
    - Enhanced keyboard navigation
    - Smart cell editing
    - Copy/paste support (future)
    - Context menu integration (future)
    """

    def __init__(self, app_context:AppContext, model: PandasTableModel, parent=None):
        """
        Initialize the dataset table view.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app_context = app_context
        self.setModel(model)
        self._model = model
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.openMenu)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.StandardKey.Copy):
            self.copySelection()
        elif event.matches(QKeySequence.StandardKey.Paste):
            self.pasteSelection()
        else:
            super().keyPressEvent(event)
    
    def copySelection(self):
        selection = self.selectionModel().selectedIndexes()
        if not selection:
            return
        rows = sorted(index.row() for index in selection)
        cols = sorted(index.column() for index in selection)
        rowcount = rows[-1] - rows[0] + 1
        colcount = cols[-1] - cols[0] + 1
        table = [["" for _ in range(colcount)] for _ in range(rowcount)]
        for index in selection:
            row = index.row() - rows[0]
            col = index.column() - cols[0]
            table[row][col] = index.data()
        text = "\n".join(["\t".join(row) for row in table])
        QApplication.clipboard().setText(text)

    def pasteSelection(self):
        clipboard = QApplication.clipboard().text()
        if not clipboard:
            return
        selection = self.selectionModel().selectedIndexes()
        if not selection:
            return
        start_row = selection[0].row()
        start_col = selection[0].column()
        rows = clipboard.split("\n")


        new_data = []
        for i, row in enumerate(rows):
            if not row.strip():
                continue
            cols = row.split("\t")
            new_row = []
            for j, value in enumerate(cols):
                idx = self._model.index(start_row + i, start_col + j)
                new_value = convert_value(value, self._model._dataset.data.dtypes.iloc[idx.column()]) if idx.isValid() else value
                new_row.append(new_value)
            new_data.append(new_row)

        self.app_context.command_executor.execute_command(EditBatchCommand(
            app_context=self.app_context, 
            dataset_id=self._model._dataset.id,
            start_row=start_row,
            start_column=start_col,
            new_data=new_data
        ))

    def openMenu(self, position):
        indexes = self.selectionModel().selectedIndexes()
        if not indexes:
            return
        self.menu = CellContextMenu(self.app_context, self, self._model._dataset.id, indexes)
        self.menu.exec(self.viewport().mapToGlobal(position))
