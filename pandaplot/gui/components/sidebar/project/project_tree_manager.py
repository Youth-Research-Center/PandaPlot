import logging
from collections.abc import Callable

import shiboken6
from PySide6.QtCore import QSignalBlocker, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHeaderView,
    QToolButton,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QWidget,
)

from pandaplot.gui.components.sidebar.project.project_tree import CONTAINER_TYPES
from pandaplot.gui.resources.item_icons import SELECTED_ROW_FOREGROUND, item_icon
from pandaplot.gui.resources.themed_icons import IconRole, themed_icon
from pandaplot.models.project import Project
from pandaplot.models.project.visitors import ProjectTreeBuilder
from pandaplot.models.state.app_context import AppContext

ACTIONS_COLUMN = 1
"""Tree column that holds row actions (the Project Details button); column 0 holds the item names."""

_ACTIONS_COLUMN_PADDING = 4
_MAX_BUTTON_ICON_SIZE = 16


class ProjectTreeManager:
    """Fills the Project Explorer tree and keeps the Project Details button on the project's root row.

    The project root item (and its button) is kept while the same project is shown, so the button keeps its focus across tree rebuilds.
    """

    def __init__(
        self,
        app_context: AppContext,
        tree,
        on_item_name_changed,
        *,
        on_project_details: Callable[[Project], None] | None = None,
    ):
        """Create the manager.

        Args:
            app_context: Provides the theme used to tint icons.
            tree: The `ProjectTreeWidget` to fill.
            on_item_name_changed: Slot for the tree's `itemChanged`, disconnected while the tree is rebuilt.
            on_project_details: Called with the project of the row whose Project Details button was clicked.
        """
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app_context = app_context
        self.tree = tree
        self.on_item_name_changed = on_item_name_changed
        self._on_project_details = on_project_details
        self._root_project: Project | None = None
        self._root_button: QToolButton | None = None
        self.tree.itemSelectionChanged.connect(self._tint_root_button)

    def _icon(self, item_type: str) -> QIcon:
        return item_icon(self.app_context, item_type, selected_color=SELECTED_ROW_FOREGROUND)

    def show_no_project_content(self):
        """Show placeholder content when no project is loaded."""
        self.tree.clear()
        self._root_project = None
        self._root_button = None
        placeholder_item = QTreeWidgetItem(["No project loaded"])
        placeholder_item.setToolTip(
            0, "Load a project to see its structure here")
        self.tree.addTopLevelItem(placeholder_item)
        self._fit_actions_column()

    def update_project_tree(self, project):
        """Update the tree view with project contents using hierarchical metadata structure."""
        # Save expanded state of folders before rebuilding
        expanded_folders = self._get_expanded_folders()

        # Temporarily disconnect itemChanged signal to prevent spurious rename commands
        self.tree.itemChanged.disconnect(self.on_item_name_changed)

        try:
            root_item = self._kept_root_item(project)
            if root_item is None:
                self.tree.clear()
                root_item = self._create_root_item(project)
            else:
                # Rebuild only the children, and leave nothing current or selected, exactly as a full clear did.
                root_item.takeChildren()
                self.tree.selectionModel().clear()
                root_item.setText(0, project.name)
                root_item.setToolTip(0, f"Project: {project.description}")

            self._build_tree_from_project(project, root_item)
        finally:
            # Reconnect the itemChanged signal
            self.tree.itemChanged.connect(self.on_item_name_changed)

        if self._root_button is not None:
            self._root_button.setAccessibleName(f"Project Details: {project.name}")
        self._tint_root_button()

        # Expand the root item
        root_item.setExpanded(True)

        # Restore expanded state of folders
        self._restore_expanded_folders(expanded_folders)

    def _kept_root_item(self, project: Project) -> QTreeWidgetItem | None:
        """Return the existing root item when the tree already shows `project`, otherwise None."""
        if self._root_project is not project or self.tree.topLevelItemCount() != 1:
            return None
        root_item = self.tree.topLevelItem(0)
        if self._root_button is None or not shiboken6.isValid(self._root_button):
            return None
        return root_item

    def _create_root_item(self, project: Project) -> QTreeWidgetItem:
        """Add the project's root row and its Project Details button to the (cleared) tree."""
        root_item = QTreeWidgetItem([project.name])
        root_item.setIcon(0, self._icon("project"))
        root_item.setToolTip(0, f"Project: {project.description}")
        root_item.setData(0, Qt.ItemDataRole.UserRole, {"type": "project", "id": "root"})

        # Make project root non-editable
        root_item.setFlags(root_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.tree.addTopLevelItem(root_item)
        self._root_project = project
        self._create_root_button(root_item, project)
        return root_item

    def _create_root_button(self, root_item: QTreeWidgetItem, project: Project) -> None:
        """Put the Project Details button in the actions column of the project's root row."""
        button = QToolButton(self.tree)
        button.setAutoRaise(True)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        button.setToolTip("Project Details...")
        button.setAccessibleName(f"Project Details: {project.name}")
        button.setAccessibleDescription("Edit the project's name, notes, cover image and example settings")
        button.clicked.connect(self._on_root_button_clicked)
        self._root_button = button
        # Size the button before it is attached: an index widget's size hint feeds back into the row height.
        self._fit_actions_column()
        self._tint_root_button()
        self.tree.setItemWidget(root_item, ACTIONS_COLUMN, button)
        QWidget.setTabOrder(self.tree, button)

    def _on_root_button_clicked(self) -> None:
        """Open Project Details for the project of the row the button is on."""
        if self._on_project_details is not None and self._root_project is not None:
            self._on_project_details(self._root_project)

    def _row_side(self) -> int:
        """Height of a tree row at the current font, which is the side of the row's button."""
        item = self.tree.topLevelItem(0)
        if item is None:
            return self.tree.fontMetrics().height() + _ACTIONS_COLUMN_PADDING
        return self.tree.sizeHintForIndex(self.tree.indexFromItem(item, 0)).height()

    def _fit_actions_column(self) -> None:
        """Size the actions column and the button from the row height, so the root row is as tall as the others."""
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(ACTIONS_COLUMN, QHeaderView.ResizeMode.Fixed)
        side = self._row_side()
        if self._root_button is not None and shiboken6.isValid(self._root_button):
            self._root_button.setFixedSize(side, side)
            icon_side = min(_MAX_BUTTON_ICON_SIZE, side - 2)
            self._root_button.setIconSize(QSize(icon_side, icon_side))
        width = side + _ACTIONS_COLUMN_PADDING
        header.setMinimumSectionSize(width)  # the style's default minimum is wider than a button
        header.resizeSection(ACTIONS_COLUMN, width)

    def _tint_root_button(self) -> None:
        """Tint the button's icon for the row state: light on the accent of a selected row, the text colour otherwise."""
        button = self._root_button
        if button is None or not shiboken6.isValid(button):
            return
        root_item = self.tree.topLevelItem(0)
        selected = root_item is not None and root_item.isSelected()
        role = IconRole.ON_ACCENT if selected else IconRole.TEXT
        button.setIcon(themed_icon(self.app_context, "info", role=role))

    def retint_icons(self) -> None:
        """Re-render every item icon from the current theme tokens.

        Setting an icon emits `itemChanged`, which the panel treats as a rename, so the tree's signals are blocked meanwhile.
        """
        with QSignalBlocker(self.tree):
            iterator = QTreeWidgetItemIterator(self.tree)
            while iterator.value():
                tree_item = iterator.value()
                item_data = tree_item.data(0, Qt.ItemDataRole.UserRole)
                if isinstance(item_data, dict) and item_data.get("type"):
                    tree_item.setIcon(0, self._icon(item_data["type"]))
                iterator += 1
        self._fit_actions_column()
        self._tint_root_button()

    def _build_tree_from_project(self, project, root_item):
        """Build tree structure from project using visitor pattern."""
        # Create a factory for QTreeWidgetItem creation
        def create_tree_item(display_text: str, item_type: str, item_data: dict) -> QTreeWidgetItem:
            """Factory function to create QTreeWidgetItem instances."""
            tree_item = QTreeWidgetItem([display_text])
            tree_item.setIcon(0, self._icon(item_type))
            tree_item.setData(0, Qt.ItemDataRole.UserRole, item_data)

            # Set item flags based on type
            if item_type == "project":
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
                if item_data and (item_data.get("type") == "project" or item_data.get("type") in CONTAINER_TYPES):
                    expanded.add(item_data.get("id", ""))

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
            if item_data and item_data.get("id") in expanded_folders:
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
            "item": current_item,
            "type": item_data.get("type", ""),
            "id": item_data.get("id", ""),
            "data": item_data.get("data")
        }

    def get_target_folder_id(self):
        """Get the folder ID where new items should be created."""
        selected_info = self.get_selected_item_info()
        if not selected_info:
            return None

        if selected_info["type"] in CONTAINER_TYPES:
            return selected_info["id"]
        elif selected_info["type"] == "project":
            return None  # Root level
        else:
            # For non-folder items, get their parent folder
            item_obj = selected_info["data"]
            return item_obj.parent_id if item_obj else None
