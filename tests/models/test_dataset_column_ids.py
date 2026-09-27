"""Tests for the Dataset column-id registry and its stability across edits."""

import numpy as np
import pandas as pd

from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.project import Project
from pandaplot.models.project.items.chart import (
    Chart,
    DataSeries,
    resolve_series_column,
)
from pandaplot.models.project.items.dataset import Dataset


def test_columns_get_ids_and_are_resolvable():
    ds = Dataset(name="ds", data=pd.DataFrame({"a": [1], "b": [2]}))
    assert set(ds.column_ids.values()) == {"a", "b"}
    a_id = ds.column_id("a")
    assert a_id is not None
    assert ds.column_name(a_id) == "a"
    assert ds.column_id("missing") is None


def test_rename_preserves_id():
    ds = Dataset(name="ds", data=pd.DataFrame({"a": [1], "b": [2]}))
    a_id = ds.column_id("a")

    returned = ds.rename_column("a", "time")
    ds.data.rename(columns={"a": "time"}, inplace=True)

    assert returned == a_id
    assert ds.column_id("time") == a_id  # id is stable across the rename
    assert ds.column_id("a") is None
    assert ds.column_name(a_id) == "time"


def test_set_data_syncs_ids_by_name():
    ds = Dataset(name="ds", data=pd.DataFrame({"a": [1], "b": [2]}))
    a_id = ds.column_id("a")

    # Add a column and drop another; matching names keep their ids.
    ds.set_data(pd.DataFrame({"a": [1], "c": [3]}))

    assert ds.column_id("a") == a_id  # preserved
    assert ds.column_name(a_id) == "a"
    assert ds.column_id("b") is None  # dropped
    assert ds.column_id("c") is not None  # freshly assigned


def test_rename_column_unknown_name_returns_none():
    ds = Dataset(name="ds", data=pd.DataFrame({"a": [1]}))
    assert ds.rename_column("nope", "x") is None


def test_serialization_round_trip_preserves_ids():
    ds = Dataset(name="ds", data=pd.DataFrame({"a": [1], "b": [2]}))
    a_id = ds.column_id("a")

    restored = Dataset.from_dict(ds.to_dict())
    # from_dict restores the registry even before the DataFrame is attached.
    assert restored.column_id("a") == a_id


def test_resolver_prefers_id_falls_back_to_name():
    ds = Dataset(name="ds", data=pd.DataFrame({"a": [1], "b": [2]}))
    a_id = ds.column_id("a")

    # id resolves to current name even if the stored fallback name is stale
    ds.rename_column("a", "time")
    ds.data.rename(columns={"a": "time"}, inplace=True)
    assert resolve_series_column(ds, a_id, "a") == "time"

    # empty id -> fall back to the stored name
    assert resolve_series_column(ds, "", "b") == "b"

    # neither resolves -> None
    assert resolve_series_column(ds, "", "") is None
    assert resolve_series_column(ds, "bogus-id", "gone") == "gone"


def test_assign_series_column_ids_via_dataset():
    from pandaplot.models.project.items.chart import assign_series_column_ids

    ds = Dataset(name="ds", data=pd.DataFrame({"a": [1], "b": [2]}))
    series = DataSeries(dataset_id=ds.id, x_column="a", y_column="b")
    assign_series_column_ids(series, ds)

    assert series.x_column_id == ds.column_id("a")
    assert series.y_column_id == ds.column_id("b")


def test_add_data_series_stores_column_ids():
    """add_data_series references columns purely by id; the caller resolves."""
    ds = Dataset(name="ds", data=pd.DataFrame({"a": [1], "b": [2]}))
    chart = Chart(name="c")

    series = chart.add_data_series(
        ds.id,
        x_column_id=ds.column_id("a"),
        y_column_id=ds.column_id("b"),
        label="s",
    )

    assert series.dataset_id == ds.id
    assert series.x_column_id == ds.column_id("a")
    assert series.y_column_id == ds.column_id("b")
    # No dataset reference is held; names are left empty (id is authoritative).
    assert series.x_column == ""
    assert series.y_column == ""


def test_add_data_series_defaults_to_empty_ids():
    """Omitting column ids yields an unbound series (e.g. index-only x)."""
    chart = Chart(name="c")
    series = chart.add_data_series("ds1")

    assert series.dataset_id == "ds1"
    assert series.x_column_id == ""
    assert series.y_column_id == ""


def test_add_fit_data_stores_column_ids():
    ds = Dataset(name="ds", data=pd.DataFrame({"a": [1], "b": [2]}))
    chart = Chart(name="c")

    fit = chart.add_fit_series(
        ds.id, np.array([1.0]), np.array([2.0]),
        "Linear", FitStyle(fit_type="Linear"),
        source_x_column_id=ds.column_id("a"),
        source_y_column_id=ds.column_id("b"),
    )

    assert fit.dataset_id == ds.id
    assert fit.x_column_id == ds.column_id("a")
    assert fit.y_column_id == ds.column_id("b")


def test_search_chart_resolves_column_ids_via_project():
    """search_chart matches on live column names resolved from ids."""
    ds = Dataset(name="ds", data=pd.DataFrame({"velocity": [1], "b": [2]}))
    project = Project("P")
    project.add_item(ds)
    chart = Chart(name="c")
    chart.add_data_series(ds.id, x_column_id=ds.column_id("velocity"),
                          y_column_id=ds.column_id("b"))
    project.add_item(chart)

    # Resolves the id -> current name and matches on it.
    assert chart.search_chart("velocity", project) is True
    # A rename is reflected without touching the series.
    ds.rename_column("velocity", "speed")
    ds.data.rename(columns={"velocity": "speed"}, inplace=True)
    assert chart.search_chart("speed", project) is True
    assert chart.search_chart("velocity", project) is False
    # Without a project, id-only series expose no column name to match.
    assert chart.search_chart("speed") is False
