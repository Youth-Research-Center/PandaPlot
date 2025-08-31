"""
Folder model for managing folder items in the project hierarchy.
"""

from typing import Optional
from pandaplot.models.project.items import ItemCollection


class Folder(ItemCollection):
    """
    Represents a folder item in the project hierarchy.
    
    A folder can contain other items (notes, datasets, charts, other folders).
    It extends ItemCollection with folder-specific functionality.
    """
    
    def __init__(self, id: Optional[str] = None, name: str = "New Folder"):
        # Call parent constructor (ItemCollection sets item_type to FOLDER)
        super().__init__(id, name)
