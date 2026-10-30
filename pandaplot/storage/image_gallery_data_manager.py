import json
from typing import override
from zipfile import ZipFile

from pandaplot.models.project.items.image import ImageGallery
from pandaplot.storage.item_data_manager import ItemDataManager


class ImageGalleryDataManager(ItemDataManager[ImageGallery]):
    @override
    def save(self, item: ImageGallery, zip_file: ZipFile, path_in_zip: str) -> None:
        """
        Save image gallery metadata as JSON. path_in_zip is without extension.
        Children (Image / nested ImageGallery albums) are saved as their own
        independent items by ProjectDataManager, not here.
        """
        metadata = item.to_dict()
        zip_file.writestr(f"{path_in_zip}.json", json.dumps(metadata, indent=2))

    @override
    def load(self, item_class: type[ImageGallery], zip_file: ZipFile, path_in_zip: str, schema_version: int) -> ImageGallery:
        """Read and deserialize image gallery metadata from the given path."""
        metadata = json.loads(zip_file.read(f"{path_in_zip}.json").decode("utf-8"))

        gallery = item_class(
            id=metadata.get("id"),
            name=metadata.get("name", ""),
        )
        gallery.parent_id = metadata.get("parent_id")
        gallery.created_at = metadata.get("created_at", gallery.created_at)
        gallery.modified_at = metadata.get("modified_at", gallery.created_at)
        gallery.metadata = metadata.get("metadata", {})
        return gallery
