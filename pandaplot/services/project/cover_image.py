"""Preparation of a project's cover image before it is stored in the project."""

from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice, QSize, Qt
from PySide6.QtGui import QImage, QImageReader

from pandaplot.utils.errors import UserFacingError

DEFAULT_COVER_MAX_SIDE = 800
MAX_COVER_FILE_BYTES = 25 * 1024 * 1024


def prepare_cover_image(data: bytes, *, max_side: int = DEFAULT_COVER_MAX_SIDE) -> bytes:
    """Decode an image (applying its EXIF orientation), downscale it so its longest side is at most ``max_side``, and encode it as PNG.

    Images that already fit are never upscaled. Uses only ``QtGui``, so it is safe to call from commands.

    Args:
        data: Encoded image bytes in any format Qt can read.
        max_side: Maximum length of the longest side, in pixels.

    Returns:
        PNG-encoded bytes.

    Raises:
        UserFacingError: If ``data`` is not an image PandaPlot can read.
    """
    source = QBuffer()
    source.setData(data)
    source.open(QIODevice.OpenModeFlag.ReadOnly)
    return _encode_png(_read_bounded(QImageReader(source), max_side))


def prepare_cover_image_from_file(path: str | Path, *, max_side: int = DEFAULT_COVER_MAX_SIDE) -> bytes:
    """Read an image file, downscale it while decoding so its longest side is at most ``max_side``, and encode it as PNG.

    Files larger than ``MAX_COVER_FILE_BYTES`` are rejected before they are read, and the decoder scales
    large images down as it reads them, so a huge image never has to fit in memory at full size. If the
    decoder cannot report the size up front, the decoded image is scaled down afterwards instead.

    Args:
        path: Path of the image file.
        max_side: Maximum length of the longest side, in pixels.

    Returns:
        PNG-encoded bytes.

    Raises:
        UserFacingError: If the file is too large or is not an image PandaPlot can read.
        OSError: If the file cannot be accessed.
    """
    file_path = Path(path)
    if file_path.stat().st_size > MAX_COVER_FILE_BYTES:
        raise UserFacingError("The image file is too large. Choose an image under 25 MB.")
    return _encode_png(_read_bounded(QImageReader(str(file_path)), max_side))


def _read_bounded(reader: QImageReader, max_side: int) -> QImage:
    """Decode ``reader``'s image, applying its EXIF orientation, so its longest side is at most ``max_side``.

    The decoder scales a large image down while reading it when it can report the size up front; otherwise
    the decoded image is scaled down afterwards. Images that already fit are never upscaled.

    Args:
        reader: Reader positioned on the encoded image.
        max_side: Maximum length of the longest side, in pixels.

    Returns:
        The decoded image.

    Raises:
        UserFacingError: If the reader's data is not an image PandaPlot can read.
    """
    reader.setAutoTransform(True)
    size = reader.size()
    if size.isValid() and max(size.width(), size.height()) > max_side:
        reader.setScaledSize(_bounded_size(size, max_side))
    image = reader.read()
    if image.isNull():
        raise UserFacingError("This file is not an image PandaPlot can read.")
    if max(image.width(), image.height()) > max_side:
        image = image.scaled(_bounded_size(image.size(), max_side), mode=Qt.TransformationMode.SmoothTransformation)
    return image


def _bounded_size(size: QSize, max_side: int) -> QSize:
    """Return ``size`` scaled to fit in a ``max_side`` square, keeping each side at least 1 pixel.

    ``QSize.scaled`` rounds the short side of a very thin image down to 0, which Qt cannot decode or scale into.
    """
    scaled = size.scaled(max_side, max_side, Qt.AspectRatioMode.KeepAspectRatio)
    return QSize(max(1, scaled.width()), max(1, scaled.height()))


def _encode_png(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    # PySide6 accepts a str format at runtime; its stubs only list bytes.
    saved = image.save(buffer, "PNG")  # ty: ignore[no-matching-overload]
    if not saved:
        raise UserFacingError("This image could not be prepared as a cover image.")
    return bytes(buffer.data().data())
