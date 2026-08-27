import datetime
import logging
import os
from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage

from pandaplot.commands.project.image.create_image_gallery_command import (
    CreateImageGalleryCommand,
)
from pandaplot.commands.project.image.import_images_command import ImportImagesCommand
from pandaplot.models.project.items import Image


def _write_test_png(path):
    image = QImage(4, 3, QImage.Format.Format_RGB32)
    image.fill(0xFFFFFF)
    assert image.save(str(path), "PNG")


def _fake_png_bytes():
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image = QImage(2, 2, QImage.Format.Format_RGB32)
    image.fill(0x000000)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


@pytest.fixture
def gallery_id(app_context_with_project):
    command = CreateImageGalleryCommand(app_context_with_project, gallery_name="Trip")
    command.execute()
    return command.created_gallery_id


class TestImportImagesCommandCopyMode:
    def test_execute_creates_copied_image_with_bytes(self, app_context_with_project, gallery_id, tmp_path):
        png_path = tmp_path / "photo.png"
        _write_test_png(png_path)

        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=[str(png_path)], copy_into_project=True,
        )

        assert command.execute() is True
        project = app_context_with_project.get_app_state().current_project
        gallery = project.find_item(gallery_id)
        images = gallery.get_items()
        assert len(images) == 1
        image = images[0]
        assert isinstance(image, Image)
        assert image.name == "photo"
        assert image.storage_mode == "copied"
        assert image.image_ext == "png"
        assert image.width == 4
        assert image.height == 3
        assert image.get_bytes() is not None

    def test_execute_multiple_sources_creates_multiple_images(self, app_context_with_project, gallery_id, tmp_path):
        paths = []
        for name in ("a.png", "b.png"):
            p = tmp_path / name
            _write_test_png(p)
            paths.append(str(p))

        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=paths, copy_into_project=True,
        )

        assert command.execute() is True
        project = app_context_with_project.get_app_state().current_project
        gallery = project.find_item(gallery_id)
        assert len(gallery.get_items()) == 2

    def test_undo_removes_all_created_images(self, app_context_with_project, gallery_id, tmp_path):
        png_path = tmp_path / "photo.png"
        _write_test_png(png_path)
        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=[str(png_path)], copy_into_project=True,
        )
        command.execute()

        command.undo()

        project = app_context_with_project.get_app_state().current_project
        gallery = project.find_item(gallery_id)
        assert gallery.get_items() == []


class TestImportImagesCommandCleanup:
    def test_cleanup_resets_created_image_ids_and_project(self, app_context_with_project, gallery_id, tmp_path):
        png_path = tmp_path / "photo.png"
        _write_test_png(png_path)
        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=[str(png_path)], copy_into_project=True,
        )
        command.execute()
        assert command.created_image_ids != []
        assert command.project is not None

        command.cleanup()

        assert command.created_image_ids == []
        assert command.project is None


class TestImportImagesCommandExternalMode:
    def test_execute_creates_external_image_without_bytes(self, app_context_with_project, gallery_id, tmp_path):
        png_path = tmp_path / "linked.png"
        _write_test_png(png_path)

        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=[str(png_path)], copy_into_project=False,
        )

        assert command.execute() is True
        project = app_context_with_project.get_app_state().current_project
        gallery = project.find_item(gallery_id)
        image = gallery.get_items()[0]
        assert image.storage_mode == "external"
        assert image.source_file == str(png_path)
        assert image.get_bytes() is None


class TestImportImagesCommandErrors:
    def test_execute_fails_when_gallery_not_found(self, app_context_with_project, tmp_path):
        png_path = tmp_path / "photo.png"
        _write_test_png(png_path)

        command = ImportImagesCommand(
            app_context_with_project, gallery_id="does-not-exist",
            sources=[str(png_path)], copy_into_project=True,
        )

        assert command.execute() is False

    def test_execute_fails_when_file_missing(self, app_context_with_project, gallery_id):
        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=["/no/such/file.png"], copy_into_project=True,
        )

        assert command.execute() is False


class TestImportImagesCommandLogging:
    def test_execute_logs_a_warning_when_current_project_is_none(self, app_context_with_project, caplog):
        app_context_with_project.get_app_state().current_project = None

        command = ImportImagesCommand(
            app_context_with_project, gallery_id="some-gallery", sources=["/no/such/file.png"],
        )

        with caplog.at_level(logging.WARNING):
            assert command.execute() is False
        assert "ImportImagesCommand.execute" in caplog.text

    def test_execute_logs_a_warning_when_gallery_not_found(self, app_context_with_project, tmp_path, caplog):
        png_path = tmp_path / "photo.png"
        _write_test_png(png_path)

        command = ImportImagesCommand(
            app_context_with_project, gallery_id="does-not-exist",
            sources=[str(png_path)], copy_into_project=True,
        )

        with caplog.at_level(logging.WARNING):
            assert command.execute() is False
        assert "does-not-exist" in caplog.text

    def test_execute_logs_a_warning_when_no_sources_given(self, app_context_with_project, gallery_id, caplog):
        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id, sources=[],
        )

        with caplog.at_level(logging.WARNING):
            assert command.execute() is False
        assert gallery_id in caplog.text


