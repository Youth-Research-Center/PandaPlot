import tempfile
import zipfile

from pandaplot.app import create_project_data_manager
from pandaplot.models.migrations.per_item.sketch import migrate_sketch
from pandaplot.models.project.items.sketch import (
    EllipseElement,
    FreehandElement,
    LineElement,
    RectangleElement,
    Sketch,
    TextElement,
)
from pandaplot.storage.sketch_data_manager import SketchDataManager


def test_sketch_data_manager_save_load_real_zip():
    sketch = Sketch(name="Real Zip Persisted Sketch")
    layer = sketch.get_active_layer()
    assert layer is not None

    rect = RectangleElement(x=10.0, y=20.0, width=100.0, height=50.0, fill_color="#FF0000")
    freehand = FreehandElement(points=[(0.0, 0.0), (10.0, 10.0)])
    line = LineElement(x1=0.0, y1=0.0, x2=50.0, y2=50.0)
    ellipse = EllipseElement(rx=30.0, ry=20.0)
    text = TextElement(text="Sample Text")

    layer.elements.extend([rect, freehand, line, ellipse, text])

    manager = SketchDataManager()

    with tempfile.NamedTemporaryFile(suffix=".zip") as tmp:
        with zipfile.ZipFile(tmp.name, "w") as zf:
            manager.save(sketch, zf, "items/sketch_full")

        with zipfile.ZipFile(tmp.name, "r") as zf:
            loaded_sketch = manager.load(Sketch, zf, "items/sketch_full", schema_version=1)

    assert loaded_sketch.name == "Real Zip Persisted Sketch"
    assert loaded_sketch.id == sketch.id
    assert len(loaded_sketch.layers) == 1
    loaded_layer = loaded_sketch.layers[0]
    assert len(loaded_layer.elements) == 5

    assert isinstance(loaded_layer.elements[0], RectangleElement)
    assert isinstance(loaded_layer.elements[1], FreehandElement)
    assert isinstance(loaded_layer.elements[2], LineElement)
    assert isinstance(loaded_layer.elements[3], EllipseElement)
    assert isinstance(loaded_layer.elements[4], TextElement)
    assert loaded_layer.elements[4].text == "Sample Text"


def test_item_data_manager_factory_sketch_registration():
    pdm = create_project_data_manager()
    factory = pdm.data_factory
    manager = factory.get_manager("sketch")
    item_cls = factory.resolve_item_class("sketch")
    ext = factory.get_extension_for_type("sketch")
    assert isinstance(manager, SketchDataManager)
    assert item_cls is Sketch
    assert ext == "sketch"


def test_migrate_sketch():
    raw_data = {"id": "123", "name": "Test"}
    migrated = migrate_sketch(raw_data, schema_version=1)
    assert migrated == raw_data
