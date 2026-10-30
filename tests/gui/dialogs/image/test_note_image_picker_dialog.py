"""Tests for NoteImagePickerDialog's background image fetch."""
import logging
from unittest.mock import Mock

from pandaplot.gui.dialogs.image.note_image_picker_dialog import NoteImagePickerDialog


def test_fetch_image_bytes_logs_and_returns_none_on_error(caplog):
    image = Mock()
    image.get_bytes.side_effect = OSError("disk gone")

    with caplog.at_level(logging.WARNING):
        assert NoteImagePickerDialog._fetch_image_bytes(image) is None

    records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(records) == 1
    assert records[0].exc_info is not None
