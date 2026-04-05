import json
import logging
import zipfile

from pandaplot.models.project import Project
from pandaplot.models.project.items import Item
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory


class _ZipBytesProxy:
    """Mimics zipfile.ZipFile.read() using pre-loaded bytes so managers need no changes."""
    def __init__(self, raw_data: dict):
        self._raw_data = raw_data

    def read(self, path: str) -> bytes:
        return self._raw_data[path]


class ProjectDataManager:
    def __init__(self, item_data_manager_factory: ItemDataManagerFactory):
        self.data_factory = item_data_manager_factory
        self.logger = logging.getLogger(self.__class__.__name__)

    def save(self, project: Project, filepath: str):
        self.logger.info(f"Saving project {project.name} to {filepath}")
        with zipfile.ZipFile(filepath, "w", compression=zipfile.ZIP_DEFLATED) as zf:
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

        # Phase 1: Read all raw bytes while the zip is open.
        # The file is held open only during this block; closing it immediately
        # prevents the Windows exclusive-lock window that would otherwise last
        # until all processing (Project.from_dict, item deserialization, …) finishes.
        with zipfile.ZipFile(filepath, "r") as zf:
            names = set(zf.namelist())
            if "project.json" not in names:
                raise ValueError(f"Invalid project file: missing project.json in {filepath}")
            raw_data = {name: zf.read(name) for name in names}
        # ← zip closed here; Windows file lock released before any deserialization

        # Phase 2: Deserialize entirely from in-memory bytes (no file lock held).
        zip_proxy = _ZipBytesProxy(raw_data)
        project_dict = json.loads(raw_data["project.json"].decode("utf-8"))
        project = Project.from_dict(project_dict)

        items = {}
        for item_id, info in project_dict.get("item_files", {}).items():
            curr_item = self._load_item(item_id, info, zip_proxy)
            if curr_item is not None:
                items[item_id] = curr_item

        project_root = project_dict.get("root", {})
        project.root.id = project_root.get("id", project.root.id)
        self._add_items_to_project(project, items, project_root.get("items", []))
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
