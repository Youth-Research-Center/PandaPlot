from unittest.mock import patch

import pytest
from PySide6.QtCore import QBuffer, QIODevice, QSize
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


@pytest.mark.parametrize(("size", "expected"), [((4000, 1), (800, 1)), ((9000, 4), (800, 1)), ((2, 5000), (1, 800))])
def test_from_file_keeps_a_very_thin_image(tmp_path, size, expected):
    # Scaling these into 800x800 rounds the short side down to 0, which Qt cannot decode into.
    path = tmp_path / "strip.png"
    path.write_bytes(_encode(*size))
    out = QImage.fromData(prepare_cover_image_from_file(path))
    assert (out.width(), out.height()) == expected


def test_from_file_caps_the_size_when_the_reader_cannot_report_it(tmp_path):
    path = tmp_path / "big.png"
    path.write_bytes(_encode(2000, 1000))
    with patch.object(cover_image.QImageReader, "size", return_value=QSize()):
        out = QImage.fromData(prepare_cover_image_from_file(path))
    assert (out.width(), out.height()) == (800, 400)


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


def test_from_file_applies_exif_orientation(tmp_path):
    pytest.importorskip("PIL")
    path = tmp_path / "photo.jpg"
    path.write_bytes(_exif_jpeg(100, 50, 6))
    out = QImage.fromData(prepare_cover_image_from_file(path))
    assert (out.width(), out.height()) == (50, 100)


@pytest.mark.parametrize(("size", "expected"), [((4000, 1), (800, 1)), ((9000, 4), (800, 1)), ((2, 5000), (1, 800))])
def test_bytes_keep_a_very_thin_image(size, expected):
    out = QImage.fromData(prepare_cover_image(_encode(*size)))
    assert (out.width(), out.height()) == expected
