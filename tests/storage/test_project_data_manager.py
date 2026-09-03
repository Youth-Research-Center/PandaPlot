"""Integration tests for ProjectDataManager's schema-version-aware load
path.

These pin down two things end to end: (1) a legacy project file with no
schema_version (or one saved before this mechanism existed) is treated
as version 0, runs the registered cross-item migrations, and ends up
stamped at CURRENT_SCHEMA_VERSION; (2) a freshly-saved project round
trips its schema_version unchanged, without re-running migrations that
no longer apply.
"""
import json
import zipfile

import pandas as pd
import pytest

from pandaplot.models.migrations.schema_version import CURRENT_SCHEMA_VERSION
from pandaplot.models.project.items.chart import Chart, DataSeries
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.storage.chart_data_manager import ChartDataManager
from pandaplot.storage.dataset_data_manager import DatasetDataManager
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory
from pandaplot.storage.project_data_manager import ProjectDataManager


def _build_factory() -> ItemDataManagerFactory:
    """A minimal factory with just the two item types this test's fixture
    project uses — mirrors the real registration in app.py, which is not
    imported here to keep this a storage-layer-only test."""
    factory = ItemDataManagerFactory()
    factory.register("dataset", Dataset, DatasetDataManager(), "dataset")
    factory.register("chart", Chart, ChartDataManager(), "chart")
    return factory


@pytest.fixture
def factory():
    return _build_factory()


@pytest.fixture
def manager(factory):
    return ProjectDataManager(factory)


def _write_legacy_project_zip(path, factory, dataset_columns=("x", "y")):
    """Write a project zip shaped like one saved before schema_version
    existed: no schema_version key in project.json, and a chart series
    referencing its dataset column by name only (empty column ids), the
    exact legacy shape migrate_column_ids is meant to repair."""
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame(
        {dataset_columns[0]: [1, 2], dataset_columns[1]: [3, 4]}))
    chart = Chart(id="chart-1", name="Chart", chart_type="line")
    chart.data_series.append(DataSeries(
        dataset_id="ds-1", x_column=dataset_columns[0], y_column=dataset_columns[1]))

    project_dict = {
        "name": "Legacy Project",
        "description": "",
        "root": {"id": "root", "items": []},
        "metadata": {},
        "version": "1.0",
        # no "schema_version" key at all — the legacy case.
        "path": None,
        "item_files": {
            "ds-1": {"type": "dataset", "path": "items/ds-1"},
            "chart-1": {"type": "chart", "path": "items/chart-1"},
        },
    }
    project_dict["root"]["items"] = [
        {"id": "ds-1", "parent_id": None, "items": []},
        {"id": "chart-1", "parent_id": None, "items": []},
    ]

    with zipfile.ZipFile(path, "w") as zf:
        factory.get_manager("dataset").save(dataset, zf, "items/ds-1")
        factory.get_manager("chart").save(chart, zf, "items/chart-1")
        zf.writestr("project.json", json.dumps(project_dict))


def test_legacy_project_gets_column_ids_backfilled_and_version_stamped(tmp_path, manager, factory):
    zip_path = tmp_path / "legacy.pplot"
    _write_legacy_project_zip(zip_path, factory)

    project = manager.load(str(zip_path))

    chart = project.find_item("chart-1")
    dataset = project.find_item("ds-1")
    series = chart.data_series[0]
    assert series.x_column_id == dataset.column_id("x")
    assert series.y_column_id == dataset.column_id("y")
    assert project.schema_version == CURRENT_SCHEMA_VERSION


def test_freshly_saved_project_round_trips_schema_version(tmp_path, manager):
    project = Project(name="Fresh Project")
    zip_path = tmp_path / "fresh.pplot"

    manager.save(project, str(zip_path))
    loaded = manager.load(str(zip_path))

    assert loaded.schema_version == CURRENT_SCHEMA_VERSION


def test_load_records_failed_item_ids_instead_of_dropping_them_silently(tmp_path, manager, factory):
    """When one item's data fails to deserialize, load() must still return the
    project (with the other items intact) but record the failing item id on
    it, so callers can warn the user instead of the item just vanishing (#288)."""
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"x": [1, 2]}))

    project_dict = {
        "name": "Partially Broken Project",
        "description": "",
        "root": {"id": "root", "items": [
            {"id": "ds-1", "parent_id": None, "items": []},
            {"id": "ds-missing", "parent_id": None, "items": []},
        ]},
        "metadata": {},
        "version": "1.0",
        "schema_version": CURRENT_SCHEMA_VERSION,
        "path": None,
        "item_files": {
            "ds-1": {"type": "dataset", "path": "items/ds-1"},
            # References a path never written to the zip -- forces _load_item
            # to raise inside manager.load(), exercising the failure path.
            "ds-missing": {"type": "dataset", "path": "items/ds-missing"},
        },
    }

    zip_path = tmp_path / "partial.pplot"
    with zipfile.ZipFile(zip_path, "w") as zf:
        factory.get_manager("dataset").save(dataset, zf, "items/ds-1")
        zf.writestr("project.json", json.dumps(project_dict))

    project = manager.load(str(zip_path))

    assert project.failed_item_ids == ["ds-missing"]
    assert project.find_item("ds-1") is not None
    assert project.find_item("ds-missing") is None


def test_a_schema_version_newer_than_current_is_rejected(tmp_path, manager):
    """Migration dispatchers loop `while schema_version < CURRENT_SCHEMA_VERSION`,
    so a version newer than this app understands would silently skip migration,
    feed un-migrated dicts to from_dict(), and get swallowed by _load_item's
    broad except -- silently dropping items and risking a truncated overwrite
    on save. Must fail loudly instead."""
    project_dict = {
        "name": "From The Future",
        "description": "",
        "root": {"id": "root", "items": []},
        "metadata": {},
        "version": "1.0",
        "schema_version": CURRENT_SCHEMA_VERSION + 1,
        "path": None,
        "item_files": {},
    }
    zip_path = tmp_path / "future.pplot"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("project.json", json.dumps(project_dict))

    with pytest.raises(ValueError, match="schema_version"):
        manager.load(str(zip_path))
