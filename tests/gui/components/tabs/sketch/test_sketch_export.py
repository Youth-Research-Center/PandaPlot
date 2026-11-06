"""Tests for rendering and exporting sketches (PNG, JPEG, SVG, PDF)."""
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import ClassVar

import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem

from pandaplot.gui.components.tabs.sketch import graphics_items
from pandaplot.gui.components.tabs.sketch.sketch_export import (
    BASE_DPI,
    MAX_RASTER_PIXELS,
    ExportFormat,
    ExportRegion,
    SketchExportError,
    SketchExportOptions,
    export_rect,
    export_sketch,
    exported_layers,
    output_size,
    render_image,
)
from pandaplot.models.project.items.sketch import ELEMENT_TYPES, RectangleElement, Sketch, SketchElement, SketchLayer

pytestmark = pytest.mark.usefixtures("qapp")

RED, BLUE = QColor("#FF0000"), QColor("#0000FF")


@pytest.fixture
def sketch() -> Sketch:
    """A 200x100 canvas with a red box on the bottom layer and a blue box on
    a hidden top layer."""
    return Sketch(name="Boxes", canvas_width=200.0, canvas_height=100.0, background_color="#FFFF00", layers=[
        SketchLayer(id="bottom", elements=[RectangleElement(x=20.0, y=20.0, width=40.0, height=30.0, stroke_width=0.0, fill_color="#FF0000")]),
        SketchLayer(id="hidden", visible=False, elements=[
            RectangleElement(x=120.0, y=20.0, width=40.0, height=30.0, stroke_width=0.0, fill_color="#0000FF"),
        ]),
    ])


def _pixel(image: QImage, x: int, y: int) -> QColor:
    return image.pixelColor(x, y)


class TestOptions:
    @pytest.mark.parametrize("kwargs", [
        {"scale": 0.0}, {"scale": -1.0}, {"scale": float("nan")}, {"padding": -1.0},
        {"format": ExportFormat.JPEG, "transparent": True}, {"format": ExportFormat.PDF, "transparent": True},
    ])
    def test_invalid_options_are_refused(self, kwargs):
        with pytest.raises(ValueError):
            SketchExportOptions(**kwargs)

    def test_default_layers_are_the_visible_ones_and_chosen_ones_may_be_hidden(self, sketch):
        assert [layer.id for layer in exported_layers(sketch, SketchExportOptions())] == ["bottom"]
        assert [layer.id for layer in exported_layers(sketch, SketchExportOptions(layer_ids=frozenset({"hidden", "bottom"})))] == ["bottom", "hidden"]


class TestRegionAndSize:
    def test_canvas_region_is_the_whole_paper(self, sketch):
        assert export_rect(sketch, SketchExportOptions()) == QRectF(0.0, 0.0, 200.0, 100.0)

    def test_elements_region_is_their_bounds_plus_padding(self, sketch):
        options = SketchExportOptions(region=ExportRegion.ELEMENTS, padding=5.0)

        assert export_rect(sketch, options) == QRectF(15.0, 15.0, 50.0, 40.0)

    def test_elements_region_follows_the_chosen_layers(self, sketch):
        options = SketchExportOptions(region=ExportRegion.ELEMENTS, padding=0.0, layer_ids=frozenset({"bottom", "hidden"}))

        assert export_rect(sketch, options) == QRectF(20.0, 20.0, 140.0, 30.0)

    def test_elements_region_is_none_without_elements(self, sketch):
        assert export_rect(sketch, SketchExportOptions(region=ExportRegion.ELEMENTS, layer_ids=frozenset())) is None
        assert export_rect(Sketch(), SketchExportOptions(region=ExportRegion.ELEMENTS)) is None

    @pytest.mark.parametrize(("export_format", "scale", "expected"), [
        (ExportFormat.PNG, 1.0, (200, 100)),
        (ExportFormat.PNG, 2.5, (500, 250)),
        (ExportFormat.JPEG, 0.333, (67, 34)),
        # Vector formats keep canvas units whatever the scale.
        (ExportFormat.SVG, 4.0, (200, 100)),
        (ExportFormat.PDF, 4.0, (200, 100)),
    ])
    def test_output_size(self, sketch, export_format, scale, expected):
        options = SketchExportOptions(format=export_format, scale=scale)

        size = output_size(QRectF(0.0, 0.0, 200.0, 100.0), options)

        assert (size.width(), size.height()) == expected


