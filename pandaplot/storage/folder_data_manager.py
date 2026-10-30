import json
from typing import override
from zipfile import ZipFile

from pandaplot.models.project.items.folder import Folder
from pandaplot.storage.item_data_manager import ItemDataManager


class FolderDataManager(ItemDataManager[Folder]):
    @override
    def save(self, item: Folder, zip_file: ZipFile, path_in_zip: str) -> None:
        """
        Save folder metadata as JSON.
        path_in_zip should be without extension, e.g. 'items/<id>'
        """
        # Prepare metadata (excluding full content)
        metadata = item.to_dict()
        zip_file.writestr(f"{path_in_zip}.json", json.dumps(metadata, indent=2))

    @override
    def load(self, item_class: type[Folder], zip_file: ZipFile, path_in_zip: str, schema_version: int) -> Folder:
        """Read and deserialize item data from given path in the zip."""
        # Read metadata
        metadata = json.loads(zip_file.read(
            f"{path_in_zip}.json").decode("utf-8"))

        # Reconstruct folder
        # We aren't loading items as they will get loaded independently
        folder = item_class(
            id=metadata.get("id"),
            name=metadata.get("name", "")
        )
        folder.parent_id = metadata.get("parent_id")
        folder.created_at = metadata.get("created_at", folder.created_at)
        folder.modified_at = metadata.get("modified_at", folder.created_at)
        folder.metadata = metadata.get("metadata", {})
        return folder