class TestImportImagesCommandModifiedTime:
    def test_copied_local_file_uses_file_mtime(self, app_context_with_project, gallery_id, tmp_path):
        png_path = tmp_path / "photo.png"
        _write_test_png(png_path)
        expected_mtime_iso = datetime.datetime.fromtimestamp(os.path.getmtime(png_path)).isoformat()

        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=[str(png_path)], copy_into_project=True,
        )
        command.execute()

        image = app_context_with_project.get_app_state().current_project.find_item(gallery_id).get_items()[0]
        assert image.modified_at == expected_mtime_iso
        assert image.created_at == expected_mtime_iso

    def test_external_local_file_uses_file_mtime(self, app_context_with_project, gallery_id, tmp_path):
        png_path = tmp_path / "photo.png"
        _write_test_png(png_path)
        expected_mtime_iso = datetime.datetime.fromtimestamp(os.path.getmtime(png_path)).isoformat()

        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=[str(png_path)], copy_into_project=False,
        )
        command.execute()

        image = app_context_with_project.get_app_state().current_project.find_item(gallery_id).get_items()[0]
        assert image.modified_at == expected_mtime_iso

    @patch("pandaplot.commands.project.image.import_images_command.requests.get")
    def test_url_import_keeps_constructor_default_time(self, mock_get, app_context_with_project, gallery_id):
        mock_response = Mock()
        mock_response.content = _fake_png_bytes()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        before = datetime.datetime.now()
        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=["https://example.com/pic.png"], copy_into_project=True,
        )
        command.execute()
        after = datetime.datetime.now()

        image = app_context_with_project.get_app_state().current_project.find_item(gallery_id).get_items()[0]
        modified = datetime.datetime.fromisoformat(image.modified_at)
        assert before <= modified <= after


class TestImportImagesCommandSizeBytes:
    def test_copied_local_file_gets_size_bytes(self, app_context_with_project, gallery_id, tmp_path):
        png_path = tmp_path / "photo.png"
        _write_test_png(png_path)
        expected_size = png_path.stat().st_size

        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=[str(png_path)], copy_into_project=True,
        )
        command.execute()

        image = app_context_with_project.get_app_state().current_project.find_item(gallery_id).get_items()[0]
        assert image.size_bytes == expected_size

    def test_external_local_file_gets_size_bytes(self, app_context_with_project, gallery_id, tmp_path):
        png_path = tmp_path / "photo.png"
        _write_test_png(png_path)
        expected_size = png_path.stat().st_size

        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=[str(png_path)], copy_into_project=False,
        )
        command.execute()

        image = app_context_with_project.get_app_state().current_project.find_item(gallery_id).get_items()[0]
        assert image.size_bytes == expected_size

    @patch("pandaplot.commands.project.image.import_images_command.requests.get")
    def test_external_url_has_no_size_bytes(self, mock_get, app_context_with_project, gallery_id):
        mock_response = Mock()
        mock_response.content = _fake_png_bytes()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=["https://example.com/pic.png"], copy_into_project=False,
        )
        command.execute()

        image = app_context_with_project.get_app_state().current_project.find_item(gallery_id).get_items()[0]
        assert image.size_bytes is None

    @patch("pandaplot.commands.project.image.import_images_command.requests.get")
    def test_copied_url_still_has_size_bytes_from_downloaded_data(self, mock_get, app_context_with_project, gallery_id):
        mock_response = Mock()
        mock_response.content = _fake_png_bytes()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=["https://example.com/pic.png"], copy_into_project=True,
        )
        command.execute()

        image = app_context_with_project.get_app_state().current_project.find_item(gallery_id).get_items()[0]
        assert image.size_bytes == len(_fake_png_bytes())


class TestImportImagesCommandUrlSource:
    @patch("pandaplot.commands.project.image.import_images_command.requests.get")
    def test_execute_copy_mode_downloads_url_bytes(self, mock_get, app_context_with_project, gallery_id):
        mock_response = Mock()
        mock_response.content = _fake_png_bytes()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=["https://example.com/pic.png"], copy_into_project=True,
        )

        assert command.execute() is True
        project = app_context_with_project.get_app_state().current_project
        image = project.find_item(gallery_id).get_items()[0]
        assert image.storage_mode == "copied"
        assert image.image_ext == "png"
        assert image.width == 2
        assert image.height == 2
        assert image.get_bytes() is not None
        mock_get.assert_called_once_with("https://example.com/pic.png", timeout=10)

    @patch("pandaplot.commands.project.image.import_images_command.requests.get")
    def test_execute_external_url_stores_only_reference(self, mock_get, app_context_with_project, gallery_id):
        mock_response = Mock()
        mock_response.content = _fake_png_bytes()
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=["https://example.com/pic.png"], copy_into_project=False,
        )

        assert command.execute() is True
        image = app_context_with_project.get_app_state().current_project.find_item(gallery_id).get_items()[0]
        assert image.storage_mode == "external"
        assert image.source_file == "https://example.com/pic.png"
        assert image.get_bytes() is None

    @patch("pandaplot.commands.project.image.import_images_command.requests.get")
    def test_execute_fails_gracefully_on_network_error(self, mock_get, app_context_with_project, gallery_id):
        import requests
        mock_get.side_effect = requests.RequestException("boom")

        command = ImportImagesCommand(
            app_context_with_project, gallery_id=gallery_id,
            sources=["https://example.com/pic.png"], copy_into_project=True,
        )

        assert command.execute() is False