class TestRenderImage:
    def test_draws_the_background_and_the_visible_layers_only(self, sketch):
        image = render_image(sketch, SketchExportOptions())

        assert (image.width(), image.height()) == (200, 100)
        assert _pixel(image, 2, 2) == QColor("#FFFF00")
        assert _pixel(image, 40, 35) == RED
        # The hidden layer's blue box is not drawn.
        assert _pixel(image, 140, 35) == QColor("#FFFF00")

    def test_a_chosen_hidden_layer_is_drawn(self, sketch):
        image = render_image(sketch, SketchExportOptions(layer_ids=frozenset({"hidden"})))

        assert _pixel(image, 140, 35) == BLUE
        assert _pixel(image, 40, 35) == QColor("#FFFF00")

    def test_transparent_background_keeps_alpha(self, sketch):
        sketch.layers[0].elements[0].fill_color = "#80FF0000"

        image = render_image(sketch, SketchExportOptions(transparent=True))

        assert _pixel(image, 2, 2).alpha() == 0
        assert _pixel(image, 40, 35).alpha() == pytest.approx(128, abs=1)

    def test_layer_opacity_is_applied(self, sketch):
        sketch.layers[0].opacity = 0.5

        image = render_image(sketch, SketchExportOptions(transparent=True))

        assert _pixel(image, 40, 35).alpha() == pytest.approx(128, abs=1)

    def test_scale_multiplies_the_pixels_and_the_dpi(self, sketch):
        image = render_image(sketch, SketchExportOptions(scale=2.0))

        assert (image.width(), image.height()) == (400, 200)
        assert _pixel(image, 80, 70) == RED
        assert image.dotsPerMeterX() == round(2 * BASE_DPI / 0.0254)

    def test_elements_region_crops(self, sketch):
        image = render_image(sketch, SketchExportOptions(region=ExportRegion.ELEMENTS, padding=10.0))

        assert (image.width(), image.height()) == (60, 50)
        assert _pixel(image, 30, 25) == RED
        assert _pixel(image, 2, 2) == QColor("#FFFF00")

    def test_empty_region_is_refused(self, sketch):
        with pytest.raises(SketchExportError, match="nothing to export"):
            render_image(sketch, SketchExportOptions(region=ExportRegion.ELEMENTS, layer_ids=frozenset()))

    def test_too_large_an_image_is_refused(self, sketch):
        with pytest.raises(SketchExportError, match="too large"):
            render_image(sketch, SketchExportOptions(scale=(MAX_RASTER_PIXELS / 20000) ** 0.5 + 1))


