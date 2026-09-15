import uuid
from typing import Optional, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import Folder
from pandaplot.models.state import AppContext, AppState


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
    def execute(self) -> CommandResult:
        """Execute the create folder command."""
        try:
            self.logger.info("Executing CreateFolderCommand")
            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Create Folder",
                    "Please open or create a project first."
                )
                return CommandResult.FAILURE

            self.project = get_current_project(self.app_context)
            if not self.project:
                self.logger.warning(
                    "CreateFolderCommand.execute: has_project is True but current_project is None"
                )
                return CommandResult.FAILURE

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
                return CommandResult.FAILURE

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
                "project": self.project,
                "folder_id": self.created_folder_id,
                "folder_name": folder_name,
                "parent_id": self.parent_id,
                "folder": self.created_folder
            })
            self.logger.info(
                "CreateFolderCommand: Created folder '%s' (id=%s) under parent %s",
                folder_name,
                self.created_folder_id,
                self.parent_id or "root"
            )

            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to create folder: {str(e)}"
            self.logger.error("CreateFolderCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message(
                "Create Folder Error", error_msg)
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        """Undo the create folder command."""
        try:
            if self.created_folder_id and self.app_state.has_project:
                project = get_current_project(self.app_context)
                if not project:
                    self.logger.warning(
                        "CreateFolderCommand.undo: has_project is True but current_project is None (folder id=%s)",
                        self.created_folder_id,
                    )
                    return CommandResult.FAILURE

                folder = project.find_item(self.created_folder_id)
                if folder is None:
                    self.logger.warning(
                        "CreateFolderCommand.undo: folder '%s' not found", self.created_folder_id
                    )
                    return CommandResult.FAILURE

                project.remove_item(folder)

                # Emit event
                self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
                    "project": project,
                    "folder_id": self.created_folder_id,
                    "folder": self.created_folder
                })
                self.logger.info(
                    "CreateFolderCommand: Undo creation of folder id=%s (name=%s)",
                    self.created_folder_id,
                    getattr(self.created_folder, "name", "<unknown>")
                )
                return CommandResult.SUCCESS
            else:
                # The folder was never actually created (execute() failed or
                # was never called), so there's nothing to undo.
                return CommandResult.NOOP

        except Exception as e:
            error_msg = f"Failed to undo create folder: {str(e)}"
            self.logger.error("CreateFolderCommand Undo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)
            return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        """Redo the create folder command."""
        try:
            if self.created_folder_id and self.created_folder is not None and self.app_state.has_project:
                project = get_current_project(self.app_context)
                if not project:
                    self.logger.warning(
                        "CreateFolderCommand.redo: has_project is True but current_project is None (folder id=%s)",
                        self.created_folder_id,
                    )
                    return CommandResult.FAILURE

                # Re-add the same folder object to the project
                project.add_item(self.created_folder, parent_id=self.parent_id)

                # Emit event
                self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                    "project": project,
                    "folder_id": self.created_folder_id,
                    "folder_name": self.created_folder.name,
                    "parent_id": self.parent_id,
                    "folder": self.created_folder
                })
                self.logger.info(
                    "CreateFolderCommand: Redo creation of folder '%s' (id=%s) under parent %s",
                    self.created_folder.name,
                    self.created_folder_id,
                    self.parent_id or "root"
                )
                return CommandResult.SUCCESS
            else:
                return CommandResult.FAILURE

        except Exception as e:
            error_msg = f"Failed to redo create folder: {str(e)}"
            self.logger.error("CreateFolderCommand Redo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return CommandResult.FAILURE

    @override
    def cleanup(self) -> None:
        """Release the cached project reference held during creation once
        this command is dropped from the stacks for good (see
        Command.cleanup)."""
        self.project = None
