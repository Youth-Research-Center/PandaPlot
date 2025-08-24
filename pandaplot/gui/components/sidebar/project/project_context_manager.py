
import logging

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QMenu,
    QWidget,
)

from pandaplot.gui.components.sidebar.project.project_command_manager import (
    ProjectPanelCommandManager,
)
from pandaplot.models.state.app_context import AppContext


class ProjectViewPanelContextManager(QMenu):
    def __init__(self, parent: QWidget, app_context: AppContext, command_manager: ProjectPanelCommandManager, getItemAt, getGlobalPosition):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.app_state = app_context.get_app_state()
        self.command_manager = command_manager
        self.getItemAt = getItemAt
        self.getGlobalPosition = getGlobalPosition

        self._setup_ui()

    def _setup_ui(self):
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
        # Open action
        self.open_action = QAction("Open", self)
        self.open_action.triggered.connect(
            self.command_manager.open_selected_item)
        self.addAction(self.open_action)

        self.addSeparator()

        # Rename action
        self.rename_action = QAction("Rename", self)
        self.rename_action.triggered.connect(
            self.command_manager.rename_selected_item)
        self.addAction(self.rename_action)

        self.addSeparator()

        # Add actions
        self.add_folder_action = QAction("Add Folder", self)
        self.add_folder_action.triggered.connect(
            self.command_manager.add_folder)
        self.addAction(self.add_folder_action)

        self.add_note_action = QAction("Add Note", self)
        self.add_note_action.triggered.connect(self.command_manager.add_note)
        self.addAction(self.add_note_action)

        self.import_csv_action = QAction("Import CSV...", self)
        self.import_csv_action.triggered.connect(
            self.command_manager.import_csv)
        self.addAction(self.import_csv_action)

        self.create_empty_dataset_action = QAction(
            "Create Empty Dataset", self)
        self.create_empty_dataset_action.triggered.connect(
            self.command_manager.create_empty_dataset)
        self.addAction(self.create_empty_dataset_action)

        # Chart creation action (for datasets)
        self.create_chart_action = QAction("Create Chart", self)
        self.create_chart_action.triggered.connect(
            self.command_manager.create_chart_from_dataset)
        self.addAction(self.create_chart_action)

        self.addSeparator()

        # Delete action
        self.delete_action = QAction("Delete", self)
        self.delete_action.triggered.connect(
            self.command_manager.delete_selected_item)
        self.addAction(self.delete_action)

    def show_context_menu(self, position):
        """Show context menu at the given position."""
        if not self.app_state.has_project:
            return

        item = self.getItemAt(position)
        if not item:
            self.logger.debug("No item at the given position")
            return

        # Enable/disable actions based on item type
        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        if not item_data:
            self.logger.debug("Item has no associated data")
            self.exec(self.getGlobalPosition(position))
            return

        item_type = item_data.get('type', '')

        # Disable rename and delete for project root
        can_rename = item_type != 'project'
        can_delete = item_type != 'project'

        # Show chart creation only for datasets
        self.create_chart_action.setVisible(item_type == 'dataset')

        self.rename_action.setEnabled(can_rename)
        self.delete_action.setEnabled(can_delete)

        self.exec(self.getGlobalPosition(position))
