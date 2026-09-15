import os
import tempfile

from PySide6.QtWidgets import QWidget

from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas
from pandaplot.gui.components.tabs.sketch.sketch_exporter import SketchExporter
from pandaplot.models.project.items.sketch import (
    SKETCH_ELEMENT_TYPES,
    RectangleElement,
    Sketch,
    SketchElement,
)


def test_export_sketch_to_png_svg_pdf_jpeg(qtbot):
    sketch = Sketch(name="Export Sketch")
    layer = sketch.get_active_layer()
    rect = RectangleElement(x=10, y=10, width=100, height=100, fill_color="#FF0000")
    layer.elements.append(rect)

    parent_widget = QWidget()
    qtbot.addWidget(parent_widget)
    canvas = SketchCanvas(sketch, parent_widget)

    with tempfile.TemporaryDirectory() as tmpdir:
        png_path = os.path.join(tmpdir, "out.png")
        assert SketchExporter.export_to_image(canvas, png_path, "PNG", dpi=150, transparent=True)
        assert os.path.exists(png_path) and os.path.getsize(png_path) > 0

        jpg_path = os.path.join(tmpdir, "out.jpg")
        assert SketchExporter.export_to_image(canvas, jpg_path, "JPEG", dpi=150, transparent=False)
        assert os.path.exists(jpg_path) and os.path.getsize(jpg_path) > 0

        svg_path = os.path.join(tmpdir, "out.svg")
        assert SketchExporter.export_to_image(canvas, svg_path, "SVG")
        assert os.path.exists(svg_path) and os.path.getsize(svg_path) > 0

        pdf_path = os.path.join(tmpdir, "out.pdf")
        assert SketchExporter.export_to_image(canvas, pdf_path, "PDF")
        assert os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0


def test_sketch_element_registry_extension_seam():
    class CustomElement(SketchElement):
        type = "custom_test"

        @classmethod
        def _from_dict_concrete(cls, data):
            return cls(id=data.get("id"), x=data.get("x", 0.0), y=data.get("y", 0.0))

    SKETCH_ELEMENT_TYPES["custom_test"] = CustomElement

    data = {"type": "custom_test", "id": "custom-1", "x": 42.0, "y": 84.0}
    reconstructed = SketchElement.from_dict(data)

    assert isinstance(reconstructed, CustomElement)
    assert reconstructed.id == "custom-1"
    assert reconstructed.x == 42.0
