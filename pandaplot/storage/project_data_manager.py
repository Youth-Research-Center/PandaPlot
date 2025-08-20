import logging
import zipfile
import json
from typing import Optional

from pandaplot.models.project.items.item import Item, ItemCollection
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

            # Load hierarchy from root structure if available
            root_data = project_dict.get("root")
            if root_data:
                self.logger.info("Loading project hierarchy from root structure")
                # Load root and recursively build the hierarchy
                self._load_hierarchy_from_root(root_data, project, zf)
            else:
                # Fallback to the old method if root structure is not available
                self.logger.warning("No root structure found, falling back to individual item loading")
                self._load_items_individually(project_dict, project, zf)

        return project

    def _load_hierarchy_from_root(self, root_data: dict, project: Project, zf: zipfile.ZipFile):
        """Load the complete project hierarchy from root structure."""
        # The root data contains the full hierarchy structure
        # We need to recursively load all items and their children
        self.logger.debug("Loading root collection")
        
        # Update root properties from saved data
        if 'name' in root_data:
            project.root.name = root_data['name']
        if 'id' in root_data:
            project.root.id = root_data['id']
        
        # First get the item_files mapping for file-based loading
        project_dict = json.loads(zf.read("project.json").decode('utf-8'))
        item_files = project_dict.get("item_files", {})
        
        # Recursively load all items in the hierarchy
        if 'items' in root_data:
            for item_data in root_data['items']:
                item = self._load_item_from_hierarchy(item_data, project, zf, item_files, project.root.id)
                if item:
                    project.add_item(item, parent_id=project.root.id)

    def _load_item_from_hierarchy(self, item_data: dict, project: Project, zf: zipfile.ZipFile, item_files: dict, parent_id: str) -> Optional[Item]:
        """Recursively load an item and its children from hierarchy data."""
        try:
            item_id = item_data.get('id')
            if not item_id:
                self.logger.error("Item data missing ID field")
                return None
            
            # Check if we have a separate file for this item
            if item_id in item_files:
                # Load using the individual data manager (for datasets, charts, etc.)
                file_info = item_files[item_id]
                item_type = file_info["type"]
                file_path = file_info["path"]
                
                item_class = self.data_factory.resolve_item_class(item_type)
                manager = self.data_factory.get_manager(item_type)
                
                # Extract base path for the data manager
                # file_path is like "items/abc123.json" or "items/abc123.csv"
                # we need to pass "items/abc123" to the manager
                base_path = file_path.rsplit('.', 1)[0]  # Remove extension
                
                self.logger.debug(f"Loading item {item_id} from file path: {file_path} -> base: {base_path}")
                item = manager.load(item_class, zf, base_path)
                self.logger.debug(f"Loaded item {item_id} of type {item_type} using data manager")
            else:
                # Fallback: Load from hierarchy data (for simple items like folders)
                item_type = self._determine_item_type(item_data)
                item_class = self.data_factory.resolve_item_class(item_type)
                item = item_class.from_dict(item_data)
                self.logger.debug(f"Loaded item {item_id} of type {item_type} from hierarchy data")
            
            # Set the parent_id from the hierarchy structure
            item.parent_id = parent_id
            
            # If this is a collection, recursively load its children
            if isinstance(item, ItemCollection) and 'items' in item_data:
                for child_data in item_data['items']:
                    child_item = self._load_item_from_hierarchy(child_data, project, zf, item_files, item.id)
                    if child_item:
                        # Add child directly to this collection
                        item.add_item(child_item)
                        # Also add to project index
                        project.items_index[child_item.id] = child_item
            
            # Add to project index
            project.items_index[item.id] = item
            self.logger.debug(f"Successfully loaded item {item.id} with parent {parent_id}")
            
            return item
            
        except Exception as ex:
            self.logger.error(f"Failed to load item from hierarchy: {ex}")
            # Let's also print the available files for debugging
            try:
                available_files = zf.namelist()
                self.logger.debug(f"Available files in ZIP: {available_files}")
            except Exception:
                pass
            return None

    def _determine_item_type(self, item_data: dict) -> str:
        """Determine the item type from the item data structure."""
        # Check if the item data has a type field
        if 'type' in item_data:
            return item_data['type']
        
        # Fallback: determine type from class structure or properties
        if 'items' in item_data:
            return 'folder'  # or 'itemcollection'
        elif 'content' in item_data and 'tags' in item_data:
            return 'note'
        elif 'data_series' in item_data or 'chart_type' in item_data:
            return 'chart'
        elif 'data' in item_data or 'source_file' in item_data:
            return 'dataset'
        else:
            # Default to folder for collections
            return 'folder'

    def _load_items_individually(self, project_dict: dict, project: Project, zf: zipfile.ZipFile):
        """Fallback method to load items individually (old approach)."""
        items = project_dict.get("item_files", {}).items()
        loaded_items: set[str] = set()

        # Load collection items first to ensure parent containers exist
        for item_id, info in items:
            item_class = self.data_factory.resolve_item_class(info["type"])
            if not issubclass(item_class, ItemCollection):
                continue
            self._load_item(item_id, info, item_class, zf, project, loaded_items)

        # Load other items
        for item_id, info in items:
            if item_id in loaded_items:
                continue
            item_class = self.data_factory.resolve_item_class(info["type"])
            self._load_item(item_id, info, item_class, zf, project, loaded_items)

    def _load_item(self, item_id: str, info, item_class:type[Item], zip_file, project: Project, loaded_items: set[str]):
        try:
            path = info["path"]
            manager = self.data_factory.get_manager(info["type"])

            item = manager.load(item_class, zip_file, path)
            project.add_item(item, parent_id=item.parent_id)
            loaded_items.add(item_id)
            self.logger.info(f"Loaded item {item_id} of type {info['type']} from {path}")
        except Exception as ex:
            self.logger.error(f"Failed to load item {item_id}: {ex}")