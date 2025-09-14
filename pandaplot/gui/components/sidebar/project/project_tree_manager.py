import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QTreeWidgetItem,
)

from pandaplot.models.project.visitors import ProjectTreeBuilder
from pandaplot.models.state.app_context import AppContext


class ProjectTreeManager:
    def __init__(self, app_context: AppContext, tree, on_item_name_changed):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app_context = app_context
        self.tree = tree
        self.on_item_name_changed = on_item_name_changed

    def show_no_project_content(self):
        """Show placeholder content when no project is loaded."""
        self.tree.clear()
        placeholder_item = QTreeWidgetItem(["No project loaded"])
        placeholder_item.setToolTip(
            0, "Load a project to see its structure here")
        self.tree.addTopLevelItem(placeholder_item)

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
            root_item.setData(0, Qt.ItemDataRole.UserRole, {
                              'type': 'project', 'id': 'root'})

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
                tree_item.setFlags(tree_item.flags() & ~
                                   Qt.ItemFlag.ItemIsEditable)
            else:
                # Other items are editable
                tree_item.setFlags(tree_item.flags() |
                                   Qt.ItemFlag.ItemIsEditable)

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