class TestFiles:
    def test_png(self, sketch, tmp_path):
        path = tmp_path / "boxes.png"

        export_sketch(sketch, path, SketchExportOptions(transparent=True, scale=2.0))

        image = QImage(str(path))
        assert (image.width(), image.height()) == (400, 200)
        assert image.hasAlphaChannel()
        assert _pixel(image, 2, 2).alpha() == 0

    def test_jpeg_is_opaque(self, sketch, tmp_path):
        path = tmp_path / "boxes.jpg"

        export_sketch(sketch, path, SketchExportOptions(format=ExportFormat.JPEG))

        image = QImage(str(path))
        assert (image.width(), image.height()) == (200, 100)
        assert not image.hasAlphaChannel()
        # JPEG is lossy: compare loosely.
        background = _pixel(image, 2, 2)
        assert (background.red(), background.green(), background.blue()) == pytest.approx((255, 255, 0), abs=8)

    def test_svg_is_sized_in_canvas_pixels_and_has_no_background_when_transparent(self, sketch, tmp_path):
        path = tmp_path / "boxes.svg"

        export_sketch(sketch, path, SketchExportOptions(format=ExportFormat.SVG, transparent=True))

        root = ET.parse(path).getroot()
        assert root.get("viewBox") == "0 0 200 100"
        # 200 CSS pixels at 96 per inch.
        width = root.get("width")
        assert width is not None and width.endswith("mm")
        assert float(width.removesuffix("mm")) == pytest.approx(200 / BASE_DPI * 25.4, abs=0.001)
        text = path.read_text()
        assert "<title>Boxes</title>" in text
        assert "#ffff00" not in text.lower()
        assert "#ff0000" in text.lower()

    def test_svg_with_background(self, sketch, tmp_path):
        path = tmp_path / "boxes.svg"

        export_sketch(sketch, path, SketchExportOptions(format=ExportFormat.SVG))

        assert "#ffff00" in path.read_text().lower()

    def test_pdf_page_is_the_region_size_in_points(self, sketch, tmp_path):
        path = tmp_path / "boxes.pdf"

        export_sketch(sketch, path, SketchExportOptions(format=ExportFormat.PDF, region=ExportRegion.ELEMENTS, padding=5.0))

        data = path.read_bytes()
        assert data.startswith(b"%PDF")
        media_box = re.search(rb"/MediaBox \[0 0 ([\d.]+) ([\d.]+)\]", data)
        assert media_box is not None
        assert (float(media_box.group(1)), float(media_box.group(2))) == (50.0, 40.0)

    @pytest.mark.parametrize("export_format", list(ExportFormat))
    def test_an_unwritable_path_is_reported(self, sketch, tmp_path, export_format):
        path = tmp_path / "missing-folder" / f"boxes.{export_format.value}"

        with pytest.raises(SketchExportError):
            export_sketch(sketch, path, SketchExportOptions(format=export_format))


@dataclass(kw_only=True)
class _BadgeElement(SketchElement):
    """A made-up element type, standing in for a future domain module's own."""

    TYPE: ClassVar[str] = "test_badge"
    size: float = 10.0


def _build_badge(element: _BadgeElement) -> QGraphicsItem:
    item = QGraphicsRectItem(0.0, 0.0, element.size, element.size)
    item.setBrush(graphics_items.make_brush(element))
    item.setPen(graphics_items.make_pen(element))
    return item


def test_a_new_element_type_registered_from_outside_is_drawn_and_exported(monkeypatch, sketch):
    """The extension seam (#364): a module adds a type to ELEMENT_TYPES and a
    builder to GRAPHICS_ITEM_BUILDERS, and export draws it, without editing
    the built-in element modules."""
    monkeypatch.setitem(ELEMENT_TYPES, _BadgeElement.TYPE, _BadgeElement)
    monkeypatch.setitem(graphics_items.GRAPHICS_ITEM_BUILDERS, _BadgeElement, _build_badge)
    badge = SketchElement.from_dict({"type": "test_badge", "x": 150.0, "y": 60.0, "stroke_width": 0.0, "fill_color": "#0000FF"})
    assert isinstance(badge, _BadgeElement)
    sketch.add_element("bottom", badge)

    image = render_image(sketch, SketchExportOptions())

    assert _pixel(image, 155, 65) == BLUE


def test_export_never_includes_canvas_overlays(qtbot, monkeypatch, tmp_path):
    """A selection box and handles on the canvas are not part of the export."""
    from pandaplot.app import build_app_context
    from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas

    monkeypatch.setenv("HOME", str(tmp_path))
    sketch = Sketch(canvas_width=200.0, canvas_height=100.0, background_color="#FFFF00", layers=[SketchLayer(elements=[
        RectangleElement(id="box", x=20.0, y=20.0, width=40.0, height=30.0, stroke_width=0.0, fill_color="#FF0000"),
    ])])
    canvas = SketchCanvas(sketch, app_context=build_app_context())
    qtbot.addWidget(canvas)
    canvas.set_selection(["box"])

    image = render_image(sketch, SketchExportOptions())

    # Where the selection box's top-left handle (white, accent-edged) sits on the canvas.
    assert canvas.handle_at(canvas.mapToScene(canvas.mapFromScene(18.0, 18.0))) is not None
    assert _pixel(image, 20, 20) == RED
    assert _pixel(image, 18, 18) == QColor("#FFFF00")
