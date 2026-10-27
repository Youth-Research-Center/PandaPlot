"""Renders a Sketch to PNG, JPEG, SVG or PDF.

Export draws the model into its own offscreen scene, not the canvas's, so
the selection box, handles and tool previews never reach the file.
"""
import math
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, QSize, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QImageWriter, QPageLayout, QPageSize, QPaintDevice, QPainter, QPdfWriter
from PySide6.QtSvg import QSvgGenerator
from PySide6.QtWidgets import QGraphicsScene

from pandaplot.gui.components.tabs.sketch.graphics_items import add_layer_items
from pandaplot.models.project.items.sketch import Sketch, SketchLayer

# Raster images larger than this many pixels are refused, well below what
# QImage can allocate, so a mistyped scale fails with a message, not a crash.
MAX_RASTER_PIXELS = 100_000_000
# Pixels per inch a 1x raster export is tagged with; a 2x export is tagged
# with twice this, so both print at the same physical size.
BASE_DPI = 96


class ExportFormat(StrEnum):
    PNG = "png"
    JPEG = "jpeg"
    SVG = "svg"
    PDF = "pdf"


@dataclass(frozen=True)
class FormatInfo:
    label: str
    extension: str
    # Raster formats are sized by the scale; vector ones keep canvas units.
    raster: bool
    supports_transparency: bool


FORMATS: dict[ExportFormat, FormatInfo] = {
    ExportFormat.PNG: FormatInfo("PNG image", ".png", raster=True, supports_transparency=True),
    ExportFormat.JPEG: FormatInfo("JPEG image", ".jpg", raster=True, supports_transparency=False),
    ExportFormat.SVG: FormatInfo("SVG vector image", ".svg", raster=False, supports_transparency=True),
    ExportFormat.PDF: FormatInfo("PDF document", ".pdf", raster=False, supports_transparency=False),
}


class ExportRegion(StrEnum):
    # The whole canvas_width x canvas_height paper.
    CANVAS = "canvas"
    # The drawn elements' bounds plus padding.
    ELEMENTS = "elements"


class SketchExportError(Exception):
    """The sketch can't be exported with the given options; the message is for the user."""


@dataclass(frozen=True, kw_only=True)
class SketchExportOptions:
    """How to export a sketch.

    Attributes:
        format: File format.
        region: Whole canvas, or the drawn elements' bounds plus `padding`.
        transparent: Leave the background out (PNG and SVG only).
        scale: Output pixels per canvas unit, for raster formats.
        padding: Space around the elements for `ExportRegion.ELEMENTS`.
        layer_ids: Layers to draw; None draws the visible layers. A chosen
            layer is drawn even if it is hidden on the canvas.
    """

    format: ExportFormat = ExportFormat.PNG
    region: ExportRegion = ExportRegion.CANVAS
    transparent: bool = False
    scale: float = 1.0
    padding: float = 10.0
    layer_ids: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if not (math.isfinite(self.scale) and self.scale > 0):
            raise ValueError(f"scale must be positive, got {self.scale}")
        if not (math.isfinite(self.padding) and self.padding >= 0):
            raise ValueError(f"padding must be >= 0, got {self.padding}")
        if self.transparent and not FORMATS[self.format].supports_transparency:
            raise ValueError(f"{self.format.value} can't have a transparent background")


def exported_layers(sketch: Sketch, options: SketchExportOptions) -> list[SketchLayer]:
    """The layers to draw, bottom first."""
    if options.layer_ids is None:
        return [layer for layer in sketch.layers if layer.visible]
    return [layer for layer in sketch.layers if layer.id in options.layer_ids]


def _build_scene(sketch: Sketch, options: SketchExportOptions) -> QGraphicsScene:
    scene = QGraphicsScene()
    layer_items, _element_items = add_layer_items(scene, exported_layers(sketch, options))
    for layer_item in layer_items.values():
        layer_item.setVisible(True)
    return scene


def export_rect(sketch: Sketch, options: SketchExportOptions) -> QRectF | None:
    """The canvas area to export, or None if it would be empty (no elements
    on the chosen layers, for `ExportRegion.ELEMENTS`)."""
    if options.region is ExportRegion.CANVAS:
        return QRectF(0.0, 0.0, sketch.canvas_width, sketch.canvas_height)
    bounds = _build_scene(sketch, options).itemsBoundingRect()
    if bounds.isEmpty():
        return None
    padding = options.padding
    return bounds.adjusted(-padding, -padding, padding, padding)


def output_size(rect: QRectF, options: SketchExportOptions) -> QSize:
    """Size of the exported file: pixels for raster formats, canvas units
    (pixels in SVG, points in PDF) for vector ones."""
    scale = options.scale if FORMATS[options.format].raster else 1.0
    return QSize(max(1, math.ceil(rect.width() * scale)), max(1, math.ceil(rect.height() * scale)))


