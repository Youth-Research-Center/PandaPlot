"""
Image and ImageGallery models for the image-gallery feature.

An ImageGallery is a thin ItemCollection, structurally identical to Folder.
It is reused both for top-level "Image Gallery" tree nodes and for nested
"albums" -- an album is simply an ImageGallery nested inside another
ImageGallery. There is no separate Album class.
"""

from datetime import datetime
from typing import Any

from pandaplot.models.project.items.item import Item, ItemCollection


class Image(Item):
    """
    Represents a single image in an image gallery.

    storage_mode is "copied" (bytes stored inside the project zip by
    ImageDataManager) or "external" (source_file is a local path or a URL;
    only the reference is stored). width/height are captured at import time
    so the gallery grid can lay out tiles before decoding the image. The raw
    bytes (when storage_mode == "copied") live only in memory via
    set_bytes/get_bytes -- they are never part of to_dict, mirroring how
    Dataset.data is excluded from its to_dict.
    """

    def __init__(self, id: str | None = None, name: str = "",
                 source_file: str = "", storage_mode: str = "copied",
                 image_ext: str = "", width: int = 0, height: int = 0,
                 size_bytes: int | None = None):
        super().__init__(id, name)
        self.source_file = source_file
        self.storage_mode = storage_mode
        self.image_ext = image_ext
        self.width = width
        self.height = height
        self.size_bytes = size_bytes
        self._bytes: bytes | None = None

    def set_bytes(self, data: bytes | None) -> None:
        """Set the in-memory raw image bytes (only meaningful when storage_mode == 'copied')."""
        self._bytes = data

    def get_bytes(self) -> bytes | None:
        """Return the in-memory raw image bytes, or None if not loaded/copied."""
        return self._bytes

    def to_dict(self) -> dict[str, Any]:
        """Convert image to dictionary for serialization."""
        data = super().to_dict()
        data.update({
            "source_file": self.source_file,
            "storage_mode": self.storage_mode,
            "image_ext": self.image_ext,
            "width": self.width,
            "height": self.height,
            "size_bytes": self.size_bytes,
        })
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Image":
        """Create image from dictionary."""
        image = cls(
            id=data.get("id"),
            name=data.get("name", ""),
            source_file=data.get("source_file", ""),
            storage_mode=data.get("storage_mode", "copied"),
            image_ext=data.get("image_ext", ""),
            width=data.get("width", 0),
            height=data.get("height", 0),
            size_bytes=data.get("size_bytes"),
        )
        image.parent_id = data.get("parent_id")
        image.created_at = data.get("created_at", datetime.now().isoformat())  # noqa: DTZ005 -- local-time display bookkeeping, never compared across timezones
        image.modified_at = data.get("modified_at", image.created_at)
        image.metadata = data.get("metadata", {})
        return image


class ImageGallery(ItemCollection):
    """
    Represents an image gallery (or, nested inside another ImageGallery, an
    album) in the project hierarchy. Holds Image items and/or other
    ImageGallery items (albums) via the inherited ItemCollection behavior.
    """

    def __init__(self, id: str | None = None, name: str = "New Image Gallery"):
        super().__init__(id, name)
