"""Command to create an Image item from already-in-memory PNG bytes (e.g.
a rendered chart snapshot) -- unlike ImportImagesCommand, which only
imports from a local file path or URL."""

import uuid
from typing import Optional, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import Image, ImageGallery
from pandaplot.models.state import AppContext, AppState


class CreateImageFromBytesCommand(Command):
    """Adds one Image item, built from `png_bytes`, into the gallery
    `gallery_id`; undoable/redoable."""

    def __init__(self, app_context: AppContext, gallery_id: str, name: str,
                 png_bytes: bytes, width: int, height: int):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.gallery_id = gallery_id
        self.name = name
        self.png_bytes = png_bytes
        self.width = width
        self.height = height

        self.created_image_id: Optional[str] = None
        self.created_image: Optional[Image] = None
        self.project = None

    @override
    def execute(self) -> CommandResult:
        try:
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message("Insert Chart", "Please open or create a project first.")
                return CommandResult.FAILURE

            self.project = get_current_project(self.app_context)
            if not self.project:
                self.logger.warning("CreateImageFromBytesCommand.execute: has_project True but current_project None")
                return CommandResult.FAILURE

            gallery = self.project.find_item(self.gallery_id)
            if not isinstance(gallery, ImageGallery):
                self.logger.warning(
                    "CreateImageFromBytesCommand.execute: gallery '%s' not found or not an ImageGallery",
                    self.gallery_id,
                )
                self.ui_controller.show_error_message(
                    "Insert Chart Error", f"Gallery '{self.gallery_id}' not found."
                )
                return CommandResult.FAILURE

            self.created_image_id = str(uuid.uuid4())
            self.created_image = Image(
                id=self.created_image_id, name=self.name, storage_mode="copied",
                image_ext="png", width=self.width, height=self.height,
                size_bytes=len(self.png_bytes),
            )
            self.created_image.set_bytes(self.png_bytes)

            self.project.add_item(self.created_image, parent_id=self.gallery_id)

            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                "project": self.project,
                "image_id": self.created_image_id,
                "image_name": self.name,
                "parent_id": self.gallery_id,
                "image": self.created_image,
            })
            self.logger.info(
                "CreateImageFromBytesCommand: created image '%s' (id=%s) in gallery %s",
                self.name, self.created_image_id, self.gallery_id,
            )
            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to create image: {str(e)}"
            self.logger.error("CreateImageFromBytesCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Insert Chart Error", error_msg)
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        try:
            if not (self.created_image_id and self.app_state.has_project):
                return CommandResult.NOOP
            project = get_current_project(self.app_context)
            if not project:
                return CommandResult.FAILURE
            image = project.find_item(self.created_image_id)
            if image is None:
                return CommandResult.FAILURE
            project.remove_item(image)
            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
                "project": project, "image_id": self.created_image_id, "image": self.created_image,
            })
            return CommandResult.SUCCESS
        except Exception as e:
            self.logger.error("CreateImageFromBytesCommand Undo Error: %s", e, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", f"Failed to undo: {str(e)}")
            return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        try:
            if not (self.created_image_id and self.created_image is not None and self.app_state.has_project):
                return CommandResult.FAILURE
            project = get_current_project(self.app_context)
            if not project:
                return CommandResult.FAILURE
            project.add_item(self.created_image, parent_id=self.gallery_id)
            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                "project": project, "image_id": self.created_image_id, "image_name": self.name,
                "parent_id": self.gallery_id, "image": self.created_image,
            })
            return CommandResult.SUCCESS
        except Exception as e:
            self.logger.error("CreateImageFromBytesCommand Redo Error: %s", e, exc_info=True)
            self.ui_controller.show_error_message("Redo Error", f"Failed to redo: {str(e)}")
            return CommandResult.FAILURE

    @override
    def cleanup(self) -> None:
        self.project = None
