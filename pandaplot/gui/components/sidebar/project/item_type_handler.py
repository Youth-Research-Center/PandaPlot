import logging
from abc import ABC

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QLabel,
    QMenu,
    QMessageBox,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pandaplot.commands.project.dataset.add_column_command import AddColumnCommand
from pandaplot.commands.project.dataset.add_row_command import AddRowCommand
from pandaplot.commands.project.dataset.create_empty_dataset_command import (
    CreateEmptyDatasetCommand,
)
from pandaplot.commands.project.dataset.import_csv_command import ImportCsvCommand
from pandaplot.commands.project.folder.create_folder_command import CreateFolderCommand
from pandaplot.commands.project.item.delete_item_command import DeleteItemCommand
from pandaplot.commands.project.note.create_note_command import CreateNoteCommand

# --- Abstract Handler --- #

class ItemTypeHandler(ABC):
    type_name = None
    icon = ""

    def create_tree_item(self, obj) -> QTreeWidgetItem:
        item = QTreeWidgetItem([f"{self.icon} {obj.name}"])
        item.setData(0, Qt.ItemDataRole.UserRole, {
            "type": self.type_name,
            "id": obj.id,
            "data": obj
        })
        return item

    def open(self, panel, obj):
        """Called when item is opened (double-click)."""
        pass

    def context_menu_actions(self, panel, obj) -> list[QAction]:
        return []


# --- Concrete Handlers --- #

class ProjectHandler(ItemTypeHandler):
    type_name = "project"
    icon = "📁"


class FolderHandler(ItemTypeHandler):
    type_name = "folder"
    icon = "📁"

    def context_menu_actions(self, panel, obj):
        return [
            panel.context_menu_manager.action("Add Folder", lambda: panel.add_folder()),
            panel.context_menu_manager.action("Add Note", lambda: panel.add_note()),
            panel.context_menu_manager.action("Delete", lambda: panel.delete_selected_item())
        ]


class NoteHandler(ItemTypeHandler):
    type_name = "note"
    icon = "📝"

    def open(self, panel, obj):
        if panel.app_state:
            panel.app_state.event_bus.emit("ui.note.open_requested", {
                "note_id": obj.id,
                "note_name": obj.name
            })


class DatasetHandler(ItemTypeHandler):
    type_name = "dataset"
    icon = "📊"

    def open(self, panel, obj):
        panel.dataset_open_requested.emit(obj.id, obj.name)

    def context_menu_actions(self, panel, obj):
        return [
            panel.context_menu_manager.action("Create Chart", lambda: panel.create_chart_from_dataset()),
            panel.context_menu_manager.action("Add Column", lambda: panel.add_column_to_dataset()),
            panel.context_menu_manager.action("Add Row", lambda: panel.add_row_to_dataset()),
            panel.context_menu_manager.action("Delete", lambda: panel.delete_selected_item())
        ]


class ChartHandler(ItemTypeHandler):
    type_name = "chart"
    icon = "📈"

    def open(self, panel, obj):
        panel.chart_open_requested.emit(obj.id, obj.name)

    def context_menu_actions(self, panel, obj):
        return [panel.context_menu_manager.action("Delete", lambda: panel.delete_selected_item())]


# --- Context Menu Manager --- #

class ContextMenuManager:
    def __init__(self, app_context, panel:QWidget, command_manager):
        self.app_context = app_context
        self.panel = panel
        self.command_manager = command_manager
        self.handlers = {
            "project": ProjectHandler(),
            "folder": FolderHandler(),
            "note": NoteHandler(),
            "dataset": DatasetHandler(),
            "chart": ChartHandler()
        }

    def show_menu(self, pos, tree):
        item = tree.itemAt(pos)
        if not item:
            return
        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        handler = self.handlers.get(item_data["type"])
        if not handler:
            return

        menu = QMenu(tree)
        for action in handler.context_menu_actions(self.command_manager, item_data["data"]):
            menu.addAction(action)
        menu.exec(tree.mapToGlobal(pos))

    def action(self, label, callback):
        act = QAction(label, self.panel)
        act.triggered.connect(callback)
        return act


# --- Tree Manager --- #

class ProjectTreeManager:
    def __init__(self, app_context, context_menu_manager, parent_panel:QWidget):
        self.app_context = app_context
        self.context_menu_manager = context_menu_manager
        self.parent_panel = parent_panel
        self.logger = logging.getLogger(__name__)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabel("Project Structure")
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.SelectedClicked | QTreeWidget.EditTrigger.EditKeyPressed)

        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(lambda pos: self.context_menu_manager.show_menu(pos, self.tree))

    def update_tree(self, project):
        self.tree.clear()
        root_handler = self.context_menu_manager.handlers["project"]
        root_item = root_handler.create_tree_item(project)
        self.tree.addTopLevelItem(root_item)

        for item in project.root.get_items():
            self._add_item_recursive(item, root_item)

        root_item.setExpanded(True)

    def _add_item_recursive(self, obj, parent_item):
        handler = self.context_menu_manager.handlers.get(obj.type)
        if not handler:
            return
        item = handler.create_tree_item(obj)
        parent_item.addChild(item)
        for child in obj.get_items():
            self._add_item_recursive(child, item)

    def on_item_double_clicked(self, item, column):
        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        if not item_data:
            return
        handler = self.context_menu_manager.handlers.get(item_data["type"])
        if handler:
            handler.open(self.parent_panel, item_data["data"])
    def get_selected_item_info(self):
        """Return {id, type, data} of selected item, or None."""
        current_item = self.tree.currentItem()
        if not current_item:
            return None
        item_data = current_item.data(0, Qt.ItemDataRole.UserRole)
        if not item_data:
            return None
        return {
            "id": item_data.get("id"),
            "type": item_data.get("type"),
            "data": item_data.get("data"),
            "item": current_item
        }

    def get_target_folder_id(self):
        """Return folder ID for creating new items."""
        selected = self.get_selected_item_info()
        if not selected:
            return None
        if selected["type"] == "folder":
            return selected["id"]
        elif selected["type"] == "project":
            return None  # root level
        else:
            obj = selected["data"]
            return obj.parent_id if obj else None

