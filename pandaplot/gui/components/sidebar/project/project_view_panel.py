from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QGroupBox, QTreeWidget, 
                             QTreeWidgetItem, QMenu, QMessageBox, QStyledItemDelegate, QLineEdit, 
                             QAbstractItemView)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.commands.project.folder.create_folder_command import CreateFolderCommand
from pandaplot.commands.project.note.create_note_command import CreateNoteCommand
from pandaplot.commands.project.dataset.import_csv_command import ImportCsvCommand
from pandaplot.commands.project.dataset.create_empty_dataset_command import CreateEmptyDatasetCommand
from pandaplot.commands.project.dataset.add_column_command import AddColumnCommand
from pandaplot.commands.project.dataset.add_row_command import AddRowCommand
from pandaplot.commands.project.item.delete_item_command import DeleteItemCommand
from pandaplot.commands.project.item.move_item_command import MoveItemCommand
from pandaplot.commands.project.item.rename_item_command import RenameItemCommand
from pandaplot.commands.project.folder.rename_folder_command import RenameFolderCommand
from pandaplot.models.project.visitors import ProjectTreeBuilder
import logging

class ProjectTreeWidget(QTreeWidget):
    """Custom tree widget that handles drag and drop properly."""
    
    def __init__(self, parent_panel):
        super().__init__()
        self.parent_panel = parent_panel
        self.logger = logging.getLogger(__name__)
        
        # Enable drag and drop
        self.setDragDropMode(QTreeWidget.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        
        # Track highlighted item for drag feedback
        self.highlighted_item = None
        
        # Store original background colors for restoring
        self.original_backgrounds = {}
        
        # Track drag state to prevent unwanted rename operations
        self._is_dragging = False
    
    def startDrag(self, supportedActions):
        """Override to track drag start."""
        self._is_dragging = True
        super().startDrag(supportedActions)
    
    def dropEvent(self, event):
        """Handle drop events to persist item moves."""
        # Clear any highlighting first
        self._clear_highlight()
        
        if not self.parent_panel.app_state.has_project:
            event.ignore()
            return
            
        # Get the source item being dragged
        source_item = self.currentItem()
        if not source_item:
            event.ignore()
            return
            
        # Get source item data
        source_data = source_item.data(0, Qt.ItemDataRole.UserRole)
        if not source_data:
            event.ignore()
            return
            
        source_type = source_data.get('type', '')
        source_id = source_data.get('id', '')
        
        # Don't allow moving the project root
        if source_type == 'project':
            event.ignore()
            return
            
        # Get the target item and position
        target_item = self.itemAt(event.position().toPoint())
        
        # Determine new parent folder ID
        new_parent_id = 'root'  # Default to project root
        
        if target_item:
            target_data = target_item.data(0, Qt.ItemDataRole.UserRole)
            if target_data:
                target_type = target_data.get('type', '')
                
                # If dropping on a folder, make it the parent
                if target_type == 'folder':
                    new_parent_id = target_data.get('id', 'root')
                    self.logger.debug("ProjectTreeWidget: dropping on folder new_parent_id=%s", new_parent_id)
                # If dropping on another item, use its parent folder
                elif target_type in ['note', 'dataset', 'chart']:
                    target_item_obj = target_data.get('data')
                    if target_item_obj and target_item_obj.parent_id:
                        # Check if the parent_id is the root collection ID
                        project = self.parent_panel.app_state.current_project
                        if project and target_item_obj.parent_id == project.root.id:
                            new_parent_id = 'root'
                            self.logger.debug("ProjectTreeWidget: target item parent is root; new_parent_id=root")
                        else:
                            new_parent_id = target_item_obj.parent_id
                            self.logger.debug("ProjectTreeWidget: target item parent set to %s", new_parent_id)
                    else:
                        new_parent_id = 'root'
                        self.logger.debug("ProjectTreeWidget: target item has no parent; new_parent_id=root")
                # If dropping on project root, use root
                elif target_type == 'project':
                    new_parent_id = 'root'
        
        # Get current parent folder ID
        current_item_obj = source_data.get('data')
        if current_item_obj:
            # Check if the parent_id is the root collection ID
            project = self.parent_panel.app_state.current_project
            if project and current_item_obj.parent_id == project.root.id:
                current_parent_id = 'root'
                self.logger.debug("ProjectTreeWidget: current item parent is root")
            else:
                current_parent_id = current_item_obj.parent_id if current_item_obj.parent_id else 'root'
                self.logger.debug("ProjectTreeWidget: current item parent is %s", current_parent_id)
        else:
            current_parent_id = 'root'
            self.logger.debug("ProjectTreeWidget: no current item data; current_parent_id=root")
        
        # Only execute move if parent actually changed
        if new_parent_id != current_parent_id:
            self.logger.info("ProjectTreeWidget: moving %s %s from %s to %s", source_type, source_id, current_parent_id, new_parent_id)
            
            # Execute the move command
            command = MoveItemCommand(
                self.parent_panel.app_context,
                item_id=source_id,
                item_type=source_type,
                source_folder_id=current_parent_id,
                target_folder_id=new_parent_id
            )
            self.parent_panel.app_context.get_command_executor().execute_command(command)
            
            # Accept the event
            event.accept()
        else:
            # No change needed, but allow the visual move
            super().dropEvent(event)
        
        # Clear drag state after drop
        self._is_dragging = False
        
        # Also set a timer to clear drag state in case events are out of order
        QTimer.singleShot(100, lambda: setattr(self, '_is_dragging', False))
    
    def dragMoveEvent(self, event):
        """Handle drag move events with visual feedback."""
        try:
            # Get the item under the cursor
            target_item = self.itemAt(event.position().toPoint())
            
            # Clear previous highlighting
            self._clear_highlight()
            
            # Highlight the target item if it's a valid drop target
            if target_item:
                try:
                    target_data = target_item.data(0, Qt.ItemDataRole.UserRole)
                    if target_data:
                        target_type = target_data.get('type', '')
                        target_id = target_data.get('id', '')
                        
                        self.logger.debug("ProjectTreeWidget: drag over item %s %s", target_type, target_id)
                        
                        # Valid drop targets: folders (drop into), project root, or any item (to drop beside it)
                        if target_type in ['folder', 'project', 'note', 'dataset', 'chart']:
                            # Only highlight folders and project root for "drop into" operations
                            # For other items, provide subtle feedback since it's a "drop beside" operation
                            if target_type in ['folder', 'project']:
                                self._highlight_item(target_item)
                                if target_type == 'folder':
                                    self.setToolTip("Drop into folder")
                                else:
                                    self.setToolTip("Drop at project root")
                            else:
                                # For notes/datasets/charts, don't highlight them as they're not containers
                                # But still accept the drag to allow "drop beside" operations
                                self.setToolTip("Drop beside this item")
                            
                            event.accept()
                        else:
                            self.setToolTip("")
                            event.ignore()
                    else:
                        self.setToolTip("")
                        event.ignore()
                except RuntimeError:
                    # Target item has been deleted by Qt, ignore this drag event
                    self.setToolTip("")
                    event.ignore()
            else:
                # If no target item, accept to allow drop in empty space (project root)
                self.setToolTip("Drop at project root")
                event.accept()
        except Exception:
            # General exception handling to prevent crashes during drag operations
            self.setToolTip("")
            event.ignore()
    
    def _highlight_item(self, item):
        """Highlight an item to show it's a valid drop target."""
        if item is None or item == self.highlighted_item:
            return
            
        try:
            # Clear any previous highlight
            self._clear_highlight()
            
            # Check if the item is still valid (not deleted by Qt)
            try:
                item_data = item.data(0, Qt.ItemDataRole.UserRole)
                self.logger.debug("ProjectTreeWidget: highlighting %s %s", item_data.get('type', 'unknown'), item_data.get('id', 'no-id'))
            except RuntimeError:
                # Item has been deleted by Qt, skip highlighting
                self.logger.debug("ProjectTreeWidget: skipping highlight - item deleted by Qt")
                return
            
            # Store original background
            original_bg = item.background(0)
            self.original_backgrounds[item] = original_bg
            
            # Determine highlight color based on item type
            target_data = item.data(0, Qt.ItemDataRole.UserRole)
            target_type = target_data.get('type', '') if target_data else ''
            
            from PySide6.QtGui import QColor
            
            if target_type == 'folder':
                # Green for folders (items will be moved INTO the folder)
                highlight_color = QColor(144, 238, 144, 120)  # Light green
            elif target_type == 'project':
                # Blue for project root (items will be moved to root level)
                highlight_color = QColor(173, 216, 230, 120)  # Light blue
            else:
                # Yellow for other items (items will be moved to same level)
                highlight_color = QColor(255, 255, 224, 120)  # Light yellow
            
            # Set background directly with QColor (PySide6 accepts this)
            item.setBackground(0, highlight_color)
            self.highlighted_item = item
            
        except RuntimeError:
            # Handle case where any Qt object has been deleted during the operation
            pass
    
    def _clear_highlight(self):
        """Clear any existing highlight."""
        if self.highlighted_item:
            try:
                # Restore original background
                if self.highlighted_item in self.original_backgrounds:
                    self.highlighted_item.setBackground(0, self.original_backgrounds[self.highlighted_item])
                    del self.original_backgrounds[self.highlighted_item]
            except RuntimeError:
                # Item has been deleted by Qt, just remove it from our tracking
                if self.highlighted_item in self.original_backgrounds:
                    del self.original_backgrounds[self.highlighted_item]
            
            self.highlighted_item = None
        
        # Clear tooltip
        self.setToolTip("")
    
    def dragEnterEvent(self, event):
        """Handle drag enter events."""
        if event.source() == self:
            event.accept()
        else:
            event.ignore()
    
    def dragLeaveEvent(self, event):
        """Handle drag leave events."""
        # Clear highlighting when drag leaves the widget
        self._clear_highlight()
        super().dragLeaveEvent(event)


class ItemNameDelegate(QStyledItemDelegate):
    """Custom delegate to handle editing only the name portion of tree items, not the icon."""
    
    def createEditor(self, parent, option, index):
        """Create editor that only shows the name part."""
        editor = QLineEdit(parent)
        
        # Get the full text and extract just the name part
        full_text = index.data(Qt.ItemDataRole.DisplayRole)
        if isinstance(full_text, str):
            # Remove emoji prefix
            if full_text.startswith('📁 '):
                name_only = full_text[2:].strip()
            elif full_text.startswith('📝 '):
                name_only = full_text[2:].strip()
            elif full_text.startswith('📊 '):
                name_only = full_text[2:].strip()
            elif full_text.startswith('📈 '):
                name_only = full_text[2:].strip()
            else:
                name_only = full_text.strip()
            
            editor.setText(name_only)
            editor.selectAll()
        
        return editor
    
    def setEditorData(self, editor, index):
        """Set the editor data to just the name portion."""
        # This is handled in createEditor
        pass
    
    def setModelData(self, editor, model, index):
        """Set the model data with the icon prefix preserved."""
        new_name = editor.text().strip()
        if new_name:
            # Get the current full text to determine the icon
            full_text = index.data(Qt.ItemDataRole.DisplayRole)
            if isinstance(full_text, str):
                # Preserve the emoji prefix
                if full_text.startswith('📁 '):
                    new_full_text = f"📁 {new_name}"
                elif full_text.startswith('📝 '):
                    new_full_text = f"📝 {new_name}"
                elif full_text.startswith('📊 '):
                    new_full_text = f"📊 {new_name}"
                elif full_text.startswith('📈 '):
                    new_full_text = f"📈 {new_name}"
                else:
                    new_full_text = new_name
                
                model.setData(index, new_full_text, Qt.ItemDataRole.DisplayRole)


class ProjectViewPanel(QWidget):
    """
    UI component that displays project information and listens to app state changes.
    This follows the MVC pattern by listening to events from the app state.
    """
    
    # Signals emitted when items should be opened in tabs
    note_open_requested = Signal(str, str)  # note_id, note_name
    dataset_open_requested = Signal(str, str)  # dataset_id, dataset_name
    chart_open_requested = Signal(str, str)  # chart_id, chart_name
    chart_create_requested = Signal(str, str)  # dataset_id, chart_name
    plot_tab_requested = Signal()  # Request to open a new plot tab
    
    def __init__(self, app_context: AppContext, parent=None, **kwargs):
        super().__init__(parent)
        self.app_context = app_context
        self.app_state = app_context.get_app_state()
        self.logger = logging.getLogger(__name__)
        self.setStyleSheet("background-color: #ffffff; color: black;")
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Create a label to display the project name
        self.project_label = QLabel("Project View")
        self.project_label.setStyleSheet("background-color: #DCDCDC; color: black; padding: 10px;")
        layout.addWidget(self.project_label)
        
        self.create_treeview(layout)
        
        # Subscribe to app state events if app_state is provided
        if self.app_state:
            self.subscribe_to_events()
        
    def set_app_state(self, app_state: AppState):
        """Set the app state and subscribe to events."""
        self.app_state = app_state
        self.subscribe_to_events()
        self.update_project_display()
        
    def subscribe_to_events(self):
        """Subscribe to relevant app state events."""
        if self.app_state:
            self.app_state.event_bus.subscribe('project_loaded', self.on_project_loaded)
            self.app_state.event_bus.subscribe('project_closed', self.on_project_closed)
            self.app_state.event_bus.subscribe('first_project_loaded', self.on_first_project_loaded)
            
            # Subscribe to item events for automatic tree updates
            self.app_state.event_bus.subscribe('folder_created', self.on_item_changed)
            self.app_state.event_bus.subscribe('folder_renamed', self.on_item_changed)
            self.app_state.event_bus.subscribe('folder_deleted', self.on_item_changed)
            self.app_state.event_bus.subscribe('note_created', self.on_item_changed)
            self.app_state.event_bus.subscribe('note_renamed', self.on_item_changed)
            self.app_state.event_bus.subscribe('note_deleted', self.on_item_changed)
            self.app_state.event_bus.subscribe('dataset_created', self.on_item_changed)
            self.app_state.event_bus.subscribe('dataset_imported', self.on_item_changed)
            self.app_state.event_bus.subscribe('dataset_removed', self.on_item_changed)
            self.app_state.event_bus.subscribe('dataset_column_added', self.on_item_changed)
            self.app_state.event_bus.subscribe('dataset_column_removed', self.on_item_changed)
            self.app_state.event_bus.subscribe('dataset_row_added', self.on_item_changed)
            self.app_state.event_bus.subscribe('dataset_row_removed', self.on_item_changed)
            self.app_state.event_bus.subscribe('item_moved', self.on_item_changed)
            
            # Subscribe to chart events
            self.app_state.event_bus.subscribe('chart.created', self.on_item_changed)
            self.app_state.event_bus.subscribe('chart.updated', self.on_item_changed)
            self.app_state.event_bus.subscribe('chart.deleted', self.on_item_changed)

    def create_treeview(self, layout):
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
        self.project_title_label.setStyleSheet("font-weight: bold; font-size: 9pt; color: black; margin-top: 5px;")
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
        self.tree.customContextMenuRequested.connect(self.show_context_menu)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)
        
        # Enable inline editing for item names
        self.tree.setEditTriggers(QTreeWidget.EditTrigger.SelectedClicked | QTreeWidget.EditTrigger.EditKeyPressed)
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

        # Initially show placeholder content
        self.show_no_project_content()
        
        # Create context menu
        self.create_context_menu()
        
    def show_no_project_content(self):
        """Show placeholder content when no project is loaded."""
        self.tree.clear()
        placeholder_item = QTreeWidgetItem(["No project loaded"])
        placeholder_item.setToolTip(0, "Load a project to see its structure here")
        self.tree.addTopLevelItem(placeholder_item)
        
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
        self.update_project_tree(project)
        
    def on_project_closed(self, event_data):
        """Handle project closed event."""
        self.logger.info("Project closed")
        
        # Reset to no project state
        self.project_title_label.setText("No project loaded")
        self.project_file_label.setText("File label will appear here")
        self.show_no_project_content()
        
    def on_first_project_loaded(self, event_data):
        """Handle first project loaded event."""
        project = event_data.get('project')
        self.logger.info(f"First project loaded - {project.name}")
        # Could add special handling for first project load (e.g., welcome message)
    
    def on_item_changed(self, event_data):
        """Handle item creation/modification/deletion events by refreshing the tree."""
        if self.app_state.has_project:
            project = self.app_state.current_project
            if project:
                self.update_project_tree(project)
        
    def update_project_tree(self, project):
        """Update the tree view with project contents using hierarchical metadata structure."""
        # Save expanded state of folders before rebuilding
        expanded_folders = self._get_expanded_folders()
        
        # Temporarily disconnect itemChanged signal to prevent spurious rename commands
        self.tree.itemChanged.disconnect(self.on_item_name_changed)
        
        try:
            self.tree.clear()
            
            # Project root item
            root_item = QTreeWidgetItem([f"📁 {project.name}"])
            root_item.setToolTip(0, f"Project: {project.description}")
            root_item.setData(0, Qt.ItemDataRole.UserRole, {'type': 'project', 'id': 'root'})
            
            # Make project root non-editable
            root_item.setFlags(root_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            
            self.tree.addTopLevelItem(root_item)
                
            self._build_tree_from_project(project, root_item)
        finally:
            # Reconnect the itemChanged signal
            self.tree.itemChanged.connect(self.on_item_name_changed)
        
        # Expand the root item
        root_item.setExpanded(True)
        
        # Restore expanded state of folders
        self._restore_expanded_folders(expanded_folders)
    
    def _build_tree_from_project(self, project, root_item):
        """Build tree structure from project using visitor pattern."""
        # Create a factory for QTreeWidgetItem creation
        def create_tree_item(display_text: str, item_type: str, item_data: dict) -> QTreeWidgetItem:
            """Factory function to create QTreeWidgetItem instances."""
            tree_item = QTreeWidgetItem([display_text])
            tree_item.setData(0, Qt.ItemDataRole.UserRole, item_data)
            
            # Set item flags based on type
            if item_type == 'project':
                # Project root is not editable
                tree_item.setFlags(tree_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            else:
                # Other items are editable
                tree_item.setFlags(tree_item.flags() | Qt.ItemFlag.ItemIsEditable)
            
            return tree_item
        
        # Create the visitor with our tree item factory
        tree_builder = ProjectTreeBuilder(create_tree_item)
        
        # Use the visitor to build the tree structure
        # We pass root_item as the parent context so items are added to it
        for item in project.root.get_items():
            tree_item = tree_builder.visit(item, root_item)
            root_item.addChild(tree_item)
    
    def _get_expanded_folders(self):
        """Get a set of IDs for currently expanded folders."""
        expanded = set()
        
        def check_item(item):
            if item.isExpanded():
                item_data = item.data(0, Qt.ItemDataRole.UserRole)
                if item_data and item_data.get('type') in ['project', 'folder']:
                    expanded.add(item_data.get('id', ''))
            
            # Check children
            for i in range(item.childCount()):
                check_item(item.child(i))
        
        # Start from root items
        for i in range(self.tree.topLevelItemCount()):
            check_item(self.tree.topLevelItem(i))
        
        return expanded
    
    def _restore_expanded_folders(self, expanded_folders):
        """Restore the expanded state of folders."""
        def expand_item(item):
            item_data = item.data(0, Qt.ItemDataRole.UserRole)
            if item_data and item_data.get('id') in expanded_folders:
                item.setExpanded(True)
            
            # Check children
            for i in range(item.childCount()):
                expand_item(item.child(i))
        
        # Start from root items
        for i in range(self.tree.topLevelItemCount()):
            expand_item(self.tree.topLevelItem(i))
    
    
    def create_context_menu(self):
        """Create the right-click context menu."""
        self.context_menu = QMenu(self)
        self.context_menu.setStyleSheet("""
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
        self.open_action.triggered.connect(self.open_selected_item)
        self.context_menu.addAction(self.open_action)
        
        self.context_menu.addSeparator()
        
        # Rename action
        self.rename_action = QAction("Rename", self)
        self.rename_action.triggered.connect(self.rename_selected_item)
        self.context_menu.addAction(self.rename_action)
        
        self.context_menu.addSeparator()
        
        # Add actions
        self.add_folder_action = QAction("Add Folder", self)
        self.add_folder_action.triggered.connect(self.add_folder)
        self.context_menu.addAction(self.add_folder_action)
        
        self.add_note_action = QAction("Add Note", self)
        self.add_note_action.triggered.connect(self.add_note)
        self.context_menu.addAction(self.add_note_action)
        
        self.import_csv_action = QAction("Import CSV...", self)
        self.import_csv_action.triggered.connect(self.import_csv)
        self.context_menu.addAction(self.import_csv_action)
        
        self.create_empty_dataset_action = QAction("Create Empty Dataset", self)
        self.create_empty_dataset_action.triggered.connect(self.create_empty_dataset)
        self.context_menu.addAction(self.create_empty_dataset_action)
        
        # Chart creation action (for datasets)
        self.create_chart_action = QAction("Create Chart", self)
        self.create_chart_action.triggered.connect(self.create_chart_from_dataset)
        self.context_menu.addAction(self.create_chart_action)
        
        self.context_menu.addSeparator()
        
        # Dataset manipulation actions (for datasets)
        self.add_column_action = QAction("Add Column", self)
        self.add_column_action.triggered.connect(self.add_column_to_dataset)
        self.context_menu.addAction(self.add_column_action)
        
        self.add_row_action = QAction("Add Row", self)
        self.add_row_action.triggered.connect(self.add_row_to_dataset)
        self.context_menu.addAction(self.add_row_action)
        
        self.context_menu.addSeparator()
        
        # Delete action
        self.delete_action = QAction("Delete", self)
        self.delete_action.triggered.connect(self.delete_selected_item)
        self.context_menu.addAction(self.delete_action)
    
    def show_context_menu(self, position):
        """Show context menu at the given position."""
        if not self.app_state.has_project:
            return
            
        item = self.tree.itemAt(position)
        if item:
            # Enable/disable actions based on item type
            item_data = item.data(0, Qt.ItemDataRole.UserRole)
            if item_data:
                item_type = item_data.get('type', '')
                
                # Disable rename and delete for project root
                can_rename = item_type != 'project'
                can_delete = item_type != 'project'
                
                # Show chart creation only for datasets
                self.create_chart_action.setVisible(item_type == 'dataset')
                
                # Show dataset manipulation actions only for datasets
                self.add_column_action.setVisible(item_type == 'dataset')
                self.add_row_action.setVisible(item_type == 'dataset')
                
                self.rename_action.setEnabled(can_rename)
                self.delete_action.setEnabled(can_delete)
            
            self.context_menu.exec(self.tree.mapToGlobal(position))
    
    def on_item_double_clicked(self, item, column):
        """Handle double-click on tree item."""
        item_data = item.data(0, Qt.ItemDataRole.UserRole)
        if item_data:
            item_type = item_data.get('type', '')
            
            # For folders, toggle expansion
            if item_type == 'folder':
                item.setExpanded(not item.isExpanded())
            # For other items that can be opened, don't start editing
            elif item_type in ['note', 'dataset', 'chart']:
                self.open_selected_item()
                return
        
        # For project root or items without actions, do nothing
        # Inline editing is triggered by single click when item is selected
    
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
            self.logger.debug(f"Item name changed: {current_name} -> {new_name} (type: {item_type}, id: {item_id})")
            
            # Set flag to prevent recursive updates
            self._editing_in_progress = True
            
            try:
                # Execute appropriate rename command based on item type
                if item_type == 'folder':
                    command = RenameFolderCommand(self.app_context, item_id, new_name)
                    self.app_context.get_command_executor().execute_command(command)
                elif item_type == 'note':
                    command = RenameItemCommand(self.app_context, item_id, new_name)
                    self.app_context.get_command_executor().execute_command(command)
                else:
                    # TODO: Add rename commands for datasets and charts
                    self.logger.debug(f"Inline rename not yet implemented for {item_type}")
                    # Revert the name change in the UI
                    old_prefix = '📊 ' if item_type == 'dataset' else '📈 '
                    item.setText(0, f"{old_prefix}{current_name}")
            finally:
                self._editing_in_progress = False
        else:
            # Revert to original name if invalid
            prefix = '📁 ' if item_type == 'folder' else '📝 ' if item_type == 'note' else '📊 ' if item_type == 'dataset' else '📈 '
            item.setText(0, f"{prefix}{current_name}")
    
    def open_selected_item(self):
        """Open the selected item."""
        current_item = self.tree.currentItem()
        if not current_item:
            return
            
        item_data = current_item.data(0, Qt.ItemDataRole.UserRole)
        if not item_data:
            return
            
        item_type = item_data.get('type', '')
        item_id = item_data.get('id', '')
        
        # Handle different item types
        if item_type == 'folder':
            # Toggle folder expansion
            current_item.setExpanded(not current_item.isExpanded())
        elif item_type == 'note':
            # Open note in a tab
            note_obj = item_data.get('data')
            note_name = note_obj.name if note_obj else 'Unnamed Note'
            self.note_open_requested.emit(item_id, note_name)
        elif item_type == 'dataset':
            # Open dataset in a tab (could show data table view)
            dataset_obj = item_data.get('data')
            dataset_name = dataset_obj.name if dataset_obj else 'Unnamed Dataset'
            self.dataset_open_requested.emit(item_id, dataset_name)
        elif item_type == 'chart':
            # Open chart in a tab (could show chart configuration/preview)
            chart_obj = item_data.get('data')
            chart_name = chart_obj.name if chart_obj else 'Unnamed Chart'
            self.chart_open_requested.emit(item_id, chart_name)
    
    def get_selected_item_info(self):
        """Get information about the currently selected item."""
        current_item = self.tree.currentItem()
        if not current_item:
            return None
            
        item_data = current_item.data(0, Qt.ItemDataRole.UserRole)
        if not item_data:
            return None
            
        return {
            'item': current_item,
            'type': item_data.get('type', ''),
            'id': item_data.get('id', ''),
            'data': item_data.get('data')
        }
    
    def get_target_folder_id(self):
        """Get the folder ID where new items should be created."""
        selected_info = self.get_selected_item_info()
        if not selected_info:
            return None
            
        if selected_info['type'] == 'folder':
            return selected_info['id']
        elif selected_info['type'] == 'project':
            return None  # Root level
        else:
            # For non-folder items, get their parent folder
            item_obj = selected_info['data']
            return item_obj.parent_id if item_obj else None
    
    def add_folder(self):
        """Add a new folder."""
        if not self.app_state.has_project:
            return
            
        folder_id = self.get_target_folder_id()
        
        command = CreateFolderCommand(self.app_context, parent_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)
    
    def add_note(self):
        """Add a new note."""
        if not self.app_state.has_project:
            return
            
        folder_id = self.get_target_folder_id()
        
        command = CreateNoteCommand(self.app_context, folder_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)
    
    def import_csv(self):
        """Import a CSV file as a dataset."""
        if not self.app_state.has_project:
            return
            
        folder_id = self.get_target_folder_id()
        
        command = ImportCsvCommand(self.app_context, folder_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)
    
    def create_empty_dataset(self):
        """Create a new empty dataset."""
        if not self.app_state.has_project:
            return
            
        folder_id = self.get_target_folder_id()
        
        command = CreateEmptyDatasetCommand(self.app_context, folder_id=folder_id)
        self.app_context.get_command_executor().execute_command(command)
    
    def create_chart_from_dataset(self):
        """Create a chart from the selected dataset."""
        selected_item = self.tree.currentItem()
        if not selected_item:
            return
            
        # Get dataset information
        item_data = selected_item.data(0, Qt.ItemDataRole.UserRole)
        if not item_data or item_data.get('type') != 'dataset':
            return
            
        dataset_id = item_data.get('id')
        dataset_obj = item_data.get('data')
        dataset_name = dataset_obj.name if dataset_obj else 'Dataset'
        
        if dataset_id:
            # Signal to create a new chart tab with this dataset
            self.chart_create_requested.emit(dataset_id, f"Chart from {dataset_name}")
            self.logger.debug(f"Requesting chart creation for dataset '{dataset_id}'")
    
    def rename_selected_item(self):
        """Rename the selected item by starting inline editing."""
        selected_info = self.get_selected_item_info()
        if not selected_info or selected_info['type'] == 'project':
            return
            
        # Start inline editing on the current item
        current_item = selected_info['item']
        if current_item:
            self.tree.editItem(current_item, 0)  # Start editing the first column
    
    def delete_selected_item(self):
        """Delete the selected item."""
        selected_info = self.get_selected_item_info()
        if not selected_info or selected_info['type'] == 'project':
            return
            
        item_id = selected_info['id']
        item_obj = selected_info['data']
        item_name = item_obj.name if item_obj else 'Unnamed Item'
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete '{item_name}' and all its contents?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            command = DeleteItemCommand(self.app_context, item_id)
            self.app_context.get_command_executor().execute_command(command)
        
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
                    
                self.update_project_tree(project)
        else:
            self.project_title_label.setText("No project loaded")
            self.project_file_label.setText("File label will appear here")
            self.show_no_project_content()
    
    def add_column_to_dataset(self):
        """Add a new column to the selected dataset."""
        selected_info = self.get_selected_item_info()
        if not selected_info or selected_info['type'] != 'dataset':
            return
        
        dataset_id = selected_info['id']
        
        command = AddColumnCommand(self.app_context, dataset_id)
        success = self.app_context.get_command_executor().execute_command(command)
        
        if success:
            self.logger.info(f"Added column to dataset {dataset_id}")
        else:
            self.logger.warning(f"Failed to add column to dataset {dataset_id}")
    
    def add_row_to_dataset(self):
        """Add a new row to the selected dataset."""
        selected_info = self.get_selected_item_info()
        if not selected_info or selected_info['type'] != 'dataset':
            return
        
        dataset_id = selected_info['id']
        
        command = AddRowCommand(self.app_context, dataset_id)
        success = self.app_context.get_command_executor().execute_command(command)
        
        if success:
            self.logger.info(f"Added row to dataset {dataset_id}")
        else:
            self.logger.warning(f"Failed to add row to dataset {dataset_id}")