import json
import logging
from typing import override
from zipfile import ZipFile

from pandaplot.models.project.items.image import Image, normalize_render_dpi
from pandaplot.storage.item_data_manager import ItemDataManager


class ImageDataManager(ItemDataManager[Image]):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @override
    def save(self, item: Image, zip_file: ZipFile, path_in_zip: str) -> None:
        """
        Save image metadata as JSON, plus the raw image bytes when
        storage_mode is "copied". path_in_zip is without extension.
        """
        self.logger.debug("Saving image '%s' (ID: %s) to path: %s", item.name, item.id, path_in_zip)

        if item.storage_mode == "copied":
            data = item.get_bytes()
            if data is None:
                self.logger.warning(
                    "Image '%s' (ID: %s) has storage_mode='copied' but no bytes in memory; "
                    "skipping blob write, only metadata will be saved",
                    item.name, item.id
                )
            else:
                blob_path = f"{path_in_zip}.{item.image_ext}"
                zip_file.writestr(blob_path, data)

        metadata = {
            "id": item.id,
            "name": item.name,
            "parent_id": item.parent_id,
            "created_at": item.created_at,
            "modified_at": item.modified_at,
            "metadata": item.metadata,
            "source_file": item.source_file,
            "storage_mode": item.storage_mode,
            "image_ext": item.image_ext,
            "width": item.width,
            "height": item.height,
            "size_bytes": item.size_bytes,
            "note_id": item.note_id,
            "source_chart_id": item.source_chart_id,
            "render_dpi": item.render_dpi,
        }
        zip_file.writestr(f"{path_in_zip}.json", json.dumps(metadata, indent=2))
        self.logger.info("Successfully saved image '%s' (ID: %s)", item.name, item.id)

    @override
    def load(self, item_class: type[Image], zip_file: ZipFile, path_in_zip: str, schema_version: int) -> Image:
        """Load image metadata, plus its bytes when storage_mode is "copied"."""
        self.logger.debug("Loading image from path: %s", path_in_zip)

        metadata = json.loads(zip_file.read(f"{path_in_zip}.json").decode("utf-8"))

        image = item_class(
            id=metadata.get("id"),
            name=metadata.get("name", ""),
            source_file=metadata.get("source_file", ""),
            storage_mode=metadata.get("storage_mode", "copied"),
            image_ext=metadata.get("image_ext", ""),
            width=metadata.get("width", 0),
            height=metadata.get("height", 0),
            size_bytes=metadata.get("size_bytes"),
            note_id=metadata.get("note_id"),
            source_chart_id=metadata.get("source_chart_id"),
            render_dpi=normalize_render_dpi(metadata.get("render_dpi")),
        )
        image.parent_id = metadata.get("parent_id")
        image.created_at = metadata.get("created_at", image.created_at)
        image.modified_at = metadata.get("modified_at", image.created_at)
        image.metadata = metadata.get("metadata", {})

        if image.storage_mode == "copied":
            blob_path = f"{path_in_zip}.{image.image_ext}"
            if blob_path in zip_file.namelist():
                image.set_bytes(zip_file.read(blob_path))
            else:
                self.logger.warning(
                    "Blob file '%s' not found for image '%s' (ID: %s); bytes will be None",
                    blob_path, image.name, image.id
                )

        self.logger.info("Successfully loaded image '%s' (ID: %s)", image.name, image.id)
        return image