# --- CommandManager --- #
class ProjectPanelCommandManager:
    def __init__(self, app_context, tree_manager: ProjectTreeManager, panel: QWidget):
        self.logger = logging.getLogger(__name__)
        self.app_context = app_context
        self.tree_manager = tree_manager
        self.executor = app_context.get_command_executor()
        self.panel = panel

    def add_folder(self):
        """Add a new folder."""
        if not self.app_context.app_state.has_project:
            return

        folder_id = self.tree_manager.get_target_folder_id()

        command = CreateFolderCommand(self.app_context, parent_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)

    def add_note(self):
        """Add a new note."""
        if not self.app_context.app_state.has_project:
            return

        folder_id = self.tree_manager.get_target_folder_id()

        command = CreateNoteCommand(self.app_context, folder_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)

    def import_csv(self):
        """Import a CSV file as a dataset."""
        if not self.app_context.app_state.has_project:
            return

        folder_id = self.tree_manager.get_target_folder_id()

        command = ImportCsvCommand(self.app_context, folder_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)

    def create_empty_dataset(self):
        """Create a new empty dataset."""
        if not self.app_context.app_state.has_project:
            return

        folder_id = self.tree_manager.get_target_folder_id()

        command = CreateEmptyDatasetCommand(
            self.app_context, folder_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)

    def create_chart_from_dataset(self):
        """Create a chart from the selected dataset."""
        selected_item = self.tree_manager.get_selected_item_info()
        if not selected_item:
            return

        # Get dataset information
        item_data = selected_item["data"](0, Qt.ItemDataRole.UserRole)
        if not item_data or item_data.get('type') != 'dataset':
            return

        dataset_id = item_data.get('id')
        dataset_obj = item_data.get('data')
        dataset_name = dataset_obj.name if dataset_obj else 'Dataset'

        if dataset_id:
            # Signal to create a new chart tab with this dataset
            self.panel.chart_create_requested.emit(
                dataset_id, f"Chart from {dataset_name}")
            self.logger.debug(
                f"Requesting chart creation for dataset '{dataset_id}'")

    def rename_selected_item(self):
        """Rename the selected item by starting inline editing."""
        selected_info = self.tree_manager.get_selected_item_info()
        if not selected_info or selected_info['type'] == 'project':
            return

        # Start inline editing on the current item
        current_item = selected_info['item']
        if current_item:
            # Start editing the first column
            self.tree_manager.tree.editItem(current_item, 0)

    def delete_selected_item(self):
        """Delete the selected item."""
        selected_info = self.tree_manager.get_selected_item_info()
        if not selected_info or selected_info['type'] == 'project':
            return

        item_id = selected_info['id']
        item_obj = selected_info['data']
        item_name = item_obj.name if item_obj else 'Unnamed Item'

        reply = QMessageBox.question(
            self.panel,
            "Confirm Delete",
            f"Are you sure you want to delete '{item_name}' and all its contents?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            command = DeleteItemCommand(self.app_context, item_id)
            self.app_context.get_command_executor().execute_command(command)

    
    def add_column_to_dataset(self):
        """Add a new column to the selected dataset."""
        selected_info = self.tree_manager.get_selected_item_info()
        if not selected_info or selected_info['type'] != 'dataset':
            return

        dataset_id = selected_info['id']

        command = AddColumnCommand(self.app_context, dataset_id)
        success = self.app_context.get_command_executor().execute_command(command)

        if success:
            self.logger.info(f"Added column to dataset {dataset_id}")
        else:
            self.logger.warning(
                f"Failed to add column to dataset {dataset_id}")

    def add_row_to_dataset(self):
        """Add a new row to the selected dataset."""
        selected_info = self.tree_manager.get_selected_item_info()
        if not selected_info or selected_info['type'] != 'dataset':
            return

        dataset_id = selected_info['id']

        command = AddRowCommand(self.app_context, dataset_id)
        success = self.app_context.get_command_executor().execute_command(command)

        if success:
            self.logger.info(f"Added row to dataset {dataset_id}")
        else:
            self.logger.warning(f"Failed to add row to dataset {dataset_id}")


# --- Main Panel --- #

class ProjectViewPanel(QWidget):
    dataset_open_requested = Signal(str, str)
    chart_open_requested = Signal(str, str)
    chart_create_requested = Signal(str, str)
    plot_tab_requested = Signal() 

    def __init__(self, app_context, parent=None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        self.app_context = app_context
        self.app_state = app_context.get_app_state()

        layout = QVBoxLayout(self)

        # Project label area
        self.project_label = QLabel("Project View")
        layout.addWidget(self.project_label)

        # Managers
        self.context_menu_manager = ContextMenuManager(app_context, self, self.command_manager)
        self.tree_manager = ProjectTreeManager(app_context, self.context_menu_manager, self)
        self.command_manager = ProjectPanelCommandManager(app_context, self.tree_manager, self)

        layout.addWidget(self.tree_manager.tree)

