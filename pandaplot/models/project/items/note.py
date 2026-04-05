"""
Note model for managing text-based note items in the project.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pandaplot.models.project.items import Item


class Note(Item):
    """
    Represents a note item in the project.
    
    A note contains text content that can be edited and saved.
    It's part of the hierarchical project structure.
    """
    
    def __init__(self, id: Optional[str] = None, name: str = "", content: str = "", 
                 tags: Optional[List[str]] = None):
        super().__init__(id, name)
        
        # Set note-specific attributes
        self.content = content
        self.tags = tags if tags is not None else []
    
    def update_content(self, new_content: str) -> None:
        """Update the note content and modification timestamp."""
        self.content = new_content
        self.update_modified_time()
    
    def add_tag(self, tag: str) -> None:
        """Add a tag to the note."""
        if tag not in self.tags:
            self.tags.append(tag)
            self.update_modified_time()
    
    def remove_tag(self, tag: str) -> None:
        """Remove a tag from the note."""
        if tag in self.tags:
            self.tags.remove(tag)
            self.update_modified_time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert note to dictionary for serialization."""
        data = super().to_dict()
        data.update({
            "content": self.content,
            "tags": self.tags
        })
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Note":
        """Create note from dictionary."""
        note = cls(
            id=data.get("id"),
            name=data.get("name", ""),
            content=data.get("content", ""),
            tags=data.get("tags", [])
        )
        # Set inherited attributes
        note.parent_id = data.get("parent_id")
        note.created_at = data.get("created_at", datetime.now().isoformat())
        note.modified_at = data.get("modified_at", note.created_at)
        note.metadata = data.get("metadata", {})
        return note
