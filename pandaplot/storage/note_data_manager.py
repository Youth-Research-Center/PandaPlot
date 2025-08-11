import json
from typing import override

from pandaplot.storage.item_data_manager import ItemDataManager


class NoteDataManager(ItemDataManager):
    @override
    def save(self, item, zip_file, base_path: str) -> None:
        """
        Save note content as markdown, and metadata as JSON.
        base_path should be without extension, e.g. 'items/<id>'
        """
        # Save content as Markdown
        zip_file.writestr(f"{base_path}.md", item.content or "")

        # Prepare metadata (excluding full content)
        metadata = {
            "id": item.id,
            "name": item.name,
            "parent_id": item.parent_id,
            "tags": item.tags,
            "created_at": item.created_at,
            "modified_at": item.modified_at,
            "metadata": item.metadata
        }
        zip_file.writestr(f"{base_path}.json", json.dumps(metadata, indent=2))

    @override
    def load(self, item_class, zip_file, base_path: str):
        """
        Load note from markdown + metadata json.
        base_path is without extension.
        """
        # Read markdown content
        content = zip_file.read(f"{base_path}.md").decode('utf-8')

        # Read metadata
        metadata = json.loads(zip_file.read(
            f"{base_path}.json").decode('utf-8'))

        # Reconstruct note
        note = item_class(
            id=metadata.get("id"),
            name=metadata.get("name", ""),
            content=content,
            tags=metadata.get("tags", [])
        )
        note.parent_id = metadata.get("parent_id")
        note.created_at = metadata.get("created_at")
        note.modified_at = metadata.get("modified_at")
        note.metadata = metadata.get("metadata", {})
        return note
