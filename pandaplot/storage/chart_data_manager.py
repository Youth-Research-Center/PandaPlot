import json
from typing import override

from pandaplot.storage.item_data_manager import ItemDataManager


class ChartDataManager(ItemDataManager):
    @override
    def save(self, item, zip_file, path_in_zip: str) -> None:
        """
        Save chart configuration and metadata as JSON.
        path_in_zip should be without extension, e.g. 'items/<id>'
        """
        # Convert chart to dictionary for serialization
        chart_data = item.to_dict()
        
        # Save as JSON
        zip_file.writestr(f"{path_in_zip}.json", json.dumps(chart_data, indent=2))

    @override
    def load(self, item_class, zip_file, path_in_zip: str):
        """
        Load chart from JSON configuration.
        path_in_zip is without extension.
        """
        # Read JSON data
        chart_data = json.loads(zip_file.read(
            f"{path_in_zip}.json").decode('utf-8'))

        # Reconstruct chart using from_dict class method
        chart = item_class.from_dict(chart_data)
        return chart
