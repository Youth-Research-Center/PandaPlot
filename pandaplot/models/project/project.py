
import logging
from typing import Dict, Any, List, Optional
from pandaplot.models.project.items import Item, ItemCollection

class Project:
    """
    Represents a project containing a hierarchical structure of items.
    
    The project uses a unified Item-based system where all content
    (notes, datasets, charts, folders) are items in a hierarchy.
    """
    
    def __init__(self, name: str = "Untitled Project", description: str = ""):
        self.logger = logging.getLogger(__name__)
        self.name = name
        self.description = description
        
        # Main project hierarchy - root is an ItemCollection
        self.root: ItemCollection = ItemCollection(name=f"{name} Root")
        
        # Flat lookup for quick item access by ID
        self.items_index: Dict[str, Item] = {}
        
        # Project metadata
        self.metadata: Dict[str, Any] = {}
        self.version = "1.0"
    
    def add_item(self, item: Item, parent_id: Optional[str] = None):
        """Add an item to the project hierarchy."""
        if parent_id is None:
            # Add to root
            self.root.add_item(item)
        else:
            # Find parent and add item there
            parent = self.find_item(parent_id)
            if parent is not None and isinstance(parent, ItemCollection):
                parent.add_item(item)
            else:
                self.logger.warning(f"Parent {parent_id} not found or not a collection, item: {item.id} {item.name} ")
                # If parent not found or not a collection, add to root
                # TODO: see if we need to handle this case differently, e.g. recursively search for a collection
                self.root.add_item(item)
        
        # Update index
        self.items_index[item.id] = item

    def remove_item(self, item: Item):
        """Remove an item from the project hierarchy."""
        if item.id == self.root.id:
            raise ValueError("Cannot remove the root item directly.")

        # If this is a collection, recursively remove all child items first
        if isinstance(item, ItemCollection):
            # Make a copy of the items list to avoid modification during iteration
            child_items = list(item.get_items())
            for child_item in child_items:
                self.remove_item(child_item)
        
        # Remove from parent
        if item.parent_id:
            # Check if parent is the root collection
            if item.parent_id == self.root.id:
                self.root.remove_item(item)
            else:
                # Find parent in the items index
                parent = self.find_item(item.parent_id)
                if parent and isinstance(parent, ItemCollection):
                    parent.remove_item(item)
        else:
            # No parent_id means it should be in root
            self.root.remove_item(item)
        
        # Remove from index
        if item.id in self.items_index:
            del self.items_index[item.id]
    
    def remove_item_by_id(self, item_id: str):
        """Remove an item by ID from the project."""
        if item_id == self.root.id:
            raise ValueError("Cannot remove the root item directly.")
        
        item = self.find_item(item_id)
        if item:
            self.remove_item(item)
    
    def find_item(self, item_id: str) -> Optional[Item]:
        """Find an item by ID in the project."""
        if item_id == self.root.id:
            return self.root
        return self.items_index.get(item_id)
    
    def get_all_items(self) -> List[Item]:
        """Get all items in the project (flat list)."""
        return list(self.items_index.values())
    
    def get_root_items(self) -> List[Item]:
        """Get items at the root level."""
        return self.root.get_items()
     
    def accept_visitor(self, visitor, parent_context=None):
        """
        Accept a visitor to traverse the project hierarchy.
        
        Args:
            visitor: The visitor object that implements visit methods
            parent_context: Optional context to pass to the visitor
            
        Returns:
            Result from the visitor
        """
        return visitor.build_tree(self.root, parent_context)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert project to dictionary for serialization."""
        return {
            'name': self.name,
            'description': self.description,
            'root': self.root.to_dict(),
            'metadata': self.metadata,
            'version': self.version
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        """Create project from dictionary."""
        project = cls(
            name=data.get('name', 'Untitled Project'),
            description=data.get('description', '')
        )
        project.metadata = data.get('metadata', {})
        project.version = data.get('version', '1.0')
        
        # TODO: Parse root hierarchy when item types are fully implemented
        return project
        
    def __str__(self):
        return f"Project(name='{self.name}', items={len(self.items_index)})"
        
    def __repr__(self):
        return self.__str__()