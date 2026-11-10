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
from pandaplot.utils.errors import UserFacingError


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

    with pytest.raises(UserFacingError, match="newer version of PandaPlot"):
        manager.load(str(zip_path))


def test_formula_columns_raised_the_schema_version_past_the_last_pre_formula_release():
    """Regression: formula columns persist data an older build would drop on its next save, so the
    version must be one older builds reject (they only accept <= their own CURRENT_SCHEMA_VERSION)."""
    assert CURRENT_SCHEMA_VERSION >= 4


def test_a_version_3_project_loads_and_is_stamped_current(tmp_path, manager):
    project_dict = {
        "name": "Before Formulas",
        "description": "",
        "root": {"id": "root", "items": []},
        "metadata": {},
        "version": "1.0",
        "schema_version": 3,
        "path": None,
        "item_files": {},
    }
    zip_path = tmp_path / "v3.pplot"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("project.json", json.dumps(project_dict))

    project = manager.load(str(zip_path))

    assert project.schema_version == CURRENT_SCHEMA_VERSION


# --- example settings and cover image (#608, #598) ---

def _png_bytes() -> bytes:
    from PySide6.QtCore import QBuffer, QIODevice
    from PySide6.QtGui import QColor, QImage

    image = QImage(8, 4, QImage.Format.Format_RGB32)
    image.fill(QColor("blue"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def test_schema_version_is_7():
    assert CURRENT_SCHEMA_VERSION == 7


def test_cover_image_and_example_info_round_trip(tmp_path, manager):
    from pandaplot.models.project.example_info import ExampleInfo, ExampleLevel, ExampleSection

    project = Project(name="Cover")
    project.example_info = ExampleInfo(
        is_example=True, summary="s", section=ExampleSection.CHARTS, level=ExampleLevel.INTERMEDIATE,
        tag_ids=("physics",), featured_chart_ids=("c",), start_note_id="n", data_credit="credit")
    project.cover_image = _png_bytes()
    path = str(tmp_path / "cover.pplot")

    manager.save(project, path)

    with zipfile.ZipFile(path) as zf:
        assert zf.read("cover.png") == project.cover_image
        meta = json.loads(zf.read("project.json"))
    assert meta["cover_image"] == "cover.png"
    assert meta["schema_version"] == CURRENT_SCHEMA_VERSION
    loaded = manager.load(path)
    assert loaded.cover_image == project.cover_image
    assert loaded.example_info == project.example_info


def test_project_without_cover_image_writes_no_entry(tmp_path, manager):
    path = str(tmp_path / "plain.pplot")
    manager.save(Project(name="Plain"), path)

    with zipfile.ZipFile(path) as zf:
        assert "cover.png" not in zf.namelist()
        assert "cover_image" not in json.loads(zf.read("project.json"))
    assert manager.load(path).cover_image is None


def test_corrupt_cover_image_loads_as_none_with_warning(tmp_path, manager, caplog):
    project = Project(name="Bad cover")
    project.cover_image = b"this is not a png"
    path = str(tmp_path / "bad.pplot")
    manager.save(project, path)

    with caplog.at_level("WARNING"):
        loaded = manager.load(path)

    assert loaded.cover_image is None
    assert "cover image" in caplog.text


def test_missing_cover_entry_loads_as_none(tmp_path, manager):
    path = str(tmp_path / "missing.pplot")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("project.json", json.dumps({"name": "M", "schema_version": 7, "cover_image": "cover.png"}))

    assert manager.load(path).cover_image is None


def test_version_6_file_without_example_or_cover_loads_with_defaults(tmp_path, manager):
    from pandaplot.models.project.example_info import ExampleInfo

    path = str(tmp_path / "v6.pplot")
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("project.json", json.dumps({"name": "Old", "description": "d", "schema_version": 6}))

    loaded = manager.load(path)

    assert loaded.name == "Old"
    assert loaded.example_info == ExampleInfo()
    assert loaded.cover_image is None


def _write_zip_with_damaged_cover(path) -> None:
    """Write a project zip whose stored cover.png entry fails its CRC check when read."""
    cover = b"damaged-cover-bytes" * 8
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("cover.png", cover)
        zf.writestr("project.json", json.dumps({"name": "Damaged", "schema_version": 7, "cover_image": "cover.png"}))
    raw = bytearray(path.read_bytes())
    offset = raw.index(cover)
    raw[offset] ^= 0xFF
    path.write_bytes(bytes(raw))
    with zipfile.ZipFile(path) as zf, pytest.raises(zipfile.BadZipFile):
        zf.read("cover.png")


def test_damaged_cover_entry_does_not_prevent_loading_project(tmp_path, manager, caplog):
    path = tmp_path / "damaged.pplot"
    _write_zip_with_damaged_cover(path)

    with caplog.at_level("WARNING"):
        loaded = manager.load(str(path))

    assert loaded.name == "Damaged"
    assert loaded.cover_image is None
    assert "cover image" in caplog.text


def test_damaged_other_entry_still_fails_loading(tmp_path, manager):
    path = tmp_path / "damaged-item.pplot"
    payload = b"item-payload-bytes" * 8
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as zf:
        zf.writestr("items/x.json", payload)
        zf.writestr("project.json", json.dumps({"name": "Damaged", "schema_version": 7}))
    raw = bytearray(path.read_bytes())
    raw[raw.index(payload)] ^= 0xFF
    path.write_bytes(bytes(raw))

    with pytest.raises(zipfile.BadZipFile):
        manager.load(str(path))
