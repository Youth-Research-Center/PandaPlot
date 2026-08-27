import json
import logging
from typing import Any, Dict, List, override
from zipfile import ZipFile

import numpy as np
import pandas as pd

from pandaplot.models.project.items.dataset import Dataset
from pandaplot.storage.item_data_manager import ItemDataManager


def _json_safe_scalar(value: Any) -> Any:
    """Convert a single category/interval-bound value into a JSON-serializable form."""
    if pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _serialize_categorical_dtype(dtype: pd.CategoricalDtype) -> Dict[str, Any]:
    """Capture enough of a CategoricalDtype to reconstruct it exactly on load.

    `str(dtype)` collapses to the literal string "category", discarding both
    the `ordered` flag and the categories themselves. For a `cut`/`qcut`
    column (whitelisted transform functions, see #208) the categories are
    ordered `pd.Interval`s -- re-deriving them from the CSV text alone would
    mean re-parsing interval strings and would still lose `ordered=True`.
    """
    categories = dtype.categories
    if isinstance(categories, pd.IntervalIndex):
        return {
            "kind": "interval",
            "ordered": bool(dtype.ordered),
            "closed": categories.closed,
            "subtype": str(categories.dtype.subtype),
            "left": [_json_safe_scalar(v) for v in categories.left],
            "right": [_json_safe_scalar(v) for v in categories.right],
        }
    return {
        "kind": "value",
        "ordered": bool(dtype.ordered),
        "subtype": str(categories.dtype),
        "categories": [_json_safe_scalar(v) for v in categories],
    }


def _restore_scalar_index(values: List[Any], subtype: str) -> pd.Index:
    if subtype.startswith("datetime64"):
        return pd.to_datetime(pd.Index(values))
    try:
        return pd.Index(values, dtype=subtype)
    except (TypeError, ValueError):
        return pd.Index(values)


