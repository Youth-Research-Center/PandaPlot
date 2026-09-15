"""Command to duplicate one or more Image items into a target gallery."""

import uuid
from typing import List, override

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import Image, ImageGallery
from pandaplot.models.state import AppContext, AppState


class CopyImagesCommand(Command):
    """
    Command to duplicate one or more images into a (possibly different)
    image gallery. Copied-mode images get an independent in-memory byte
    buffer; external-mode images' copies share the same source_file
    reference (no bytes to duplicate).
    """

    def __init__(self, app_context: AppContext, image_ids: List[str], target_gallery_id: str):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.image_ids = image_ids
        self.target_gallery_id = target_gallery_id

        # Store state for undo
        self.created_image_ids: List[str] = []
        self.project = None

    @override
    def execute(self) -> CommandResult:
        """Execute the copy images command."""
        try:
            self.logger.info("Executing CopyImagesCommand for %d image(s) into gallery %s",
                              len(self.image_ids), self.target_gallery_id)

            if not self.app_state.has_project:
                self.ui_controller.show_warning_message("Copy Images", "Please open or create a project first.")
                return CommandResult.FAILURE

            self.project = get_current_project(self.app_context)
            if not self.project:
                self.logger.warning(
                    "CopyImagesCommand.execute: has_project is True but current_project is None"
                )
                return CommandResult.FAILURE

            target_gallery = self.project.find_item(self.target_gallery_id)
            if not isinstance(target_gallery, ImageGallery):
                self.logger.warning(
                    "CopyImagesCommand.execute: target gallery '%s' not found or not an ImageGallery (got %s)",
                    self.target_gallery_id, type(target_gallery).__name__ if target_gallery else None,
                )
                self.ui_controller.show_error_message(
                    "Copy Images Error", f"Target gallery '{self.target_gallery_id}' not found."
                )
                return CommandResult.FAILURE

            originals = []
            for image_id in self.image_ids:
                original = self.project.find_item(image_id)
                if not isinstance(original, Image):
                    self.logger.warning(
                        "CopyImagesCommand.execute: image '%s' not found or not an Image (got %s)",
                        image_id, type(original).__name__ if original else None,
                    )
                    self.ui_controller.show_error_message(
                        "Copy Images Error", f"Image '{image_id}' not found."
                    )
                    return CommandResult.FAILURE
                originals.append(original)

            new_images = [self._build_copy(original) for original in originals]

            for image in new_images:
                self.project.add_item(image, parent_id=self.target_gallery_id)
                self.created_image_ids.append(image.id)

                self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                    "project": self.project,
                    "image_id": image.id,
                    "image_name": image.name,
                    "parent_id": self.target_gallery_id,
                    "image": image
                })

            self.logger.info("CopyImagesCommand: Copied %d image(s) into gallery %s",
                              len(new_images), self.target_gallery_id)
            return CommandResult.SUCCESS

        except Exception as e:
            error_msg = f"Failed to copy images: {str(e)}"
            self.logger.error("CopyImagesCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Copy Images Error", error_msg)
            return CommandResult.FAILURE

    def _build_copy(self, original: Image) -> Image:
        """Build a duplicate Image, independent in-memory bytes for copied mode."""
        copy = Image(
            id=str(uuid.uuid4()), name=original.name, source_file=original.source_file,
            storage_mode=original.storage_mode, image_ext=original.image_ext,
            width=original.width, height=original.height, size_bytes=original.size_bytes,
        )
        if original.storage_mode == "copied":
            copy.set_bytes(original.get_bytes())
        return copy

    def undo(self) -> CommandResult:
        """Undo the copy images command by removing all created copies."""
        try:
            if self.created_image_ids and self.app_state.has_project:
                project = get_current_project(self.app_context)
                if not project:
                    self.logger.warning(
                        "CopyImagesCommand.undo: has_project is True but current_project is None"
                    )
                    return CommandResult.FAILURE

                for image_id in self.created_image_ids:
                    image = project.find_item(image_id)
                    if image is not None:
                        project.remove_item(image)

                    self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
                        "project": project,
                        "image_id": image_id,
                    })

                self.logger.info("Undone copy of %d image(s)", len(self.created_image_ids))
                return CommandResult.SUCCESS
            else:
                # No images were ever created (execute() failed or was never
                # called), so there's nothing to undo.
                return CommandResult.NOOP

        except Exception as e:
            error_msg = f"Failed to undo image copy: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)
            return CommandResult.FAILURE

    def redo(self) -> CommandResult:
        """Redo the copy by re-running execute() after clearing prior created ids."""
        try:
            if self.created_image_ids and self.app_state.has_project:
                self.created_image_ids = []
                return self.execute()
            return CommandResult.FAILURE
        except Exception as e:
            error_msg = f"Failed to redo image copy: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return CommandResult.FAILURE

    @override
    def cleanup(self) -> None:
        """Release the created-image-id bookkeeping and cached project
        reference held for undo once this command is dropped from the
        stacks for good (see Command.cleanup)."""
        self.created_image_ids = []
        self.project = None
