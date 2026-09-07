"""
Command to apply image edits (crop, rotate, resize) to an existing Image item.
"""

import datetime
from typing import Optional, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import Image
from pandaplot.models.state import AppContext, AppState


class EditImageCommand(Command):
    """
    Command to update an Image item with newly edited raw image bytes and dimensions.
    """

    def __init__(self, app_context: AppContext, image_id: str,
                 new_bytes: bytes, new_width: int, new_height: int,
                 new_ext: Optional[str] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.image_id = image_id
        self.new_bytes = new_bytes
        self.new_width = new_width
        self.new_height = new_height
        self.new_ext = new_ext

        # Undo state
        self.old_bytes: Optional[bytes] = None
        self.old_width: int = 0
        self.old_height: int = 0
        self.old_size_bytes: Optional[int] = None
        self.old_storage_mode: str = "copied"
        self.old_image_ext: str = ""
        self.old_modified_at: str = ""
        # True once the old_* fields above have been captured. redo()
        # re-enters execute(), which must NOT recapture them a second
        # time: CommandExecutor pushes a command onto the redo stack even
        # when undo() returns FAILURE (not just on success), and
        # EditImageCommand.undo()'s failure branches all return before
        # restoring the item -- so the item can still be in its edited
        # (new) state when a later redo() runs. Recapturing old_bytes at
        # that point would silently replace the true pre-edit snapshot
        # with the already-edited bytes, permanently losing the ability
        # to restore the original on any future undo.
        self._old_state_captured = False

    @override
    def execute(self) -> CommandResult:
        try:
            self.logger.info("Executing EditImageCommand for image %s", self.image_id)

            if not self.app_state.has_project:
                self.ui_controller.show_warning_message("Edit Image", "Please open or create a project first.")
                return CommandResult.FAILURE

            project = get_current_project(self.app_context)
            if not project:
                return CommandResult.FAILURE

            item = project.find_item(self.image_id)
            if not isinstance(item, Image):
                self.logger.warning("EditImageCommand: item '%s' not found or not an Image", self.image_id)
                self.ui_controller.show_error_message("Edit Image Error", f"Image '{self.image_id}' not found.")
                return CommandResult.FAILURE

            # Save state for undo -- only the first time this command
            # actually applies (see _old_state_captured's docstring).
            if not self._old_state_captured:
                self.old_bytes = item.get_bytes()
                self.old_width = item.width
                self.old_height = item.height
                self.old_size_bytes = item.size_bytes
                self.old_storage_mode = item.storage_mode
                self.old_image_ext = item.image_ext
                self.old_modified_at = item.modified_at
                self._old_state_captured = True

            # Apply edit
            item.set_bytes(self.new_bytes)
            item.width = self.new_width
            item.height = self.new_height
            item.size_bytes = len(self.new_bytes)
            item.storage_mode = "copied"
            if self.new_ext:
                item.image_ext = self.new_ext
            item.modified_at = datetime.datetime.now().isoformat()

            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_CONTENT_CHANGED, {
                "project": project,
                "item_id": item.id,
                "image_id": item.id,
                "image": item,
            })

            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to edit image: {str(e)}"
            self.logger.error("EditImageCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Edit Image Error", error_msg)
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        try:
            if not self.app_state.has_project:
                return CommandResult.FAILURE

            project = get_current_project(self.app_context)
            if not project:
                return CommandResult.FAILURE

            item = project.find_item(self.image_id)
            if not isinstance(item, Image):
                return CommandResult.FAILURE

            item.set_bytes(self.old_bytes)
            item.width = self.old_width
            item.height = self.old_height
            item.size_bytes = self.old_size_bytes
            item.storage_mode = self.old_storage_mode
            item.image_ext = self.old_image_ext
            item.modified_at = self.old_modified_at

            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_CONTENT_CHANGED, {
                "project": project,
                "item_id": item.id,
                "image_id": item.id,
                "image": item,
            })

            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to undo image edit: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)
            return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the pre-edit/post-edit image byte buffers held for undo
        once this command is dropped from the stacks for good (see
        Command.cleanup)."""
        self.old_bytes = None
        self.new_bytes = b""
