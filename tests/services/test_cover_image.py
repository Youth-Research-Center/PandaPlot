from unittest.mock import patch

import pytest
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QColor, QImage

from pandaplot.services.project import cover_image
from pandaplot.services.project.cover_image import MAX_COVER_FILE_BYTES, prepare_cover_image, prepare_cover_image_from_file
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


def test_from_file_downscales_while_decoding(tmp_path):
    path = tmp_path / "big.png"
    path.write_bytes(_encode(2000, 1000))
    with patch.object(cover_image.QImage, "scaled", side_effect=AssertionError("must not rescale after decoding")):
        out = QImage.fromData(prepare_cover_image_from_file(path))
    assert (out.width(), out.height()) == (800, 400)


def test_from_file_never_upscales(tmp_path):
    path = tmp_path / "small.png"
    path.write_bytes(_encode(300, 200))
    out = QImage.fromData(prepare_cover_image_from_file(path))
    assert (out.width(), out.height()) == (300, 200)


def test_from_file_rejects_files_over_the_size_limit_without_reading_them(tmp_path):
    path = tmp_path / "huge.png"
    path.write_bytes(_encode(10, 10))
    with (
        patch.object(cover_image, "MAX_COVER_FILE_BYTES", 5),
        patch.object(cover_image, "QImageReader", side_effect=AssertionError("must not decode")),
        pytest.raises(UserFacingError, match="too large"),
    ):
        prepare_cover_image_from_file(path)
    assert MAX_COVER_FILE_BYTES == 25 * 1024 * 1024


def test_from_file_non_image_raises_user_facing_error(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("not an image")
    with pytest.raises(UserFacingError, match="not an image"):
        prepare_cover_image_from_file(path)
