"""Tests for SketchDataManager and saving sketches inside a project file."""
import io
import json
from unittest.mock import patch
from zipfile import ZipFile

from pandaplot.app import create_project_data_manager
from pandaplot.models.migrations.schema_version import CURRENT_SCHEMA_VERSION
from pandaplot.models.project.items.sketch import (
    EllipseElement,
    FreehandElement,
    LineElement,
    RectangleElement,
    Sketch,
    SketchLayer,
    TextElement,
)
from pandaplot.models.project.project import Project
from pandaplot.storage.sketch_data_manager import SketchDataManager


def _sketch() -> Sketch:
    return Sketch(
        id="sketch-1", name="Diagram",
        layers=[
            SketchLayer(id="bg", name="Background", locked=True, elements=[
                RectangleElement(id="r", x=10.0, y=10.0, width=100.0, height=50.0, fill_color="#EEEEEE"),
                EllipseElement(id="e", x=60.0, y=35.0, rx=20.0, ry=10.0),
            ]),
            SketchLayer(id="ink", name="Ink", opacity=0.8, elements=[
                FreehandElement(id="f", points=[(0.0, 0.0), (1.5, 2.5)]),
                LineElement(id="l", x=1.0, y=1.0, dx=9.0, dy=9.0),
                TextElement(id="t", text="Label", font_size=18),
            ]),
        ],
        active_layer_id="ink",
    )


def _round_trip(sketch: Sketch, schema_version: int = CURRENT_SCHEMA_VERSION) -> Sketch:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as zf:
        SketchDataManager().save(sketch, zf, "items/sketch-1")

    buffer.seek(0)
    with ZipFile(buffer, "r") as zf:
        return SketchDataManager().load(Sketch, zf, "items/sketch-1", schema_version)


def test_save_writes_one_json_file_at_path_in_zip():
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as zf:
        SketchDataManager().save(_sketch(), zf, "items/sketch-1")

    buffer.seek(0)
    with ZipFile(buffer, "r") as zf:
        assert zf.namelist() == ["items/sketch-1.json"]
        assert json.loads(zf.read("items/sketch-1.json"))["active_layer_id"] == "ink"


def test_round_trip_preserves_sketch_layers_and_elements():
    sketch = _sketch()

    loaded = _round_trip(sketch)

    assert loaded.to_dict() == sketch.to_dict()
    assert loaded.layers == sketch.layers


def test_load_runs_migrate_sketch_with_the_saved_schema_version():
    calls = []

    def spy_migrate_sketch(raw, schema_version):
        calls.append(schema_version)
        return raw

    with patch("pandaplot.storage.sketch_data_manager.migrate_sketch", side_effect=spy_migrate_sketch):
        _round_trip(_sketch(), schema_version=5)

    assert calls == [5]


def test_app_registers_sketch_with_its_manager_class_and_extension():
    factory = create_project_data_manager().data_factory

    assert isinstance(factory.get_manager("sketch"), SketchDataManager)
    assert factory.resolve_item_class("sketch") is Sketch
    assert factory.get_extension_for_type("sketch") == "sketch"


def test_project_with_a_sketch_round_trips_through_a_project_file(tmp_path):
    manager = create_project_data_manager()
    project = Project(name="With sketch")
    original = _sketch()
    project.add_item(original)
    path = tmp_path / "project.pplot"

    manager.save(project, str(path))
    loaded = manager.load(str(path))

    sketch = loaded.find_item("sketch-1")
    assert isinstance(sketch, Sketch)
    assert sketch.to_dict() == original.to_dict()
    assert loaded.schema_version == CURRENT_SCHEMA_VERSION
