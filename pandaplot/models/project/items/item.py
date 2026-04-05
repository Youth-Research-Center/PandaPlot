import uuid
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional


class Item:
    """Base class for all project items."""
    
    def __init__(self, id: Optional[str] = None, name: str = ""):
        self.id: str = id if id else str(uuid.uuid4())
        self.name: str = name
        self.parent_id: Optional[str] = None
        self.created_at: str = datetime.now().isoformat()
        self.modified_at: str = self.created_at
        self.metadata: Dict[str, Any] = {}
    
    def update_modified_time(self):
        """Update the modification timestamp."""
        self.modified_at = datetime.now().isoformat()
    
    def update_name(self, new_name: str) -> None:
        """Update the note name and modification timestamp."""
        self.name = new_name
        self.update_modified_time()

    def to_dict(self) -> Dict[str, Any]:
        """Convert item to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "parent_id": self.parent_id,
            "created_at": self.created_at,
            "modified_at": self.modified_at,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Item":
        """Create item from dictionary."""
        item = cls(
            id=data.get("id"),
            name=data.get("name", "")
        )
        item.parent_id = data.get("parent_id")
        item.created_at = data.get("created_at", datetime.now().isoformat())
        item.modified_at = data.get("modified_at", item.created_at)
        item.metadata = data.get("metadata", {})
        return item
    
    def __str__(self):
        return f"{self.__class__.__name__}(id='{self.id}', name='{self.name}')"
    
    def __repr__(self):
        return self.__str__()

class ItemCollection(Item):
    """Collection item that can contain other items (like folders)."""
    
    def __init__(self, id: Optional[str] = None, name: str = "Collection"):
        super().__init__(id, name)
        self.items = OrderedDict()

    def __iter__(self):
        return iter(self.items.values())
    
    def add_item(self, item: Item):
        """Add an item to this collection."""
        self.items[item.id] = item
        item.parent_id = self.id
        self.update_modified_time()

    def remove_item(self, item: Item):
        """Remove an item from this collection."""
        if item.id in self.items:
            del self.items[item.id]
            item.parent_id = None
            self.update_modified_time()
    
    def remove_item_by_id(self, item_id: str):
        """Remove an item by ID from this collection."""
        if item_id in self.items:
            item = self.items[item_id]
            del self.items[item_id]
            item.parent_id = None
            self.update_modified_time()

    def get_item_by_id(self, item_id: str) -> Optional[Item]:
        """Get an item by ID from this collection."""
        return self.items.get(item_id)

    def get_items(self) -> List[Item]:
        """Get all items in this collection."""
        return list(self.items.values())
    
    def __len__(self):
        """Get total number of items including sub-collections."""
        num_items = 0
        for item in self.items.values():
            if isinstance(item, ItemCollection):
                num_items += len(item)
            else:
                num_items += 1
        return num_items
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert collection to dictionary for serialization."""
        data = super().to_dict()
        data["items"] = [item.to_dict() for item in self.items.values()]
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ItemCollection":
        """Create collection from dictionary."""
        # TODO: We should consider getting rid of this method, or changing the scope
        collection = cls(
            id=data.get("id"),
            name=data.get("name", "Collection")
        )
        collection.parent_id = data.get("parent_id")
        collection.created_at = data.get("created_at", datetime.now().isoformat())
        collection.modified_at = data.get("modified_at", collection.created_at)
        collection.metadata = data.get("metadata", {})

        # TODO: Parse nested items when their specific types are implemented
        return collection