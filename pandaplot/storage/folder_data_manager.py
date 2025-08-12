

import json
from typing import override
from pandaplot.storage.item_data_manager import ItemDataManager


class FolderDataManager(ItemDataManager):
    @override
    def save(self, item, zip_file, path_in_zip: str) -> None:
        """
        Save folder metadata as JSON.
        path_in_zip should be without extension, e.g. 'items/<id>'
        """
        # Save content as Markdown
        zip_file.writestr(f"{path_in_zip}.md", item.content or "")

        # Prepare metadata (excluding full content)
        metadata = item.to_dict()
        zip_file.writestr(f"{path_in_zip}.json", json.dumps(metadata, indent=2))

    @override
    def load(self, item_class, zip_file, path_in_zip: str):
        """Read and deserialize item data from given path in the zip."""+
        # Read metadata
        metadata = json.loads(zip_file.read(
            f"{path_in_zip}.json").decode('utf-8'))

        # Reconstruct folder
        # TODO: problem with reconstructing folder is that it needs to reference specific object 
        # instances and not recreate new ones
        folder = item_class(
            id=metadata.get("id"),
            name=metadata.get("name", "")
        )
        folder.parent_id = metadata.get("parent_id")
        folder.created_at = metadata.get("created_at")
        folder.modified_at = metadata.get("modified_at")
        folder.metadata = metadata.get("metadata", {})
        return folder