def _background(sketch: Sketch, options: SketchExportOptions) -> QColor | None:
    if options.transparent:
        return None
    color = QColor(sketch.background_color)
    return color if color.isValid() else QColor(Qt.GlobalColor.white)


def _paint(sketch: Sketch, options: SketchExportOptions, device: QPaintDevice, target: QRectF, source: QRectF) -> None:
    scene = _build_scene(sketch, options)
    painter = QPainter(device)
    if not painter.isActive():
        # E.g. the SVG or PDF file could not be opened for writing.
        raise SketchExportError("Could not start drawing the export; check that the file can be written.")
    try:
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
        background = _background(sketch, options)
        if background is not None:
            painter.fillRect(target, background)
        scene.render(painter, target, source, Qt.AspectRatioMode.IgnoreAspectRatio)
    finally:
        painter.end()


def _require_rect(sketch: Sketch, options: SketchExportOptions) -> QRectF:
    rect = export_rect(sketch, options)
    if rect is None:
        raise SketchExportError("There is nothing to export: the chosen layers have no elements.")
    return rect


def render_image(sketch: Sketch, options: SketchExportOptions) -> QImage:
    """Render the sketch to an image of `output_size()` pixels.

    Raises:
        SketchExportError: If the region is empty or the image would be too large.
    """
    rect = _require_rect(sketch, options)
    size = output_size(rect, options)
    if size.width() * size.height() > MAX_RASTER_PIXELS:
        raise SketchExportError(
            f"The image would be {size.width()} x {size.height()} pixels, which is too large. Choose a smaller scale or region.",
        )
    image_format = QImage.Format.Format_ARGB32_Premultiplied if options.transparent else QImage.Format.Format_RGB32
    image = QImage(size, image_format)
    image.fill(Qt.GlobalColor.transparent)
    dots_per_meter = round(BASE_DPI * options.scale / 0.0254)
    image.setDotsPerMeterX(dots_per_meter)
    image.setDotsPerMeterY(dots_per_meter)
    _paint(sketch, options, image, QRectF(0.0, 0.0, size.width(), size.height()), rect)
    return image


def _export_raster(sketch: Sketch, path: Path, options: SketchExportOptions) -> None:
    image = render_image(sketch, options)
    writer = QImageWriter(str(path), b"png" if options.format is ExportFormat.PNG else b"jpeg")
    writer.setQuality(95)
    if not writer.write(image):
        raise SketchExportError(f"Could not write '{path}': {writer.errorString()}")


def _export_svg(sketch: Sketch, path: Path, options: SketchExportOptions) -> None:
    rect = _require_rect(sketch, options)
    size = output_size(rect, options)
    generator = QSvgGenerator()
    generator.setFileName(str(path))
    generator.setSize(size)
    # CSS pixels, so the file's physical size reads as `size` pixels.
    generator.setResolution(BASE_DPI)
    generator.setViewBox(QRectF(0.0, 0.0, size.width(), size.height()))
    generator.setTitle(sketch.name)
    _paint(sketch, options, generator, QRectF(0.0, 0.0, size.width(), size.height()), rect)


def _export_pdf(sketch: Sketch, path: Path, options: SketchExportOptions) -> None:
    rect = _require_rect(sketch, options)
    size = output_size(rect, options)
    writer = QPdfWriter(str(path))
    writer.setTitle(sketch.name)
    # One canvas unit per point, on a page exactly the region's size.
    writer.setResolution(72)
    page_size = QPageSize(QSizeF(size.width(), size.height()), QPageSize.Unit.Point, sketch.name, QPageSize.SizeMatchPolicy.ExactMatch)
    writer.setPageLayout(QPageLayout(page_size, QPageLayout.Orientation.Portrait, QMarginsF(0.0, 0.0, 0.0, 0.0)))
    _paint(sketch, options, writer, QRectF(0.0, 0.0, size.width(), size.height()), rect)


_EXPORTERS = {
    ExportFormat.PNG: _export_raster,
    ExportFormat.JPEG: _export_raster,
    ExportFormat.SVG: _export_svg,
    ExportFormat.PDF: _export_pdf,
}


def export_sketch(sketch: Sketch, path: Path, options: SketchExportOptions) -> None:
    """Write the sketch to `path` in `options.format`.

    Raises:
        SketchExportError: If there is nothing to export, the output would be
            too large, or the file can't be written.
    """
    _EXPORTERS[options.format](sketch, path, options)
    if not path.is_file():
        raise SketchExportError(f"Could not write '{path}'.")
