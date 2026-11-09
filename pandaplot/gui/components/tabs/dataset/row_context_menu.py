"""Dataset's row context menu."""

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu

from pandaplot.commands.project.dataset.add_rows_command import AddRowsCommand
from pandaplot.commands.project.dataset.delete_rows_command import DeleteRowsCommand
from pandaplot.services.theme.theme_manager import ThemeManager


class RowHeaderContextMenu(QMenu):
    def __init__(self, app_context, parent, dataset_id, row_indices):
        super().__init__(parent)
        
        self.app_context = app_context
        self.dataset_id = dataset_id
        self.row_indices = row_indices
        
        self._init_ui()
    
    def _init_ui(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        self.setStyleSheet(theme_manager.build_context_menu_stylesheet())

        # Add row actions
        add_row_above_action = QAction("Add row(s) above", self)
        add_row_above_action.triggered.connect(
            lambda: self.app_context.command_executor.execute_command(AddRowsCommand(
                self.app_context, 
                self.dataset_id, 
                reference_positions=self.row_indices,
                side="above"
            ))
        )
        self.addAction(add_row_above_action)
        
        add_row_below_action = QAction("Add row(s) below", self)
        add_row_below_action.triggered.connect(
            lambda: self.app_context.command_executor.execute_command(AddRowsCommand(
                self.app_context, 
                self.dataset_id, 
                reference_positions=self.row_indices,
                side="below"
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