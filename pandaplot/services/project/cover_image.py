"""Preparation of a project's cover image before it is stored in the project."""

from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QImage

from pandaplot.utils.errors import UserFacingError

DEFAULT_COVER_MAX_SIDE = 800


def prepare_cover_image(data: bytes, *, max_side: int = DEFAULT_COVER_MAX_SIDE) -> bytes:
    """Decode an image, downscale it so its longest side is at most ``max_side``, and encode it as PNG.

    Images that already fit are never upscaled. Uses only ``QtGui``, so it is safe to call from commands.

    Args:
        data: Encoded image bytes in any format Qt can read.
        max_side: Maximum length of the longest side, in pixels.

    Returns:
        PNG-encoded bytes.

    Raises:
        UserFacingError: If ``data`` is not an image PandaPlot can read.
    """
    image = QImage.fromData(data)
    if image.isNull():
        raise UserFacingError("This file is not an image PandaPlot can read.")
    if max(image.width(), image.height()) > max_side:
        box = image.size().boundedTo(image.size().scaled(max_side, max_side, Qt.AspectRatioMode.KeepAspectRatio))
        image = image.scaled(box, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    # PySide6 accepts a str format at runtime; its stubs only list bytes.
    saved = image.save(buffer, "PNG")  # ty: ignore[no-matching-overload]
    if not saved:
        raise UserFacingError("This image could not be prepared as a cover image.")
    return bytes(buffer.data().data())
