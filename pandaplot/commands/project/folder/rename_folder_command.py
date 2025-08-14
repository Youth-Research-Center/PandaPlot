from typing import Optional, override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items.folder import Folder
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState

# TODO: do we need this command at all? 
class RenameFolderCommand(Command):
    """
    Command to rename a folder in the project structure.
    """

    def __init__(self, app_context: AppContext, folder_id: Optional[str] = None, new_name: Optional[str] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.folder_id = folder_id
        self.new_name = new_name

        # Store state for undo
        self.old_name = None

    @override
    def execute(self) -> bool:
        """Execute the rename folder command."""
        try:
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Rename Folder",
                    "No project is currently loaded."
                )
                return False

            project = self.app_state.current_project
            if not project:
                return False

            # Check if folder_id and new_name are provided
            if not self.folder_id or not self.new_name:
                self.ui_controller.show_warning_message(
                    "Rename Folder",
                    "Folder ID and new name are required."
                )
                return False

            # Find the folder to rename using the hierarchical structure
            folder = project.find_item(self.folder_id)
            if folder is None or not isinstance(folder, Folder):
                self.ui_controller.show_warning_message(
                    "Rename Folder",
                    f"Folder with ID '{self.folder_id}' not found in the project."
                )
                return False

            # Store old name for undo
            self.old_name = folder.name

            # Rename the folder
            folder.name = self.new_name

            # Emit event
            self.app_state.event_bus.emit('folder_renamed', {
                'project': project,
                'folder_id': self.folder_id,
                'old_name': self.old_name,
                'new_name': self.new_name,
                'folder': folder
            })

            self.logger.info(
                "Renamed folder '%s' -> '%s' (id=%s)", self.old_name, self.new_name, self.folder_id
            )
            return True

        except Exception as e:
            error_msg = f"Failed to rename folder: {e}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message(
                "Rename Folder Error", error_msg)
            return False

    @override
    def undo(self):
        """Undo the rename folder command."""
        try:
            if self.old_name and self.folder_id and self.app_state.has_project:
                project = self.app_state.current_project
                if not project:
                    self.ui_controller.show_warning_message(
                        "Undo Rename Folder",
                        "No project is currently loaded."
                    )
                    return False

                # Find the folder and restore old name
                folder = project.find_item(self.folder_id)
                if folder is None or not isinstance(folder, Folder):
                    self.ui_controller.show_warning_message(
                        "Undo Rename Folder",
                        f"Folder with ID '{self.folder_id}' not found in the project."
                    )
                    return False

                folder.name = self.old_name

                # Emit event
                self.app_state.event_bus.emit('folder_renamed', {
                    'project': project,
                    'folder_id': self.folder_id,
                    'old_name': self.new_name,
                    'new_name': self.old_name,
                    'folder': folder
                })

                self.logger.info(
                    "Restored folder name to '%s' (id=%s)", self.old_name, self.folder_id
                )
                return True

        except Exception as e:
            error_msg = f"Failed to undo rename folder: {e}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)
            return False

    @override
    def redo(self):
        """Redo the rename folder command."""
        try:
            if self.old_name and self.folder_id and self.new_name and self.app_state.has_project:
                project = self.app_state.current_project
                if not project:
                    return False

                # Find the folder and apply new name
                folder = project.find_item(self.folder_id)
                if folder is None or not isinstance(folder, Folder):
                    return False

                folder.name = self.new_name

                # Emit event
                self.app_state.event_bus.emit('folder_renamed', {
                    'project': project,
                    'folder_id': self.folder_id,
                    'old_name': self.old_name,
                    'new_name': self.new_name,
                    'folder': folder
                })

                self.logger.info(
                    "Redone folder rename to '%s' (id=%s)", self.new_name, self.folder_id
                )
                return True
            else:
                return False

        except Exception as e:
            error_msg = f"Failed to redo rename folder: {e}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return False
