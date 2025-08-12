import zipfile
import json

from pandaplot.models.project.items.item import ItemCollection
from pandaplot.models.project.project import Project
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory

class ProjectDataManager:
    def __init__(self, item_data_manager_factory: ItemDataManagerFactory):
        self.data_factory = item_data_manager_factory

    def save(self, project: Project, filepath: str):
        with zipfile.ZipFile(filepath, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            project_dict = project.to_dict()
            
            # Add item references (with paths to their separate files)
            for item in project.get_all_items():
                type_name = item.__class__.__name__.lower()
                item_file = f"items/{item.id}.{self.data_factory.get_extension_for_type(type_name)}"
                project_dict.setdefault("item_files", {})[item.id] = {
                    "type": type_name,
                    "path": item_file
                }
                manager = self.data_factory.get_manager(type_name)
                manager.save(item, zf, item_file)

            # Save project.json last
            zf.writestr("project.json", json.dumps(project_dict, indent=2))

    def load(self, filepath: str) -> Project:
        with zipfile.ZipFile(filepath, 'r') as zf:
            project_dict = json.loads(zf.read("project.json").decode('utf-8'))
            project = Project.from_dict(project_dict)

            items = project_dict.get("item_files", {}).items()
            loaded_items = set()
            

            # We need to first load all collection items to ensure parent id exists
            for item_id, info in items:
                type_name = info["type"]
                item_class = self.data_factory.resolve_item_class(type_name)
                
                if not issubclass(item_class, ItemCollection):
                    continue

                path = info["path"]
                manager = self.data_factory.get_manager(type_name)
                item = manager.load(item_class, zf, path)
                project.add_item(item, parent_id=item.parent_id)
                loaded_items.add(item_id)

            # Load other items
            for item_id, info in items:
                if item_id in loaded_items:
                    continue
                type_name = info["type"]
                path = info["path"]
                manager = self.data_factory.get_manager(type_name)

                item_class = self.data_factory.resolve_item_class(type_name)
                item = manager.load(item_class, zf, path)
                project.add_item(item, parent_id=item.parent_id)
                loaded_items.add(item_id)

        return project

