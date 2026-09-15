from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QPageSize, QPainter, QPdfWriter
from PySide6.QtSvg import QSvgGenerator

from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas


class SketchExporter:
    """Utility service for exporting a SketchCanvas to raster or vector image formats."""

    @staticmethod
    def export_to_image(
        canvas: SketchCanvas,
        filepath: str,
        format_str: str = "PNG",
        dpi: int = 300,
        transparent: bool = False,
    ) -> bool:
        """Export sketch canvas scene to PNG, JPEG, SVG, or PDF."""
        scene = canvas.scene()
        rect = scene.sceneRect()

        scale_factor = dpi / 72.0
        target_width = max(1, int(rect.width() * scale_factor))
        target_height = max(1, int(rect.height() * scale_factor))

        fmt_lower = format_str.lower()

        if fmt_lower == "svg":
            svg = QSvgGenerator()
            svg.setFileName(filepath)
            svg.setSize(QSizeF(rect.width(), rect.height()).toSize())
            svg.setViewBox(rect)
            painter = QPainter(svg)
            if not transparent:
                painter.fillRect(rect, QColor(canvas.sketch.background_color))
            scene.render(painter, QRectF(0, 0, rect.width(), rect.height()), rect)
            painter.end()
            return True

        elif fmt_lower == "pdf":
            writer = QPdfWriter(filepath)
            writer.setPageSize(QPageSize(QSizeF(rect.width(), rect.height()), QPageSize.Unit.Point))
            writer.setPageMargins(QMarginsF(0, 0, 0, 0))
            painter = QPainter(writer)
            if not transparent:
                painter.fillRect(rect, QColor(canvas.sketch.background_color))
            scene.render(painter)
            painter.end()
            return True

        else:
            image_format = QImage.Format_ARGB32 if transparent else QImage.Format_RGB32
            image = QImage(target_width, target_height, image_format)
            if transparent:
                image.fill(Qt.transparent)
            else:
                image.fill(QColor(canvas.sketch.background_color))

            painter = QPainter(image)
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
            scene.render(painter, QRectF(0, 0, target_width, target_height), rect)
            painter.end()

            return image.save(filepath, format_str.upper())