class DatasetDataManager(ItemDataManager[Dataset]):
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @override
    def save(self, item: Dataset, zip_file: ZipFile, path_in_zip: str) -> None:
        """
        Save dataset metadata as JSON and data as CSV.
        path_in_zip should be without extension, e.g. 'items/<id>'
        """
        self.logger.debug("Saving dataset '%s' (ID: %s) to path: %s", item.name, item.id, path_in_zip)

        try:
            # Save DataFrame as CSV if data exists
            column_dtypes: Dict[str, str] = {}
            column_categoricals: Dict[str, Dict[str, Any]] = {}
            if item.data is not None:
                csv_path = f"{path_in_zip}.csv"
                self.logger.debug("Saving dataset data to CSV: %s (shape: %s)", csv_path, item.data.shape)
                csv_data = item.data.to_csv(index=False)
                zip_file.writestr(csv_path, csv_data)
                # CSV has no type system, so plain re-import (pd.read_csv)
                # loses any dtype pandas can't round-trip through text --
                # notably datetime64 and category, both routinely produced
                # by transform expressions (to_datetime/cut/qcut are
                # whitelisted transform functions). Persist the dtype each
                # column had so load() can restore it. See #208.
                column_dtypes = {col: str(dtype) for col, dtype in item.data.dtypes.items()}
                for col, dtype in item.data.dtypes.items():
                    if isinstance(dtype, pd.CategoricalDtype):
                        column_categoricals[str(col)] = _serialize_categorical_dtype(dtype)
            else:
                self.logger.debug("Dataset '%s' has no data to save", item.name)

            # Prepare metadata (excluding the actual DataFrame)
            metadata = {
                "id": item.id,
                "name": item.name,
                "parent_id": item.parent_id,
                "created_at": item.created_at,
                "modified_at": item.modified_at,
                "metadata": item.metadata,
                "source_file": item.source_file,
                "has_data": item.data is not None,
                "column_ids": dict(item.column_ids),
                "column_dtypes": column_dtypes,
                "column_categoricals": column_categoricals,
            }
            
            self.logger.debug("Saving dataset metadata for '%s'", item.name)
        except Exception as e:
            self.logger.error("Failed to save dataset '%s' (ID: %s): %s", item.name, item.id, str(e), exc_info=True)
            raise
        
        # Save metadata as JSON
        json_path = f"{path_in_zip}.json"
        self.logger.debug("Saving dataset metadata to: %s", json_path)
        zip_file.writestr(json_path, json.dumps(metadata, indent=2))
        self.logger.info("Successfully saved dataset '%s' (ID: %s)", item.name, item.id)

    @override
    def load(self, item_class: type[Dataset], zip_file: ZipFile, path_in_zip: str, schema_version: int) -> Dataset:
        """
        Load dataset from CSV data + metadata JSON.
        path_in_zip is without extension.
        """
        self.logger.debug("Loading dataset from path: %s", path_in_zip)
        
        try:
            # Read metadata
            json_path = f"{path_in_zip}.json"
            self.logger.debug("Reading dataset metadata from: %s", json_path)
            metadata = json.loads(zip_file.read(json_path).decode("utf-8"))

            dataset_name = metadata.get("name", "Unknown")
            dataset_id = metadata.get("id", "Unknown")
            
            # Read CSV data if it exists
            data = None
            if metadata.get("has_data", False):
                try:
                    csv_path = f"{path_in_zip}.csv"
                    self.logger.debug("Reading dataset data from: %s", csv_path)
                    csv_content = zip_file.read(csv_path).decode("utf-8")
                    # Use StringIO to read CSV from string
                    from io import StringIO
                    data = pd.read_csv(StringIO(csv_content))
                    self._restore_column_dtypes(
                        data,
                        metadata.get("column_dtypes") or {},
                        metadata.get("column_categoricals") or {},
                    )
                    self.logger.debug("Loaded dataset data with shape: %s", data.shape)
                except KeyError:
                    # CSV file doesn't exist, data will be None
                    self.logger.warning("CSV file not found for dataset '%s', data will be None", dataset_name)
                    pass
            else:
                self.logger.debug("Dataset '%s' has no data to load", dataset_name)

            # Reconstruct dataset
            self.logger.debug("Reconstructing dataset object for '%s'", dataset_name)
            dataset = item_class(
                id=dataset_id,
                name=dataset_name,
                data=data,
                source_file=metadata.get("source_file")
            )

            # Restore the saved column-id registry so column ids stay stable
            # across save/load (chart series reference columns by these ids).
            # Only ids whose names still match the loaded data are kept; any
            # drift is reconciled by name, matching _sync_column_ids.
            saved_column_ids = metadata.get("column_ids")
            if saved_column_ids:
                from collections import OrderedDict
                current_names = [str(c) for c in dataset.data.columns] if dataset.data is not None else []
                name_to_saved_id = {name: cid for cid, name in saved_column_ids.items()}
                restored: "OrderedDict[str, str]" = OrderedDict()
                for name in current_names:
                    cid = name_to_saved_id.get(name)
                    if cid is not None:
                        restored[cid] = name
                    else:
                        # New/unmatched column keeps the fresh id __init__ assigned.
                        existing_id = dataset.column_id(name)
                        if existing_id is not None:
                            restored[existing_id] = name
                dataset.column_ids = restored

            self.logger.info("Successfully loaded dataset '%s' (ID: %s)", dataset_name, dataset_id)
            return dataset

        except Exception as e:
            self.logger.error("Failed to load dataset from %s: %s", path_in_zip, str(e), exc_info=True)
            raise

    def _restore_column_dtypes(
        self,
        data: pd.DataFrame,
        column_dtypes: Dict[str, str],
        column_categoricals: Dict[str, Dict[str, Any]] | None = None,
    ) -> None:
        """Best-effort cast each column back to the dtype it had at save time.

        `pd.read_csv` re-infers every column from plain text, which loses
        any dtype it can't recover on its own -- notably datetime64 (reads
        back as an object/string column) and category (reads back as its
        underlying value type). Both are routinely produced by transform
        expressions (`to_datetime`/`cut`/`qcut` are whitelisted transform
        functions), so a save/reload cycle silently downgraded a
        transformed column's type. Each column is restored independently;
        a column whose saved dtype no longer fits its re-read values
        (e.g. a hand-edited CSV) is left as read_csv inferred it rather
        than failing the whole load.
        """
        column_categoricals = column_categoricals or {}
        for column, dtype_str in column_dtypes.items():
            if column not in data.columns or dtype_str == str(data[column].dtype):
                continue
            try:
                if dtype_str.startswith("datetime64"):
                    target_dtype = pd.api.types.pandas_dtype(dtype_str)
                    if isinstance(target_dtype, pd.DatetimeTZDtype):
                        parsed = pd.to_datetime(data[column], utc=True)
                        parsed = parsed.dt.tz_convert(target_dtype.tz)
                    else:
                        parsed = pd.to_datetime(data[column])
                    data[column] = parsed.astype(target_dtype)
                elif dtype_str == "category":
                    info = column_categoricals.get(column)
                    if info:
                        data[column] = self._restore_categorical_column(data[column], info)
                    else:
                        # No categorical metadata (e.g. file saved before
                        # this was tracked) -- fall back to categorizing
                        # the raw CSV text, same as before.
                        data[column] = data[column].astype("category")
                else:
                    data[column] = data[column].astype(dtype_str)
            except (ValueError, TypeError) as e:
                self.logger.warning(
                    "Could not restore dtype '%s' for column '%s': %s", dtype_str, column, e,
                )

    def _restore_categorical_column(self, series: pd.Series, info: Dict[str, Any]) -> pd.Categorical:
        """Reconstruct the exact categories and `ordered` flag from saved metadata.

        The CSV round trip only gives back each cell's text, so cells are
        mapped back to their original category object by matching that
        text against `str(category)` -- the same textual form `to_csv`
        wrote -- rather than treating the text itself as the category
        (which is what a plain `astype("category")` does, and is how this
        silently dropped ordered `Interval` categories from `cut`/`qcut`).
        """
        ordered = bool(info.get("ordered", False))
        if info.get("kind") == "interval":
            closed = info.get("closed", "right")
            subtype = info.get("subtype", "float64")
            lefts = _restore_scalar_index(info.get("left", []), subtype)
            rights = _restore_scalar_index(info.get("right", []), subtype)
            categories: pd.Index = pd.IntervalIndex.from_arrays(lefts, rights, closed=closed)
        else:
            subtype = info.get("subtype", "object")
            categories = _restore_scalar_index(info.get("categories", []), subtype)

        text_to_category = {str(category): category for category in categories}
        mapped = series.astype(str).map(text_to_category)
        return pd.Categorical(mapped, categories=categories, ordered=ordered)