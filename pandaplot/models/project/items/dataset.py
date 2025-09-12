"""
Dataset model for managing data table items in the project.
"""

from datetime import datetime
from typing import Optional, Dict, Any
import pandas as pd
from pandaplot.models.project.items import Item


class Dataset(Item):
    """
    Represents a dataset item in the project.
    
    A dataset contains tabular data (typically from CSV or other data sources).
    It's part of the hierarchical project structure.
    """
    
    def __init__(self, id: Optional[str] = None, name: str = "", 
                 data: Optional[pd.DataFrame] = None, source_file: Optional[str] = None):
        super().__init__(id, name)
        
        # Set dataset-specific attributes
        self.data: pd.DataFrame = data if data is not None else pd.DataFrame()
        self.source_file: Optional[str] = source_file
    
    def set_data(self, data: pd.DataFrame) -> None:
        """Set the dataset data and update metadata."""
        self.data = data
        self.update_modified_time()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert dataset to dictionary for serialization."""
        data = super().to_dict()
        data.update({
            'source_file': self.source_file,
            'has_data': self.data is not None
        })
        
        # TODO: serialization of dataframe
        # Note: We don't serialize the actual DataFrame data here
        # Data should be stored separately or reconstructed from source
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Dataset':
        """Create dataset from dictionary."""
        dataset = cls(
            id=data.get('id'),
            name=data.get('name', ''),
            source_file=data.get('source_file')
        )
        
        # Set inherited attributes
        dataset.parent_id = data.get('parent_id')
        dataset.created_at = data.get('created_at', datetime.now().isoformat())
        dataset.modified_at = data.get('modified_at', dataset.created_at)
        
        return dataset
        