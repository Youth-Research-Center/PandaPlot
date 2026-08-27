import uuid
from typing import Optional, override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import ImageGallery
from pandaplot.models.state import AppContext, AppState


class CreateImageGalleryCommand(Command):
    """
    Command to create a new image gallery (or, when parent_id points at an
    existing gallery, a nested album) in the project structure.
    """

    def __init__(self, app_context: AppContext, gallery_name: Optional[str] = None, parent_id: Optional[str] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.gallery_name = gallery_name
        self.parent_id = parent_id

        # Store state for undo
        self.created_gallery_id = None
        self.created_gallery = None
        self.project = None

    @override
    def execute(self) -> bool:
        """Execute the create image gallery command."""
        try:
            self.logger.info("Executing CreateImageGalleryCommand")
            if not self.app_state.has_project:
                self.ui_controller.show_warning_message(
                    "Create Image Gallery",
                    "Please open or create a project first."
                )
                return False

            self.project = self.app_state.current_project
            if not self.project:
                self.logger.warning(
                    "CreateImageGalleryCommand.execute: has_project is True but current_project is None"
                )
                return False

            if not self.gallery_name:
                existing_galleries = [item for item in self.project.get_all_items()
                                       if isinstance(item, ImageGallery)]
                gallery_count = len(existing_galleries) + 1
                gallery_name = f"New Image Gallery {gallery_count}"
            else:
                gallery_name = self.gallery_name.strip()

            if not gallery_name:
                self.logger.warning(
                    "CreateImageGalleryCommand.execute: gallery name is empty (parent_id=%s)", self.parent_id
                )
                self.ui_controller.show_warning_message(
                    "Create Image Gallery",
                    "Gallery name cannot be empty."
                )
                return False

            self.created_gallery_id = str(uuid.uuid4())
            self.created_gallery = ImageGallery(
                id=self.created_gallery_id,
                name=gallery_name
            )

            self.project.add_item(self.created_gallery, parent_id=self.parent_id)

            self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                "project": self.project,
                "gallery_id": self.created_gallery_id,
                "gallery_name": gallery_name,
                "parent_id": self.parent_id,
                "gallery": self.created_gallery
            })
            self.logger.info(
                "CreateImageGalleryCommand: Created gallery '%s' (id=%s) under parent %s",
                gallery_name, self.created_gallery_id, self.parent_id or "root"
            )
            return True

        except Exception as e:
            error_msg = f"Failed to create image gallery: {str(e)}"
            self.logger.error("CreateImageGalleryCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Create Image Gallery Error", error_msg)
            return False

    @override
    def undo(self):
        """Undo the create image gallery command."""
        try:
            if self.created_gallery_id and self.app_state.has_project:
                project = self.app_state.current_project
                if project:
                    gallery = project.find_item(self.created_gallery_id)
                    if gallery is not None:
                        project.remove_item(gallery)

                    self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
                        "project": project,
                        "gallery_id": self.created_gallery_id,
                        "gallery": self.created_gallery
                    })
                    self.logger.info(
                        "CreateImageGalleryCommand: Undo creation of gallery id=%s (name=%s)",
                        self.created_gallery_id,
                        getattr(self.created_gallery, "name", "<unknown>")
                    )

        except Exception as e:
            error_msg = f"Failed to undo create image gallery: {str(e)}"
            self.logger.error("CreateImageGalleryCommand Undo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)

    @override
    def redo(self):
        """Redo the create image gallery command."""
        try:
            if self.created_gallery_id and self.created_gallery is not None and self.app_state.has_project:
                project = self.app_state.current_project
                if not project:
                    self.logger.warning(
                        "CreateImageGalleryCommand.redo: has_project is True but current_project is None"
                    )
                    return False

                project.add_item(self.created_gallery, parent_id=self.parent_id)

                self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                    "project": project,
                    "gallery_id": self.created_gallery_id,
                    "gallery_name": self.created_gallery.name,
                    "parent_id": self.parent_id,
                    "gallery": self.created_gallery
                })
                self.logger.info(
                    "CreateImageGalleryCommand: Redo creation of gallery '%s' (id=%s) under parent %s",
                    self.created_gallery.name, self.created_gallery_id, self.parent_id or "root"
                )
                return True
            else:
                return False

        except Exception as e:
            error_msg = f"Failed to redo create image gallery: {str(e)}"
            self.logger.error("CreateImageGalleryCommand Redo Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return False

    @override
    def cleanup(self) -> None:
        """Release the cached project reference held during creation once
        this command is dropped from the stacks for good (see
        Command.cleanup)."""
        self.project = None
