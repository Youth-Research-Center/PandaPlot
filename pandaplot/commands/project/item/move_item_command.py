from typing import Optional, override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.state import (AppState, AppContext)


class MoveItemCommand(Command):
    """
    Command to move an item between folders in the project structure.
    """

    # TODO: avoid optional types
    def __init__(self, app_context: AppContext, item_id: Optional[str] = None, item_type: Optional[str] = None,
                 source_folder_id: Optional[str] = None, target_folder_id: Optional[str] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.item_id = item_id
        self.item_type = item_type  # 'note', 'chart', 'dataset', etc.
        self.source_folder_id = source_folder_id
        self.target_folder_id = target_folder_id

        # Store state for undo
        self.move_performed = False

    @override
    def execute(self):
        """Execute the move item command."""
        # Initialize item_name for error messages
        item_name = self.item_id  # Fallback to ID if name is not available

        try:
            # Debug logging
            self.logger.debug(
                f"Moving item '{self.item_id}' from '{self.source_folder_id}' to '{self.target_folder_id}'")

            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Move Item",
                    "No project is currently loaded."
                )
                return

            project = self.app_state.current_project
            if project is None:
                return

            # Find the item in the hierarchical structure
            if not self.item_id:
                self.ui_controller.show_error_message(
                    "Move Item Error",
                    "No item ID specified."
                )
                return

            item = project.find_item(self.item_id)
            if item is None:
                self.ui_controller.show_error_message(
                    "Move Item Error",
                    f"Item '{self.item_id}' not found."
                )
                return

            # Store item name for better error messages
            item_name = getattr(item, 'name', 'Unnamed Item')
            self.logger.debug(f"Moving item '{item_name}' (ID: {self.item_id})")

            # Validate target folder exists (if specified)
            if self.target_folder_id and self.target_folder_id != 'root':
                self.logger.debug(f"Looking for target folder '{self.target_folder_id}'")
                target_folder = project.find_item(self.target_folder_id)
                if target_folder is None:
                    error_msg = f"Target folder '{self.target_folder_id}' does not exist."
                    self.logger.error(error_msg)
                    self.logger.debug(f"Available items in project: {list(project.items_index.keys())}")
                    self.ui_controller.show_error_message(
                        "Move Item Error",
                        f"Cannot move '{item_name}' - target folder '{self.target_folder_id}' does not exist."
                    )
                    return
                else:
                    self.logger.debug(f"Found target folder: {target_folder.name} (type: {type(target_folder).__name__})")

            # Remove item from current parent
            project.remove_item(item)

            # Add item to new parent
            # Convert 'root' string to None for project.add_item()
            parent_id_for_add = None if self.target_folder_id == 'root' else self.target_folder_id
            project.add_item(item, parent_id=parent_id_for_add)

            self.move_performed = True

            # Emit event
            self.app_state.event_bus.emit('item_moved', {
                'project': project,
                'item_id': self.item_id,
                'item_type': self.item_type,
                'source_folder': self.source_folder_id,
                'target_folder': self.target_folder_id,
                'item': item
            })

            self.logger.info(f"Moved {self.item_type} '{item_name}' (ID: {self.item_id}) from '{self.source_folder_id}' to '{self.target_folder_id}'")

        except Exception as e:
            error_msg = f"Failed to move item '{item_name}': {str(e)}"
            self.logger.error(error_msg)
            self.ui_controller.show_error_message("Move Item Error", error_msg)
            raise

    def undo(self):
        """Undo the move item command."""
        try:
            if self.move_performed and self.app_state.has_project:
                project = self.app_state.current_project
                if project and self.item_id:
                    # Find the item in the hierarchical structure
                    item = project.find_item(self.item_id)
                    if item is not None:
                        # Get item name for better messages
                        item_name = getattr(item, 'name', 'Unnamed Item')

                        # Remove item from current location
                        project.remove_item(item)

                        # Add item back to original location
                        # Convert 'root' string to None for project.add_item()
                        parent_id_for_add = None if self.source_folder_id == 'root' else self.source_folder_id
                        project.add_item(item, parent_id=parent_id_for_add)

                        # Emit event
                        self.app_state.event_bus.emit('item_moved', {
                            'project': project,
                            'item_id': self.item_id,
                            'item_type': self.item_type,
                            'source_folder': self.target_folder_id,  # Reversed for undo
                            'target_folder': self.source_folder_id,
                            'item': item,
                            'undo': True
                        })

                        self.logger.info(f"Undid move of {self.item_type} '{item_name}' (ID: {self.item_id})")

        except Exception as e:
            # Try to get item name for error message
            item_name = self.item_id  # Fallback to ID
            if self.app_state.has_project:
                project = self.app_state.current_project
                if project and self.item_id:
                    item = project.find_item(self.item_id)
                    if item is not None:
                        item_name = getattr(item, 'name', self.item_id)

            error_msg = f"Failed to undo move of '{item_name}': {str(e)}"
            self.logger.error(error_msg)
            self.ui_controller.show_error_message("Undo Error", error_msg)

    def redo(self):
        """Redo the move item command."""
        self.execute()
