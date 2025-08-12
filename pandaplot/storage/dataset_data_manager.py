import json
import pandas as pd
from typing import override

from pandaplot.storage.item_data_manager import ItemDataManager


class DatasetDataManager(ItemDataManager):
    @override
    def save(self, item, zip_file, path_in_zip: str) -> None:
        """
        Save dataset metadata as JSON and data as CSV.
        path_in_zip should be without extension, e.g. 'items/<id>'
        """
        # Save DataFrame as CSV if data exists
        if item.data is not None:
            csv_data = item.data.to_csv(index=False)
            zip_file.writestr(f"{path_in_zip}.csv", csv_data)

        # Prepare metadata (excluding the actual DataFrame)
        metadata = {
            "id": item.id,
            "name": item.name,
            "parent_id": item.parent_id,
            "created_at": item.created_at,
            "modified_at": item.modified_at,
            "metadata": item.metadata,
            "source_file": item.source_file,
            "has_data": item.data is not None
        }
        
        # Save metadata as JSON
        zip_file.writestr(f"{path_in_zip}.json", json.dumps(metadata, indent=2))

    @override
    def load(self, item_class, zip_file, path_in_zip: str):
        """
        Load dataset from CSV data + metadata JSON.
        path_in_zip is without extension.
        """
        # Read metadata
        metadata = json.loads(zip_file.read(
            f"{path_in_zip}.json").decode('utf-8'))

        # Read CSV data if it exists
        data = None
        if metadata.get("has_data", False):
            try:
                csv_content = zip_file.read(f"{path_in_zip}.csv").decode('utf-8')
                # Use StringIO to read CSV from string
                from io import StringIO
                data = pd.read_csv(StringIO(csv_content))
            except KeyError:
                # CSV file doesn't exist, data will be None
                pass

        # Reconstruct dataset
        dataset = item_class(
            id=metadata.get("id"),
            name=metadata.get("name", ""),
            data=data,
            source_file=metadata.get("source_file")
        )
        
        # Set inherited attributes
        dataset.parent_id = metadata.get("parent_id")
        dataset.created_at = metadata.get("created_at")
        dataset.modified_at = metadata.get("modified_at")
        dataset.metadata = metadata.get("metadata", {})
        
        return dataset
