"""
Custom Table View for dataset editing with Excel-like behavior.

This module provides a QTableView implementation optimized for dataset editing
with Excel-like keyboard navigation, editing behavior, and user interactions.
"""

import logging
from PySide6.QtWidgets import QTableView, QApplication, QMenu, QHeaderView
from PySide6.QtGui import QKeySequence, QAction, QPainter, QFont, QFontMetrics
from PySide6.QtCore import Qt, QRect
from random import random

from pandaplot.commands.project.dataset.add_columns_command import AddColumnsCommand
from pandaplot.commands.project.dataset.add_rows_command import AddRowsCommand
from pandaplot.commands.project.dataset.change_column_dtype_command import ChangeColumnDtypeCommand
from pandaplot.commands.project.dataset.delete_columns_command import DeleteColumnsCommand
from pandaplot.commands.project.dataset.delete_rows_command import DeleteRowsCommand
from pandaplot.commands.project.dataset.edit_batch_command import EditBatchCommand
from pandaplot.gui.components.tabs.dataset.pandas_table_model import PandasTableModel
from pandaplot.models.state.app_context import AppContext
from pandaplot.utils.pandas import convert_value


class CustomHeaderView(QHeaderView):
    """Custom header view that displays column number, name, and data type in two rows."""
    
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.dataset = None
        
    def set_dataset(self, dataset):
        """Set the dataset to get column information from."""
        self.dataset = dataset
        
    def paintSection(self, painter, rect, logical_index):
        """Paint a header section with custom two-row layout."""
        if not self.dataset or self.orientation() != Qt.Orientation.Horizontal:
            # Fall back to default painting for vertical headers or when no dataset
            super().paintSection(painter, rect, logical_index)
            return
            
        painter.save()
        
        # Clear the background
        painter.fillRect(rect, self.palette().button())
        
        # Draw border
        painter.setPen(self.palette().mid().color())
        painter.drawRect(rect)
        
        # Get column information
        column_name = str(self.dataset.data.columns[logical_index])
        column_dtype = str(self.dataset.data.dtypes.iloc[logical_index])
        column_number = logical_index + 1
        
        # Prepare fonts
        bold_font = QFont(painter.font())
        bold_font.setBold(True)
        
        italic_font = QFont(painter.font())
        italic_font.setItalic(True)
        italic_font.setPointSize(max(8, italic_font.pointSize() - 1))  # Smaller font for dtype
        
        # Calculate text areas
        top_rect = QRect(rect.x() + 4, rect.y() + 2, rect.width() - 8, rect.height() // 2)
        bottom_rect = QRect(rect.x() + 4, rect.y() + rect.height() // 2, rect.width() - 8, rect.height() // 2)
        
        # Draw first line: "1 - Speed"
        painter.setFont(bold_font)
        painter.setPen(self.palette().text().color())
        first_line = f"{column_number} - {column_name}"
        painter.drawText(top_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, first_line)
        
        # Draw second line: data type
        painter.setFont(italic_font)
        painter.setPen(self.palette().mid().color())  # Lighter color for dtype
        painter.drawText(bottom_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, column_dtype)
        
        painter.restore()
        
    def sizeHint(self):
        """Return size hint for the header - make it taller for two rows."""
        hint = super().sizeHint()
        if self.orientation() == Qt.Orientation.Horizontal:
            hint.setHeight(max(50, hint.height()))  # Ensure adequate height for two lines
        return hint


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


class ColumnHeaderContextMenu(QMenu):
    def __init__(self, app_context, parent, dataset_id, column_indices):
        super().__init__(parent)
        
        self.app_context = app_context
        self.dataset_id = dataset_id
        self.column_indices = column_indices
        
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
        
        # Add column actions
        add_col_left_action = QAction("Add column(s) to the left", self)
        add_col_left_action.triggered.connect(
            lambda: self.app_context.command_executor.execute_command(AddColumnsCommand(
                self.app_context, 
                self.dataset_id, 
                column_names=[f"Column_{col}_{random()}" for col in self.column_indices], 
                reference_positions=self.column_indices,
                side='left'
            ))
        )
        self.addAction(add_col_left_action)
        
        add_col_right_action = QAction("Add column(s) to the right", self)
        add_col_right_action.triggered.connect(
            lambda: self.app_context.command_executor.execute_command(AddColumnsCommand(
                self.app_context, 
                self.dataset_id, 
                column_names=[f"Column_{col+1}_{random()}" for col in self.column_indices], 
                reference_positions=self.column_indices,
                side='right'
            ))
        )
        self.addAction(add_col_right_action)
        
        self.addSeparator()
        
        # Add dtype change submenu (only for single column selection)
        if len(self.column_indices) == 1:
            dtype_menu = QMenu("Change Data Type", self)
            dtype_menu.setStyleSheet(self.styleSheet())  # Apply same styling
            
            # Define available data types
            dtype_options = [
                ("Text/String", "object"),
                ("Integer", "int64"),
                ("Decimal", "float64"),
                ("True/False", "bool"),
                ("Date/Time", "datetime64[ns]")
            ]
            
            for display_name, dtype_code in dtype_options:
                dtype_action = QAction(display_name, self)
                dtype_action.triggered.connect(
                    lambda checked, dt=dtype_code: self.app_context.command_executor.execute_command(
                        ChangeColumnDtypeCommand(
                            self.app_context,
                            self.dataset_id,
                            self.column_indices[0],  # Single column
                            dt
                        )
                    )
                )
                dtype_menu.addAction(dtype_action)
            
            self.addMenu(dtype_menu)
            self.addSeparator()
        
        # Delete column action
        delete_cols_action = QAction("Delete selected column(s)", self)
        delete_cols_action.triggered.connect(
            lambda: self.app_context.command_executor.execute_command(DeleteColumnsCommand(
                self.app_context, 
                self.dataset_id, 
                self.column_indices
            ))
        )
        self.addAction(delete_cols_action)


class RowHeaderContextMenu(QMenu):
    def __init__(self, app_context, parent, dataset_id, row_indices):
        super().__init__(parent)
        
        self.app_context = app_context
        self.dataset_id = dataset_id
        self.row_indices = row_indices
        
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
        
        # Add row actions
        add_row_above_action = QAction("Add row(s) above", self)
        add_row_above_action.triggered.connect(
            lambda: self.app_context.command_executor.execute_command(AddRowsCommand(
                self.app_context, 
                self.dataset_id, 
                reference_positions=self.row_indices,
                side='above'
            ))
        )
        self.addAction(add_row_above_action)
        
        add_row_below_action = QAction("Add row(s) below", self)
        add_row_below_action.triggered.connect(
            lambda: self.app_context.command_executor.execute_command(AddRowsCommand(
                self.app_context, 
                self.dataset_id, 
                reference_positions=self.row_indices,
                side='below'
            ))
        )
        self.addAction(add_row_below_action)
        
        self.addSeparator()
        
        # Delete row action
        delete_rows_action = QAction("Delete selected row(s)", self)
        delete_rows_action.triggered.connect(
            lambda: self.app_context.command_executor.execute_command(DeleteRowsCommand(
                self.app_context, 
                self.dataset_id, 
                self.row_indices
            ))
        )
        self.addAction(delete_rows_action)
        

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
        
        # Set up custom horizontal header
        custom_header = CustomHeaderView(Qt.Orientation.Horizontal, self)
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
