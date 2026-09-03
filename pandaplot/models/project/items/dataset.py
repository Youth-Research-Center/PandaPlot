"""
Dataset model for managing data table items in the project.
"""

import uuid
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, Optional

import pandas as pd

from pandaplot.models.project.items.item import Item


class Dataset(Item):
    """
    Represents a dataset item in the project.

    A dataset contains tabular data (typically from CSV or other data sources).
    It's part of the hierarchical project structure.

    Columns carry a stable id independent of their (renamable) name. The
    DataFrame stays keyed by name for all pandas/display/export operations;
    the ``column_ids`` registry (id -> current name) lets other items
    (chart series, fits) reference a column by id so a rename doesn't have to
    cascade into every reference. See ``column_name`` / ``column_id``.
    """

    def __init__(self, id: Optional[str] = None, name: str = "",
                 data: Optional[pd.DataFrame] = None, source_file: Optional[str] = None):
        super().__init__(id, name)

        # Set dataset-specific attributes
        # column_ids maps a stable column id -> its current name, ordered to
        # match the DataFrame's columns.
        self.column_ids: "OrderedDict[str, str]" = OrderedDict()
        self.data: pd.DataFrame = data if data is not None else pd.DataFrame()
        self.source_file: Optional[str] = source_file
        self._sync_column_ids()

    def set_data(self, data: pd.DataFrame) -> None:
        """Set the dataset data and update metadata."""
        self.data = data
        self._sync_column_ids()
        self.update_modified_time()

    # ------------------------------------------------------------------
    # Column identity
    # ------------------------------------------------------------------
    def _sync_column_ids(self) -> None:
        """Reconcile the id registry with the current DataFrame columns.

        Matches by name: names that persist keep their id, new names get a
        fresh id, and ids for removed names are dropped. This correctly
        handles add / remove / reorder / import. A *rename* deliberately does
        not go through here (a name diff can't tell a rename from a
        drop+add) — use :meth:`rename_column` so the id is preserved.
        """
        current_names = [str(c) for c in self.data.columns] if self.data is not None else []
        id_by_name = {name: cid for cid, name in self.column_ids.items()}
        synced: "OrderedDict[str, str]" = OrderedDict()
        for name in current_names:
            cid = id_by_name.pop(name, None) or str(uuid.uuid4())
            synced[cid] = name
        self.column_ids = synced

    def column_name(self, column_id: str) -> Optional[str]:
        """Return the current name for a column id, or None if unknown."""
        return self.column_ids.get(column_id)

    def column_id(self, name: str) -> Optional[str]:
        """Return the stable id for a column name, or None if not found."""
        for cid, col_name in self.column_ids.items():
            if col_name == name:
                return cid
        return None

    def rename_column(self, old_name: str, new_name: str) -> Optional[str]:
        """Update the registry entry for ``old_name`` in place, keeping its id.

        Does not touch the DataFrame — the caller renames the column so the
        two stay in sync. Returns the (unchanged) column id, or None if
        ``old_name`` is not registered.
        """
        cid = self.column_id(old_name)
        if cid is None:
            return None
        self.column_ids[cid] = new_name
        return cid

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataset to dictionary for serialization."""
        data = super().to_dict()
        data.update({
            "source_file": self.source_file,
            "has_data": self.data is not None,
            "column_ids": dict(self.column_ids),
        })

        # TODO(#219): serialization of dataframe
        # Note: We don't serialize the actual DataFrame data here
        # Data should be stored separately or reconstructed from source
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Dataset":
        """Create dataset from dictionary."""
        dataset = cls(
            id=data.get("id"),
            name=data.get("name", ""),
            source_file=data.get("source_file")
        )

        # Set inherited attributes
        dataset.parent_id = data.get("parent_id")
        dataset.created_at = data.get("created_at", datetime.now().isoformat())
        dataset.modified_at = data.get("modified_at", dataset.created_at)

        # Restore the saved column-id registry. The DataFrame is loaded
        # separately; when set_data runs, _sync_column_ids keeps these ids for
        # columns whose names match (legacy files with no registry get fresh
        # ids at that point).
        saved_ids = data.get("column_ids")
        if saved_ids:
            dataset.column_ids = OrderedDict(saved_ids)

        return dataset
