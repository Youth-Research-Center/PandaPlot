import json
from typing import override
from zipfile import ZipFile

from pandaplot.models.migrations.per_item.sketch import migrate_sketch
from pandaplot.models.project.items.sketch import Sketch
from pandaplot.storage.item_data_manager import ItemDataManager


class SketchDataManager(ItemDataManager[Sketch]):
    @override
    def save(self, item: Sketch, zip_file: ZipFile, path_in_zip: str) -> None:
        """
        Save the sketch (layers and elements) as JSON.
        path_in_zip should be without extension, e.g. 'items/<id>'
        """
        zip_file.writestr(f"{path_in_zip}.json", json.dumps(item.to_dict(), indent=2))

    @override
    def load(self, item_class: type[Sketch], zip_file: ZipFile, path_in_zip: str, schema_version: int) -> Sketch:
        """
        Load a sketch from JSON, migrating it from schema_version first.
        path_in_zip is without extension.
        """
        sketch_data = json.loads(zip_file.read(f"{path_in_zip}.json").decode("utf-8"))
        sketch_data = migrate_sketch(sketch_data, schema_version)
        return item_class.from_dict(sketch_data)
