import uuid
from typing import Optional, override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import Folder
from pandaplot.models.state import (AppState, AppContext)


class CreateFolderCommand(Command):
    """
    Command to create a new folder in the project structure.
    """

    def __init__(self, app_context: AppContext, folder_name: Optional[str] = None, parent_id: Optional[str] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.folder_name = folder_name
        self.parent_id = parent_id

        # Store state for undo
        self.created_folder_id = None
        self.created_folder = None
        self.project = None

    @override
    def execute(self) -> bool:
        """Execute the create folder command."""
        try:
            self.logger.info("Executing CreateFolderCommand")
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Create Folder",
                    "Please open or create a project first."
                )
                return False

            self.project = self.app_state.current_project
            if not self.project:
                return False

            # Get folder name if not provided
            if not self.folder_name:
                # Generate a unique default name
                existing_folders = [item for item in self.project.get_all_items()
                                    if isinstance(item, Folder)]
                folder_count = len(existing_folders) + 1
                folder_name = f"New Folder {folder_count}"
            else:
                folder_name = self.folder_name.strip()

            # Validate folder name
            if not folder_name:
                self.ui_controller.show_warning_message(
                    "Create Folder",
                    "Folder name cannot be empty."
                )
                return False

            # Create folder ID
            self.created_folder_id = str(uuid.uuid4())
            self.created_folder = Folder(
                id=self.created_folder_id,
                name=folder_name
            )

            # Add folder to project
            self.project.add_item(self.created_folder,
                                  parent_id=self.parent_id)

            # Emit event
            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                'project': self.project,
                'folder_id': self.created_folder_id,
                'folder_name': folder_name,
                'parent_id': self.parent_id,
                'folder': self.created_folder
            })
            self.logger.info(
                "CreateFolderCommand: Created folder '%s' (id=%s) under parent %s",
                folder_name,
                self.created_folder_id,
                self.parent_id or "root"
            )

            return True

        except Exception as e:
            error_msg = f"Failed to create folder: {str(e)}"
            self.logger.error("CreateFolderCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message(
                "Create Folder Error", error_msg)
            return False

    @override
    def undo(self):
        """Undo the create folder command."""
        try:
            if self.created_folder_id and self.app_state.has_project:
                project = self.app_state.current_project
                if project:
                    folder = project.find_item(self.created_folder_id)
                    if folder is not None:
                        project.remove_item(folder)

                    # Emit event
                    self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
                        'project': project,
                        'folder_id': self.created_folder_id,
                        'folder': self.created_folder
                    })
                    self.logger.info(
                        "CreateFolderCommand: Undo creation of folder id=%s (name=%s)",
                        self.created_folder_id,
                        getattr(self.created_folder, 'name', '<unknown>')
                    )

        except Exception as e:
            error_msg = f"Failed to undo create folder: {str(e)}"
            self.logger.error("CreateFolderCommand Undo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)

    @override
    def redo(self):
        """Redo the create folder command."""
        try:
            if self.created_folder_id and self.created_folder is not None and self.app_state.has_project:
                project = self.app_state.current_project
                if not project:
                    return False

                # Re-add the same folder object to the project
                project.add_item(self.created_folder, parent_id=self.parent_id)

                # Emit event
                self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                    'project': project,
                    'folder_id': self.created_folder_id,
                    'folder_name': self.created_folder.name,
                    'parent_id': self.parent_id,
                    'folder': self.created_folder
                })
                self.logger.info(
                    "CreateFolderCommand: Redo creation of folder '%s' (id=%s) under parent %s",
                    self.created_folder.name,
                    self.created_folder_id,
                    self.parent_id or "root"
                )
                return True
            else:
                return False

        except Exception as e:
            error_msg = f"Failed to redo create folder: {str(e)}"
            self.logger.error("CreateFolderCommand Redo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return False
