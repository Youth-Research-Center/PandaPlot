import json
import logging
import pandas as pd
from typing import override

from pandaplot.storage.item_data_manager import ItemDataManager


class DatasetDataManager(ItemDataManager):
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    @override
    def save(self, item, zip_file, path_in_zip: str) -> None:
        """
        Save dataset metadata as JSON and data as CSV.
        path_in_zip should be without extension, e.g. 'items/<id>'
        """
        self.logger.debug("Saving dataset '%s' (ID: %s) to path: %s", item.name, item.id, path_in_zip)
        
        try:
            # Save DataFrame as CSV if data exists
            if item.data is not None:
                csv_path = f"{path_in_zip}.csv"
                self.logger.debug("Saving dataset data to CSV: %s (shape: %s)", csv_path, item.data.shape)
                csv_data = item.data.to_csv(index=False)
                zip_file.writestr(csv_path, csv_data)
            else:
                self.logger.debug("Dataset '%s' has no data to save", item.name)

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
            
            self.logger.debug("Saving dataset metadata for '%s'", item.name)
        except Exception as e:
            self.logger.error("Failed to save dataset '%s' (ID: %s): %s", item.name, item.id, str(e), exc_info=True)
            raise
        
        # Save metadata as JSON
        json_path = f"{path_in_zip}.json"
        self.logger.debug("Saving dataset metadata to: %s", json_path)
        zip_file.writestr(json_path, json.dumps(metadata, indent=2))
        self.logger.info("Successfully saved dataset '%s' (ID: %s)", item.name, item.id)

    @override
    def load(self, item_class, zip_file, path_in_zip: str):
        """
        Load dataset from CSV data + metadata JSON.
        path_in_zip is without extension.
        """
        self.logger.debug("Loading dataset from path: %s", path_in_zip)
        
        try:
            # Read metadata
            json_path = f"{path_in_zip}.json"
            self.logger.debug("Reading dataset metadata from: %s", json_path)
            metadata = json.loads(zip_file.read(json_path).decode('utf-8'))

            dataset_name = metadata.get("name", "Unknown")
            dataset_id = metadata.get("id", "Unknown")
            
            # Read CSV data if it exists
            data = None
            if metadata.get("has_data", False):
                try:
                    csv_path = f"{path_in_zip}.csv"
                    self.logger.debug("Reading dataset data from: %s", csv_path)
                    csv_content = zip_file.read(csv_path).decode('utf-8')
                    # Use StringIO to read CSV from string
                    from io import StringIO
                    data = pd.read_csv(StringIO(csv_content))
                    self.logger.debug("Loaded dataset data with shape: %s", data.shape)
                except KeyError:
                    # CSV file doesn't exist, data will be None
                    self.logger.warning("CSV file not found for dataset '%s', data will be None", dataset_name)
                    pass
            else:
                self.logger.debug("Dataset '%s' has no data to load", dataset_name)

            # Reconstruct dataset
            self.logger.debug("Reconstructing dataset object for '%s'", dataset_name)
            dataset = item_class(
                id=dataset_id,
                name=dataset_name,
                data=data,
                source_file=metadata.get("source_file")
            )
            
            self.logger.info("Successfully loaded dataset '%s' (ID: %s)", dataset_name, dataset_id)
            return dataset
            
        except Exception as e:
            self.logger.error("Failed to load dataset from %s: %s", path_in_zip, str(e), exc_info=True)
            raise
        
        # Set inherited attributes
        dataset.parent_id = metadata.get("parent_id")
        dataset.created_at = metadata.get("created_at")
        dataset.modified_at = metadata.get("modified_at")
        dataset.metadata = metadata.get("metadata", {})
        
        return dataset
