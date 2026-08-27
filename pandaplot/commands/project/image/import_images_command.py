"""
Command to import one or more images (local files or a URL) into an existing
image gallery, either copying the bytes into the project or storing just the
reference (a local path or URL) as an external image.
"""

import datetime
import os
import uuid
from typing import List, Optional, override

import requests
from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImageReader

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import Image, ImageGallery
from pandaplot.models.state import AppContext, AppState


def _is_url(source: str) -> bool:
    return source.startswith("http://") or source.startswith("https://")


class ImportImagesCommand(Command):
    """
    Command to import images into an image gallery.

    `sources` is a list of local file paths, or may contain a URL string for
    a web image.
    """

    def __init__(self, app_context: AppContext, gallery_id: str, sources: List[str],
                 *, copy_into_project: bool = True):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.gallery_id = gallery_id
        self.sources = sources
        self.copy_into_project = copy_into_project

        # Store state for undo
        self.created_image_ids: List[str] = []
        self.project = None

    @override
    def execute(self) -> bool:
        """Execute the import images command."""
        try:
            self.logger.info("Executing ImportImagesCommand for gallery %s", self.gallery_id)

            if not self.app_state.has_project:
                self.ui_controller.show_warning_message("Import Images", "Please open or create a project first.")
                return False

            self.project = self.app_state.current_project
            if not self.project:
                self.logger.warning(
                    "ImportImagesCommand.execute: has_project is True but current_project is None"
                )
                return False

            gallery = self.project.find_item(self.gallery_id)
            if not isinstance(gallery, ImageGallery):
                self.logger.warning(
                    "ImportImagesCommand.execute: gallery '%s' not found or not an ImageGallery (got %s)",
                    self.gallery_id, type(gallery).__name__ if gallery else None,
                )
                self.ui_controller.show_error_message(
                    "Import Images Error", f"Gallery '{self.gallery_id}' not found."
                )
                return False

            if not self.sources:
                self.logger.warning(
                    "ImportImagesCommand.execute: no sources given for gallery '%s'", self.gallery_id
                )
                self.ui_controller.show_warning_message("Import Images", "No images selected to import.")
                return False

            new_images = [self._build_image(source) for source in self.sources]

            for image in new_images:
                self.project.add_item(image, parent_id=self.gallery_id)
                self.created_image_ids.append(image.id)

                self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
                    "project": self.project,
                    "image_id": image.id,
                    "image_name": image.name,
                    "parent_id": self.gallery_id,
                    "image": image
                })

            self.logger.info(
                "ImportImagesCommand: Imported %d image(s) into gallery %s", len(new_images), self.gallery_id
            )
            return True

        except (FileNotFoundError, ValueError) as e:
            self.ui_controller.show_error_message("Import Images Error", str(e))
            self.logger.error("ImportImagesCommand Error: %s", e)
            return False
        except Exception as e:
            error_msg = f"Failed to import images: {str(e)}"
            self.logger.error("ImportImagesCommand Error: %s", error_msg, exc_info=True)
            self.ui_controller.show_error_message("Import Images Error", error_msg)
            return False

    def _build_image(self, source: str) -> Image:
        """Build one Image item from a local path or URL source."""
        data, ext, width, height = self._read_source_bytes_and_size(source)
        name = self._display_name(source)
        size_bytes = self._size_bytes_for(source, data)

        if self.copy_into_project:
            image = Image(
                id=str(uuid.uuid4()), name=name, source_file=source,
                storage_mode="copied", image_ext=ext, width=width, height=height,
                size_bytes=size_bytes,
            )
            image.set_bytes(data)
        else:
            image = Image(
                id=str(uuid.uuid4()), name=name, source_file=source,
                storage_mode="external", image_ext=ext, width=width, height=height,
                size_bytes=size_bytes,
            )

        self._apply_source_mtime(image, source)
        return image

    def _apply_source_mtime(self, image: Image, source: str) -> None:
        """
        Set modified_at/created_at from the local file's real mtime when
        available, so imported images reflect when the original photo was
        actually taken/modified rather than the import time. URL sources
        have no local mtime to read, so they keep the constructor-default
        "now" value.
        """
        if _is_url(source):
            return
        mtime_iso = datetime.datetime.fromtimestamp(os.path.getmtime(source)).isoformat()
        image.modified_at = mtime_iso
        image.created_at = mtime_iso

    def _size_bytes_for(self, source: str, data: bytes) -> Optional[int]:
        """
        Size in bytes for the list-view's Size column. For a URL we already
        downloaded `data` for width/height purposes only when copying; to
        avoid an extra network request just to learn a size, an
        external-mode URL import is left as None (rendered as "--" in the
        list view) rather than reusing the width/height-probe download's
        byte count, which conflates "we happened to fetch bytes" with
        "we're keeping them" -- copy mode's `data` IS the same content
        that gets stored, so len(data) is correct there regardless of
        source kind.
        """
        if self.copy_into_project:
            return len(data)
        if _is_url(source):
            return None
        return os.path.getsize(source)

    def _display_name(self, source: str) -> str:
        if _is_url(source):
            return os.path.splitext(os.path.basename(source.rstrip("/")))[0] or source
        return os.path.splitext(os.path.basename(source))[0]

    def _read_source_bytes_and_size(self, source: str):
        """
        Return (bytes, extension, width, height) for a local path or URL.

        Bytes are always read (even in "external" mode) so width/height can
        be captured without a second decode pass; only "copied" mode keeps
        them on the Image afterwards.
        """
        if _is_url(source):
            return self._read_url_bytes_and_size(source)

        if not os.path.isfile(source):
            raise FileNotFoundError(f"Image file not found: {source}")

        ext = os.path.splitext(source)[1].lstrip(".").lower()
        reader = QImageReader(source)
        size = reader.size()
        width, height = size.width(), size.height()
        if width <= 0 or height <= 0:
            raise ValueError(f"'{source}' is not a readable image file")

        with open(source, "rb") as f:
            data = f.read()

        return data, ext, width, height

    def _read_url_bytes_and_size(self, url: str):
        """Download image bytes from a URL and read its dimensions."""
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            raise ValueError(f"Failed to download image from '{url}': {e}") from e

        data = response.content
        ext = os.path.splitext(url.split("?")[0].rstrip("/"))[1].lstrip(".").lower() or "jpg"

        buffer = QBuffer()
        buffer.setData(QByteArray(data))
        buffer.open(QIODevice.OpenModeFlag.ReadOnly)
        reader = QImageReader(buffer)
        size = reader.size()
        width, height = size.width(), size.height()
        if width <= 0 or height <= 0:
            raise ValueError(f"URL '{url}' did not return a readable image")

        return data, ext, width, height

    def undo(self):
        """Undo the import images command by removing all created images."""
        try:
            if self.created_image_ids and self.app_state.has_project:
                project = self.app_state.current_project
                if project:
                    for image_id in self.created_image_ids:
                        image = project.find_item(image_id)
                        if image is not None:
                            project.remove_item(image)

                        self.app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
                            "project": project,
                            "image_id": image_id,
                        })

                    self.logger.info("Undone import of %d image(s)", len(self.created_image_ids))

        except Exception as e:
            error_msg = f"Failed to undo image import: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Undo Error", error_msg)

    def redo(self):
        """Redo the import by re-running execute() after clearing prior created ids."""
        try:
            if self.created_image_ids and self.app_state.has_project:
                self.created_image_ids = []
                return self.execute()
            return False
        except Exception as e:
            error_msg = f"Failed to redo image import: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.ui_controller.show_error_message("Redo Error", error_msg)
            return False

    @override
    def cleanup(self) -> None:
        """Release the created-image-id bookkeeping and cached project
        reference held for undo once this command is dropped from the
        stacks for good (see Command.cleanup)."""
        self.created_image_ids = []
        self.project = None
