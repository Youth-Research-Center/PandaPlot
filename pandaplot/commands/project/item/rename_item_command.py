from typing import override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.state import (AppState, AppContext)


class RenameItemCommand(Command):
    """
    Command to rename a note in the project.
    """

    def __init__(self, app_context: AppContext, item_id: str, new_name: str):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.item_id = item_id
        self.new_name = new_name

        # Store state for undo
        self.old_name = None

    @override
    def execute(self) -> bool:
        """Execute the rename item command."""
        try:
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Rename Item",
                    "No project is currently loaded."
                )
                return False

            project = self.app_state.current_project
            if not project:
                return False

            # Check in metadata notes
            item = project.find_item(self.item_id)

            if item is None:
                self.ui_controller.show_warning_message(
                    "Rename Item",
                    f"Item with ID '{self.item_id}' not found."
                )
                return False

            self.old_name = item.name
            item.update_name(self.new_name)

            # Emit dotted event only
            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_RENAMED, {
                'project': project,
                'item_id': self.item_id,
                'old_name': self.old_name,
                'new_name': self.new_name
            })

            self.logger.info(
                "Renamed item '%s' -> '%s' (id=%s)", self.old_name, self.new_name, self.item_id
            )
            return True
        except Exception as e:
            error_msg = f"Failed to rename item: {e}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message(
                "Rename Item Error", error_msg)
            raise

    def undo(self):
        """Undo the rename item command."""
        try:
            if self.old_name and self.app_state.has_project:
                project = self.app_state.current_project
                if not project:
                    return

                item = project.find_item(self.item_id)
                if item is None:
                    self.ui_controller.show_warning_message(
                        "Undo Rename Item",
                        f"Item with ID '{self.item_id}' not found."
                    )
                    return

                # Perform restore
                item.update_name(self.old_name)

                # Emit event for UI update
                self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_RENAMED, {
                    'project': project,
                    'item_id': self.item_id,
                    'old_name': self.new_name,
                    'new_name': self.old_name
                })

                self.logger.info(
                    "Restored item name to '%s' (id=%s)", self.old_name, self.item_id
                )

        except Exception as e:
            error_msg = f"Failed to undo rename item: {e}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)

    def redo(self):
        """Redo the rename item command."""
        self.execute()
