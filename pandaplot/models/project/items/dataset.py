"""
Dataset model for managing data table items in the project.
"""

import uuid
from collections import OrderedDict
from datetime import datetime
from typing import Any

import pandas as pd

from pandaplot.models.project.items.formula_column import FormulaColumnSpec
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

    A column may additionally be a *formula* column (#154): the
    ``formula_columns`` registry (column id -> FormulaColumnSpec) records the
    expression that defines it, so it can be recomputed later instead of only
    ever holding the values one transform run happened to produce.
    """

    def __init__(self, id: str | None = None, name: str = "",
                 data: pd.DataFrame | None = None, source_file: str | None = None):
        super().__init__(id, name)

        # Set dataset-specific attributes
        # column_ids maps a stable column id -> its current name, ordered to
        # match the DataFrame's columns.
        self.column_ids: OrderedDict[str, str] = OrderedDict()
        self.formula_columns: dict[str, FormulaColumnSpec] = {}
        self.data: pd.DataFrame = data if data is not None else pd.DataFrame()
        self.source_file: str | None = source_file
        self._sync_column_ids()

    def set_data(self, data: pd.DataFrame) -> None:
        """Set the dataset's DataFrame and update associated metadata.

        This is the standard entry point for updating dataset content in commands.
        It updates `self.data`, reconciles stable column IDs via `_sync_column_ids()`,
        and updates the item's modification timestamp (`modified_at`).

        Note:
            Renaming columns should use :meth:`rename_column` directly rather than
            `set_data` so that column IDs are preserved across renames.

        Args:
            data: The pandas DataFrame containing the tabular data.
        """
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
        synced: OrderedDict[str, str] = OrderedDict()
        for name in current_names:
            cid = id_by_name.pop(name, None) or str(uuid.uuid4())
            synced[cid] = name
        self.column_ids = synced
        # A formula spec for a column that no longer exists is dead weight and
        # would otherwise resurrect itself if a column of the same name were
        # added back later (it would get a fresh id, but stale entries would
        # still be serialized).
        if self.formula_columns:
            self.formula_columns = {
                cid: spec for cid, spec in self.formula_columns.items() if cid in synced
            }

    def column_name(self, column_id: str) -> str | None:
        """Return the current name for a column id, or None if unknown."""
        return self.column_ids.get(column_id)

    def column_id(self, name: str) -> str | None:
        """Return the stable id for a column name, or None if not found."""
        for cid, col_name in self.column_ids.items():
            if col_name == name:
                return cid
        return None

    def rename_column(self, old_name: str, new_name: str) -> str | None:
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

    # ------------------------------------------------------------------
    # Formula columns (#154)
    # ------------------------------------------------------------------
    def set_formula_column(self, column_id: str, spec: FormulaColumnSpec) -> None:
        """Register (or replace) the formula that defines ``column_id``."""
        self.formula_columns[column_id] = spec

    def remove_formula_column(self, column_id: str) -> FormulaColumnSpec | None:
        """Drop the formula for ``column_id``, turning it back into a plain
        static column. Returns the removed spec, if there was one."""
        return self.formula_columns.pop(column_id, None)

    def formula_column(self, column_id: str) -> FormulaColumnSpec | None:
        """Return the formula spec for a column id, or None if it's a plain column."""
        return self.formula_columns.get(column_id)

    def formula_column_by_name(self, name: str) -> FormulaColumnSpec | None:
        """Return the formula spec for a column's current name, if any."""
        cid = self.column_id(name)
        return self.formula_columns.get(cid) if cid else None

    def formula_columns_dict(self) -> dict[str, dict[str, Any]]:
        """The formula registry in its serialized (JSON-safe) form."""
        return {cid: spec.to_dict() for cid, spec in self.formula_columns.items()}

    def load_formula_columns(self, data: dict[str, Any] | None) -> None:
        """Restore the formula registry from its serialized form.

        Entries whose column id is no longer present are dropped -- the same
        reconciliation ``_sync_column_ids`` does, applied here because the
        DataFrame is typically loaded before the registry is handed over.
        """
        if not data:
            return
        self.formula_columns = {
            cid: FormulaColumnSpec.from_dict(spec)
            for cid, spec in data.items()
            if cid in self.column_ids
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert dataset to dictionary for serialization."""
        data = super().to_dict()
        data.update({
            "source_file": self.source_file,
            "has_data": self.data is not None,
            "column_ids": dict(self.column_ids),
            "formula_columns": self.formula_columns_dict(),
        })

        # TODO(#219): serialization of dataframe
        # Note: We don't serialize the actual DataFrame data here
        # Data should be stored separately or reconstructed from source
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Dataset":
        """Create dataset from dictionary."""
        dataset = cls(
            id=data.get("id"),
            name=data.get("name", ""),
            source_file=data.get("source_file")
        )

        # Set inherited attributes
        dataset.parent_id = data.get("parent_id")
        dataset.created_at = data.get("created_at", datetime.now().isoformat())  # noqa: DTZ005 -- local-time display bookkeeping, never compared across timezones
        dataset.modified_at = data.get("modified_at", dataset.created_at)

        # Restore the saved column-id registry. The DataFrame is loaded
        # separately; when set_data runs, _sync_column_ids keeps these ids for
        # columns whose names match (legacy files with no registry get fresh
        # ids at that point).
        saved_ids = data.get("column_ids")
        if saved_ids:
            dataset.column_ids = OrderedDict(saved_ids)

        dataset.load_formula_columns(data.get("formula_columns"))

        return dataset
