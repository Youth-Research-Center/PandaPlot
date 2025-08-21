import logging
import zipfile
import json

from pandaplot.models.project.items.item import Item
from pandaplot.models.project.project import Project
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory


class ProjectDataManager:
    def __init__(self, item_data_manager_factory: ItemDataManagerFactory):
        self.data_factory = item_data_manager_factory
        self.logger = logging.getLogger(__name__)

    def save(self, project: Project, filepath: str):
        self.logger.info(f"Saving project {project.name} to {filepath}")
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
        self.logger.info(f"Loading project from {filepath}")
        with zipfile.ZipFile(filepath, 'r') as zf:
            project_dict = json.loads(zf.read("project.json").decode('utf-8'))
            project = Project.from_dict(project_dict)

            items_info = project_dict.get("item_files", {}).items()
            items = {}

            # Load all of the items
            for item_id, info in items_info:
                curr_item = self._load_item(item_id, info, zf)
                if curr_item is not None:
                    items[item_id] = curr_item

            project_tree = project_dict.get("root", {}).get("items", [])
            self._add_items_to_project(project, items, project_tree)

        return project

    def _load_item(self, item_id: str, info, zip_file) -> Item | None:
        try:
            item_class = self.data_factory.resolve_item_class(info["type"])
            path = info["path"]
            manager = self.data_factory.get_manager(info["type"])

            item = manager.load(item_class, zip_file, path)
            self.logger.info(
                f"Loaded item {item_id} of type {info['type']} from {path}")
            return item
        except Exception as ex:
            self.logger.error(f"Failed to load item {item_id}: {ex}")

    def _add_items_to_project(self, project: Project, items: dict[str, Item], project_tree: list[dict]) -> None:
        """Recursively add items to the project based on the project tree structure."""
        for node in project_tree:
            item_id = node.get("id")
            if item_id in items:
                project.add_item(
                    items[item_id], parent_id=node.get("parent_id"))

            if node.get("items", None) is not None:
                # Recur for children
                self._add_items_to_project(
                    project, items, node.get("items", []))
