import logging

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QTreeWidget,
)

from pandaplot.commands.project.item.move_item_command import MoveItemCommand


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
                    self.logger.debug(
                        "ProjectTreeWidget: dropping on folder new_parent_id=%s", new_parent_id)
                # If dropping on another item, use its parent folder
                elif target_type in ['note', 'dataset', 'chart']:
                    target_item_obj = target_data.get('data')
                    if target_item_obj and target_item_obj.parent_id:
                        # Check if the parent_id is the root collection ID
                        project = self.parent_panel.app_state.current_project
                        if project and target_item_obj.parent_id == project.root.id:
                            new_parent_id = 'root'
                            self.logger.debug(
                                "ProjectTreeWidget: target item parent is root; new_parent_id=root")
                        else:
                            new_parent_id = target_item_obj.parent_id
                            self.logger.debug(
                                "ProjectTreeWidget: target item parent set to %s", new_parent_id)
                    else:
                        new_parent_id = 'root'
                        self.logger.debug(
                            "ProjectTreeWidget: target item has no parent; new_parent_id=root")
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
                self.logger.debug(
                    "ProjectTreeWidget: current item parent is root")
            else:
                current_parent_id = current_item_obj.parent_id if current_item_obj.parent_id else 'root'
                self.logger.debug(
                    "ProjectTreeWidget: current item parent is %s", current_parent_id)
        else:
            current_parent_id = 'root'
            self.logger.debug(
                "ProjectTreeWidget: no current item data; current_parent_id=root")

        # Only execute move if parent actually changed
        if new_parent_id != current_parent_id:
            self.logger.info("ProjectTreeWidget: moving %s %s from %s to %s",
                             source_type, source_id, current_parent_id, new_parent_id)

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

                        self.logger.debug(
                            "ProjectTreeWidget: drag over item %s %s", target_type, target_id)

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
                self.logger.debug("ProjectTreeWidget: highlighting %s %s", item_data.get(
                    'type', 'unknown'), item_data.get('id', 'no-id'))
            except RuntimeError:
                # Item has been deleted by Qt, skip highlighting
                self.logger.debug(
                    "ProjectTreeWidget: skipping highlight - item deleted by Qt")
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
                    self.highlighted_item.setBackground(
                        0, self.original_backgrounds[self.highlighted_item])
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
