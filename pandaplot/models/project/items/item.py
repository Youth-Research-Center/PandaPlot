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
    
    def add_item(self, item: Item, index: Optional[int] = None):
        """Add an item to this collection.

        By default the item is appended after existing siblings. When
        `index` is given, it's inserted at that position instead -- used to
        restore an item's exact prior sibling position (e.g. when a move's
        compensating rollback re-adds an item to the parent it just came
        from, see #374).
        """
        item.parent_id = self.id
        if index is None or index >= len(self.items):
            self.items[item.id] = item
        else:
            pairs = list(self.items.items())
            pairs.insert(index, (item.id, item))
            self.items = OrderedDict(pairs)
        self.update_modified_time()

    def remove_item(self, item: Item) -> Optional[int]:
        """Remove an item from this collection.

        Returns the index the item held among its siblings (or None if it
        wasn't a member), so callers can later restore its exact position
        with add_item(index=...).
        """
        if item.id not in self.items:
            return None
        index = list(self.items.keys()).index(item.id)
        del self.items[item.id]
        item.parent_id = None
        self.update_modified_time()
        return index
    
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
        # TODO(#219): We should consider getting rid of this method, or changing the scope
        collection = cls(
            id=data.get("id"),
            name=data.get("name", "Collection")
        )
        collection.parent_id = data.get("parent_id")
        collection.created_at = data.get("created_at", datetime.now().isoformat())
        collection.modified_at = data.get("modified_at", collection.created_at)
        collection.metadata = data.get("metadata", {})

        # TODO(#219): Parse nested items when their specific types are implemented
        return collection