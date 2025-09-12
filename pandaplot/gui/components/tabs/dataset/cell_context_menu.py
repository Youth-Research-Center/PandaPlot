"""Dataset cell context menu."""
from random import random

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from pandaplot.commands.project.dataset.add_columns_command import AddColumnsCommand
from pandaplot.commands.project.dataset.add_rows_command import AddRowsCommand
from pandaplot.commands.project.dataset.delete_columns_command import DeleteColumnsCommand
from pandaplot.commands.project.dataset.delete_rows_command import DeleteRowsCommand


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
