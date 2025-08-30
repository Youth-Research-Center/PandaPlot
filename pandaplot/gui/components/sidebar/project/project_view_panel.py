import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
    QLabel,
    QLayout,
    QTreeWidget,
    QVBoxLayout,
    QWidget,
)

from pandaplot.commands.project.item import RenameItemCommand
from pandaplot.gui.components.sidebar.project.item_name_delegate import ItemNameDelegate
from pandaplot.gui.components.sidebar.project.project_command_manager import ProjectPanelCommandManager
from pandaplot.gui.components.sidebar.project.project_context_manager import ProjectViewPanelContextManager
from pandaplot.gui.components.sidebar.project.project_tree import ProjectTreeWidget
from pandaplot.gui.components.sidebar.project.project_tree_manager import ProjectTreeManager
from pandaplot.models.events.event_types import DatasetOperationEvents, ProjectEvents
from pandaplot.models.state.app_context import AppContext


class ProjectViewPanel(QWidget):
    """
    UI component that displays project information and listens to app state changes.
    This follows the MVC pattern by listening to events from the app state.
    """

    def __init__(self, app_context: AppContext, parent=None, **kwargs):
        super().__init__(parent)
        self.app_context = app_context
        self.app_state = app_context.get_app_state()
        self.logger = logging.getLogger(__name__)

        # TODO: ideally we shouldn't reference the project tree manager before it's initialized
        # TODO: ideally we shouldn't reference the tree directly
        self.command_manager = ProjectPanelCommandManager(app_context,
                                                          lambda: self.project_tree_manager.get_target_folder_id(),
                                                          lambda: self.tree.currentItem(),
                                                          lambda: self.project_tree_manager.get_selected_item_info(),
                                                          lambda item, position: self.tree.editItem(
                                                              item, position)
                                                          )

        self.setStyleSheet("background-color: #ffffff; color: black;")

        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Create a label to display the project name
        self.project_label = QLabel("Project View")
        self.project_label.setStyleSheet(
            "background-color: #DCDCDC; color: black; padding: 10px;")
        layout.addWidget(self.project_label)

        self.create_treeview(layout)
        self.subscribe_to_events()

    def subscribe_to_events(self):
        """Subscribe to relevant app state events."""
        if self.app_state:
            self.app_state.event_bus.subscribe(
                ProjectEvents.PROJECT_LOADED, self.on_project_loaded)
            self.app_state.event_bus.subscribe(
                ProjectEvents.PROJECT_CLOSED, self.on_project_closed)
            self.app_state.event_bus.subscribe(
                ProjectEvents.PROJECT_CHANGED, self.on_item_changed)
            self.app_state.event_bus.subscribe(
                ProjectEvents.PROJECT_CREATED, self.on_item_changed)


    def create_treeview(self, layout: QLayout):
        """Create the treeview widget."""
        # Create project title display
        self.title_frame = QGroupBox("Project Info")
        self.title_frame.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 9pt;
                color: black;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        layout.addWidget(self.title_frame)

        title_layout = QVBoxLayout(self.title_frame)
        title_layout.setContentsMargins(10, 15, 10, 10)

        self.project_title_label = QLabel("No project loaded")
        self.project_title_label.setStyleSheet(
            "font-weight: bold; font-size: 9pt; color: black; margin-top: 5px;")
        title_layout.addWidget(self.project_title_label)

        self.project_file_label = QLabel("File label will appear here")
        self.project_file_label.setStyleSheet("font-size: 8pt; color: gray;")
        title_layout.addWidget(self.project_file_label)

        # Create treeview
        self.tree = ProjectTreeWidget(self)
        self.tree.setStyleSheet("""
            QTreeWidget { 
                color: black; 
                selection-background-color: #0078d4;
                selection-color: white;
            }
            QTreeWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
            QTreeWidget::item:hover {
                background-color: #e5f3ff;
            }
        """)
        self.tree.setHeaderLabel('Project Structure')

        # Enable context menu and interactions
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(
            lambda pos: self.context_menu.show_context_menu(pos))
        self.tree.itemDoubleClicked.connect(
            self.command_manager.on_item_double_clicked)

        # Enable inline editing for item names
        self.tree.setEditTriggers(
            QTreeWidget.EditTrigger.SelectedClicked | QTreeWidget.EditTrigger.EditKeyPressed)
        self.tree.itemChanged.connect(self.on_item_name_changed)

        # Set custom delegate to handle editing only the name portion
        self.item_delegate = ItemNameDelegate(self.tree)
        self.tree.setItemDelegate(self.item_delegate)

        # Add a flag to prevent recursive updates during editing
        self._editing_in_progress = False

        # Enable drag and drop
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tree.setDefaultDropAction(Qt.DropAction.MoveAction)

        layout.addWidget(self.tree)

        self.project_tree_manager = ProjectTreeManager(
            self.app_context, self.tree, self.on_item_name_changed)

        # Initially show placeholder content
        self.project_tree_manager.show_no_project_content()

        # Create context menu
        self.create_context_menu()

    def on_project_loaded(self, event_data):
        """Handle project loaded event."""
        project = event_data.get('project')
        file_path = event_data.get('file_path')

        self.logger.info(f"Project loaded - {project.name}")

        # Update project info display
        self.project_title_label.setText(project.name)
        if file_path:
            self.project_file_label.setText(f"File: {file_path}")
        else:
            self.project_file_label.setText("Unsaved project")

        # Update tree view with project contents
        self.project_tree_manager.update_project_tree(project)

    def on_project_closed(self, event_data):
        """Handle project closed event."""
        self.logger.info("Project closed")

        # Reset to no project state
        self.project_title_label.setText("No project loaded")
        self.project_file_label.setText("File label will appear here")
        self.project_tree_manager.show_no_project_content()

    def on_item_changed(self, event_data):
        """Handle item creation/modification/deletion events by refreshing the tree."""
        if self.app_state.has_project:
            project = self.app_state.current_project
            if project:
                self.project_tree_manager.update_project_tree(project)

    def create_context_menu(self):
        """Create the right-click context menu."""
        self.context_menu = ProjectViewPanelContextManager(
            self, self.app_context,  self.command_manager, self.tree.itemAt, self.tree.mapToGlobal)

    def on_item_name_changed(self, item, column):
        """Handle when an item name is changed through inline editing."""
        if column != 0:  # Only handle name column changes
            return

        # Prevent recursive updates
        if getattr(self, '_editing_in_progress', False):
            return

        # Prevent rename operations during drag and drop
        if hasattr(self.tree, '_is_dragging') and self.tree._is_dragging:
            self.logger.debug("Skipping rename during drag operation")
            return

        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        if not item_data:
            return

        item_type = item_data.get('type', '')
        item_id = item_data.get('id', '')

        # Skip project root
        if item_type == 'project':
            return

        # Extract new name from the item text (remove emoji prefix)
        new_text = item.text(0)
        if new_text.startswith('📁 '):
            new_name = new_text[2:].strip()
        elif new_text.startswith('📝 '):
            new_name = new_text[2:].strip()
        elif new_text.startswith('📊 '):
            new_name = new_text[2:].strip()
        elif new_text.startswith('📈 '):
            new_name = new_text[2:].strip()
        else:
            new_name = new_text.strip()

        # Get current name from data
        item_obj = item_data.get('data')
        current_name = item_obj.name if item_obj else ''

        # Only process if name actually changed
        if new_name and new_name != current_name and new_name.strip():
            self.logger.debug(
                f"Item name changed: {current_name} -> {new_name} (type: {item_type}, id: {item_id})")

            # Set flag to prevent recursive updates
            self._editing_in_progress = True

            try:
                # Execute appropriate rename command based on item type
                command = RenameItemCommand(
                    self.app_context, item_id, new_name)
                self.app_context.get_command_executor().execute_command(command)
            finally:
                self._editing_in_progress = False
        else:
            # Revert to original name if invalid
            prefix = '📁 ' if item_type == 'folder' else '📝 ' if item_type == 'note' else '📊 ' if item_type == 'dataset' else '📈 '
            item.setText(0, f"{prefix}{current_name}")

    def update_project_display(self):
        """Update the display based on current app state."""
        if self.app_state and self.app_state.has_project:
            project = self.app_state.current_project
            file_path = self.app_state.project_file_path

            if project:
                self.project_title_label.setText(project.name)
                if file_path:
                    self.project_file_label.setText(f"File: {file_path}")
                else:
                    self.project_file_label.setText("Unsaved project")

                self.project_tree_manager.update_project_tree(project)
        else:
            self.project_title_label.setText("No project loaded")
            self.project_file_label.setText("File label will appear here")
            self.project_tree_manager.show_no_project_content()
