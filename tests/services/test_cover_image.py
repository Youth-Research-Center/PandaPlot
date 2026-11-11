import pytest
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage

from pandaplot.services.project.cover_image import prepare_cover_image
from pandaplot.utils.errors import UserFacingError


def _encode(width: int, height: int, fmt: str = "PNG") -> bytes:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("red"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, fmt)
    return bytes(buffer.data())


def test_downscales_keeping_aspect_ratio():
    out = QImage.fromData(prepare_cover_image(_encode(2000, 1000)))
    assert (out.width(), out.height()) == (800, 400)


def test_downscales_portrait():
    out = QImage.fromData(prepare_cover_image(_encode(500, 1000), max_side=100))
    assert (out.width(), out.height()) == (50, 100)


def test_never_upscales():
    out = QImage.fromData(prepare_cover_image(_encode(300, 200)))
    assert (out.width(), out.height()) == (300, 200)


def test_output_is_png_even_from_other_formats():
    assert prepare_cover_image(_encode(50, 50, "JPG")).startswith(b"\x89PNG\r\n\x1a\n")


def test_non_image_bytes_raise_user_facing_error():
    with pytest.raises(UserFacingError, match="not an image"):
        prepare_cover_image(b"definitely not an image")


def _exif_jpeg(width: int, height: int, orientation: int) -> bytes:
    import io

    from PIL import Image

    image = Image.new("RGB", (width, height), "red")
    exif = Image.Exif()
    exif[0x0112] = orientation
    out = io.BytesIO()
    image.save(out, "JPEG", exif=exif)
    return out.getvalue()


def test_exif_orientation_is_applied():
    pytest.importorskip("PIL")
    # Stored 100x50 with orientation 6 (rotate 90 degrees) displays as 50x100.
    out = QImage.fromData(prepare_cover_image(_exif_jpeg(100, 50, 6)))
    assert (out.width(), out.height()) == (50, 100)


def test_extreme_aspect_ratio_keeps_at_least_one_pixel():
    out = QImage.fromData(prepare_cover_image(_encode(4000, 3)))
    assert not out.isNull()
    assert (out.width(), out.height()) == (800, 1)
