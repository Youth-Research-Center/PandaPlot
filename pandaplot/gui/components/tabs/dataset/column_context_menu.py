"""Dataset column context menu."""
from random import random

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from pandaplot.commands.project.dataset.add_columns_command import AddColumnsCommand
from pandaplot.commands.project.dataset.change_column_dtype_command import ChangeColumnDtypeCommand
from pandaplot.commands.project.dataset.delete_columns_command import DeleteColumnsCommand


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