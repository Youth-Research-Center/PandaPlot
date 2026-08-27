"""Tests for DatasetDataManager's CSV-backed save/load round trip.

Regression coverage for #208: dataset columns are saved as plain CSV, which
has no type system, so a naive round trip silently downgrades any dtype
`pd.read_csv` can't re-infer on its own -- notably datetime64 and category,
both routinely produced by transform expressions (`to_datetime`/`cut`/
`qcut` are whitelisted functions in TransformColumnCommand's safe eval
environment).
"""
import zipfile

import pandas as pd

from pandaplot.models.project.items.dataset import Dataset
from pandaplot.storage.dataset_data_manager import DatasetDataManager


def _round_trip(dataset: Dataset, tmp_path) -> Dataset:
    manager = DatasetDataManager()
    zip_path = tmp_path / "dataset.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        manager.save(dataset, zf, "items/ds")
    with zipfile.ZipFile(zip_path, "r") as zf:
        return manager.load(Dataset, zf, "items/ds", schema_version=1)


def test_round_trip_preserves_plain_numeric_and_string_columns(tmp_path):
    df = pd.DataFrame({"x": [1, 2, 3], "label": ["a", "b", "c"]})
    dataset = Dataset(id="ds", name="Data", data=df)

    loaded = _round_trip(dataset, tmp_path)

    pd.testing.assert_frame_equal(loaded.data, df)


def test_round_trip_preserves_datetime_column_dtype(tmp_path):
    """A datetime column (e.g. from a `to_datetime(...)` transform) must
    still be datetime64 after save/load, not degrade to a plain string."""
    df = pd.DataFrame({
        "x": [1, 2, 3],
        "dt_col": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-03"]),
    })
    dataset = Dataset(id="ds", name="Data", data=df)

    loaded = _round_trip(dataset, tmp_path)

    assert pd.api.types.is_datetime64_any_dtype(loaded.data["dt_col"])
    assert list(loaded.data["dt_col"]) == list(df["dt_col"])


def test_round_trip_preserves_category_column_dtype(tmp_path):
    """A categorical column from `cut(...)` must keep its exact ordered
    Interval categories after save/load, not just any CategoricalDtype --
    `str(dtype)` collapses to "category", losing `ordered` and the
    categories themselves unless separately persisted (#208 follow-up)."""
    df = pd.DataFrame({
        "x": [1, 2, 3, 4],
        "bucket": pd.cut([1, 2, 3, 4], bins=2),
    })
    dataset = Dataset(id="ds", name="Data", data=df)

    loaded = _round_trip(dataset, tmp_path)

    pd.testing.assert_series_equal(loaded.data["bucket"], df["bucket"])
    assert loaded.data["bucket"].dtype.ordered is True


def test_round_trip_preserves_ordered_numeric_category_from_qcut(tmp_path):
    df = pd.DataFrame({
        "x": range(8),
        "quartile": pd.qcut(range(8), q=4),
    })
    dataset = Dataset(id="ds", name="Data", data=df)

    loaded = _round_trip(dataset, tmp_path)

    pd.testing.assert_series_equal(loaded.data["quartile"], df["quartile"])
    assert loaded.data["quartile"].dtype.ordered is True


def test_round_trip_preserves_unordered_string_category(tmp_path):
    df = pd.DataFrame({
        "label": pd.Categorical(["b", "a", "b", "c"], categories=["c", "b", "a"]),
    })
    dataset = Dataset(id="ds", name="Data", data=df)

    loaded = _round_trip(dataset, tmp_path)

    pd.testing.assert_series_equal(loaded.data["label"], df["label"])
    assert loaded.data["label"].dtype.ordered is False
    assert list(loaded.data["label"].cat.categories) == ["c", "b", "a"]


def test_round_trip_preserves_bool_column_dtype(tmp_path):
    df = pd.DataFrame({"x": [1, 2, 3], "is_even": [False, True, False]})
    dataset = Dataset(id="ds", name="Data", data=df)

    loaded = _round_trip(dataset, tmp_path)

    assert loaded.data["is_even"].dtype == bool
    assert list(loaded.data["is_even"]) == [False, True, False]


def test_dataset_with_no_data_round_trips_without_error(tmp_path):
    dataset = Dataset(id="ds", name="Empty", data=None)
    dataset.data = None  # bypass the constructor's empty-DataFrame default

    loaded = _round_trip(dataset, tmp_path)

    # Dataset.__init__ treats a None `data` argument as "start with an
    # empty DataFrame" (see Dataset.__init__), so that's what a "no data"
    # save/load round trip is expected to produce too.
    assert loaded.data is not None
    assert loaded.data.empty
