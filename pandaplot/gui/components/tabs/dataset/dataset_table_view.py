"""
Custom Table View for dataset editing with Excel-like behavior.

This module provides a QTableView implementation optimized for dataset editing
with Excel-like keyboard navigation, editing behavior, and user interactions.
"""

import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QApplication, QHeaderView, QTableView

from pandaplot.commands.project.dataset.edit_batch_command import EditBatchCommand
from pandaplot.gui.components.tabs.dataset.cell_context_menu import CellContextMenu
from pandaplot.gui.components.tabs.dataset.column_context_menu import ColumnHeaderContextMenu
from pandaplot.gui.components.tabs.dataset.pandas_table_model import PandasTableModel
from pandaplot.gui.components.tabs.dataset.pheader_view import PHeaderView
from pandaplot.gui.components.tabs.dataset.row_context_menu import RowHeaderContextMenu
from pandaplot.models.state.app_context import AppContext
from pandaplot.utils.pandas import convert_value


class DatasetTableView(QTableView):

    def __init__(self, app_context:AppContext, model: PandasTableModel, parent=None):
        """
        Initialize the dataset table view.
        
        Args:
            app_context: Application context
            model: table model
            parent: Parent widget
        """
        super().__init__(parent)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app_context = app_context
        self.setModel(model)
        self._model = model
        
        # Set up custom horizontal header
        custom_header = PHeaderView(Qt.Orientation.Horizontal, self)
        custom_header.set_dataset(model._dataset)
        self.setHorizontalHeader(custom_header)
        
        # Set up context menu for cells
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.openMenu)
        
        # Configure headers to allow selection
        self.horizontalHeader().setSectionsClickable(True)
        self.verticalHeader().setSectionsClickable(True)
        
        # Enable single and multiple selection modes for headers
        self.horizontalHeader().setSelectionMode(QHeaderView.SelectionMode.ExtendedSelection)
        self.verticalHeader().setSelectionMode(QHeaderView.SelectionMode.ExtendedSelection)
        
        # Connect header selection signals
        self.horizontalHeader().sectionClicked.connect(self._on_column_header_clicked)
        self.verticalHeader().sectionClicked.connect(self._on_row_header_clicked)
        
        # Set up context menus for headers
        self.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.verticalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.horizontalHeader().customContextMenuRequested.connect(self._on_column_header_context_menu)
        self.verticalHeader().customContextMenuRequested.connect(self._on_row_header_context_menu)
        
        # Configure horizontal header for two-line display
        self.horizontalHeader().setMinimumHeight(50)  # Ensure enough height for two lines
        self.horizontalHeader().setDefaultSectionSize(120)  # Make columns wider to accommodate text

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
    
    def _on_column_header_clicked(self, logical_index):
        """Handle column header clicks to select entire columns."""
        self.selectColumn(logical_index)
    
    def _on_row_header_clicked(self, logical_index):
        """Handle row header clicks to select entire rows."""
        self.selectRow(logical_index)
    
    def _on_column_header_context_menu(self, position):
        """Handle right-click context menu on column headers."""
        # Get the logical index of the column header that was right-clicked
        logical_index = self.horizontalHeader().logicalIndexAt(position)
        if logical_index == -1:
            return
            
        # Get all selected columns
        selected_columns = []
        selection_model = self.selectionModel()
        if selection_model:
            selected_indexes = selection_model.selectedColumns()
            if selected_indexes:
                selected_columns = [index.column() for index in selected_indexes]
            else:
                # If no columns are selected, use the clicked column
                selected_columns = [logical_index]
        else:
            selected_columns = [logical_index]
        
        # Show context menu
        menu = ColumnHeaderContextMenu(
            self.app_context, 
            self, 
            self._model._dataset.id, 
            selected_columns
        )
        global_position = self.horizontalHeader().mapToGlobal(position)
        menu.exec(global_position)
    
    def _on_row_header_context_menu(self, position):
        """Handle right-click context menu on row headers."""
        # Get the logical index of the row header that was right-clicked
        logical_index = self.verticalHeader().logicalIndexAt(position)
        if logical_index == -1:
            return
            
        # Get all selected rows
        selected_rows = []
        selection_model = self.selectionModel()
        if selection_model:
            selected_indexes = selection_model.selectedRows()
            if selected_indexes:
                selected_rows = [index.row() for index in selected_indexes]
            else:
                # If no rows are selected, use the clicked row
                selected_rows = [logical_index]
        else:
            selected_rows = [logical_index]
        
        # Show context menu
        menu = RowHeaderContextMenu(
            self.app_context, 
            self, 
            self._model._dataset.id, 
            selected_rows
        )
        global_position = self.verticalHeader().mapToGlobal(position)
        menu.exec(global_position)
