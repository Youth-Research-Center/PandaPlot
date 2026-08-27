import logging

import pytest

from pandaplot.commands.project.image.copy_images_command import CopyImagesCommand
from pandaplot.commands.project.image.create_image_gallery_command import (
    CreateImageGalleryCommand,
)
from pandaplot.models.project.items import Image


@pytest.fixture
def gallery_id(app_context_with_project):
    command = CreateImageGalleryCommand(app_context_with_project, gallery_name="Trip")
    command.execute()
    return command.created_gallery_id


class TestCopyImagesCommandCopiedMode:
    def test_execute_creates_independent_duplicate_with_own_bytes(self, app_context_with_project, gallery_id):
        project = app_context_with_project.get_app_state().current_project
        original = Image(name="Beach", storage_mode="copied", image_ext="png", width=10, height=10, size_bytes=100)
        original.set_bytes(b"original-bytes")
        project.add_item(original, parent_id=gallery_id)

        command = CopyImagesCommand(app_context_with_project, image_ids=[original.id], target_gallery_id=gallery_id)

        assert command.execute() is True
        gallery = project.find_item(gallery_id)
        images = [c for c in gallery.get_items() if isinstance(c, Image)]
        assert len(images) == 2
        copy = next(i for i in images if i.id != original.id)
        assert copy.id != original.id
        assert copy.name == "Beach"
        assert copy.storage_mode == "copied"
        assert copy.width == 10 and copy.height == 10 and copy.size_bytes == 100
        assert copy.get_bytes() == b"original-bytes"

        # Independence: mutating the copy's bytes must not affect the original
        copy.set_bytes(b"mutated")
        assert original.get_bytes() == b"original-bytes"

    def test_created_image_ids_populated(self, app_context_with_project, gallery_id):
        project = app_context_with_project.get_app_state().current_project
        original = Image(name="Beach", storage_mode="copied", image_ext="png")
        original.set_bytes(b"data")
        project.add_item(original, parent_id=gallery_id)

        command = CopyImagesCommand(app_context_with_project, image_ids=[original.id], target_gallery_id=gallery_id)
        command.execute()

        assert len(command.created_image_ids) == 1
        assert command.created_image_ids[0] != original.id


class TestCopyImagesCommandExternalMode:
    def test_execute_copy_shares_same_source_file(self, app_context_with_project, gallery_id):
        project = app_context_with_project.get_app_state().current_project
        original = Image(name="Linked", storage_mode="external", source_file="/tmp/photo.png", image_ext="png")
        project.add_item(original, parent_id=gallery_id)

        command = CopyImagesCommand(app_context_with_project, image_ids=[original.id], target_gallery_id=gallery_id)
        assert command.execute() is True

        gallery = project.find_item(gallery_id)
        images = [c for c in gallery.get_items() if isinstance(c, Image)]
        copy = next(i for i in images if i.id != original.id)
        assert copy.storage_mode == "external"
        assert copy.source_file == "/tmp/photo.png"
        assert copy.get_bytes() is None


class TestCopyImagesCommandBatchAndCrossGallery:
    def test_copies_multiple_images_in_one_command(self, app_context_with_project, gallery_id):
        project = app_context_with_project.get_app_state().current_project
        img1 = Image(name="A", storage_mode="copied", image_ext="png")
        img1.set_bytes(b"a")
        img2 = Image(name="B", storage_mode="copied", image_ext="png")
        img2.set_bytes(b"b")
        project.add_item(img1, parent_id=gallery_id)
        project.add_item(img2, parent_id=gallery_id)

        command = CopyImagesCommand(app_context_with_project, image_ids=[img1.id, img2.id], target_gallery_id=gallery_id)
        assert command.execute() is True
        assert len(command.created_image_ids) == 2

    def test_copies_to_a_different_gallery(self, app_context_with_project, gallery_id):
        project = app_context_with_project.get_app_state().current_project
        original = Image(name="Beach", storage_mode="copied", image_ext="png")
        original.set_bytes(b"data")
        project.add_item(original, parent_id=gallery_id)

        other_gallery_command = CreateImageGalleryCommand(app_context_with_project, gallery_name="Other")
        other_gallery_command.execute()
        other_gallery_id = other_gallery_command.created_gallery_id

        command = CopyImagesCommand(app_context_with_project, image_ids=[original.id], target_gallery_id=other_gallery_id)
        assert command.execute() is True

        source_gallery = project.find_item(gallery_id)
        target_gallery = project.find_item(other_gallery_id)
        assert len([c for c in source_gallery.get_items() if isinstance(c, Image)]) == 1, "original stays put"
        assert len([c for c in target_gallery.get_items() if isinstance(c, Image)]) == 1, "copy lands in target"


class TestCopyImagesCommandLogging:
    def test_execute_logs_a_warning_when_current_project_is_none(self, app_context_with_project, caplog):
        app_context_with_project.get_app_state().current_project = None

        command = CopyImagesCommand(
            app_context_with_project, image_ids=[], target_gallery_id="some-gallery"
        )

        with caplog.at_level(logging.WARNING):
            assert command.execute() is False
        assert "CopyImagesCommand.execute" in caplog.text

    def test_execute_logs_a_warning_when_target_gallery_not_found(self, app_context_with_project, caplog):
        command = CopyImagesCommand(
            app_context_with_project, image_ids=[], target_gallery_id="missing-gallery"
        )

        with caplog.at_level(logging.WARNING):
            assert command.execute() is False
        assert "missing-gallery" in caplog.text

    def test_execute_logs_a_warning_when_image_not_found(self, app_context_with_project, gallery_id, caplog):
        command = CopyImagesCommand(
            app_context_with_project, image_ids=["missing-image"], target_gallery_id=gallery_id
        )

        with caplog.at_level(logging.WARNING):
            assert command.execute() is False
        assert "missing-image" in caplog.text


class TestCopyImagesCommandCleanup:
    def test_cleanup_resets_created_image_ids_and_project(self, app_context_with_project, gallery_id):
        project = app_context_with_project.get_app_state().current_project
        original = Image(name="Beach", storage_mode="copied", image_ext="png")
        original.set_bytes(b"data")
        project.add_item(original, parent_id=gallery_id)

        command = CopyImagesCommand(app_context_with_project, image_ids=[original.id], target_gallery_id=gallery_id)
        command.execute()
        assert command.created_image_ids != []
        assert command.project is project

        command.cleanup()

        assert command.created_image_ids == []
        assert command.project is None


class TestCopyImagesCommandUndo:
    def test_undo_removes_all_created_copies(self, app_context_with_project, gallery_id):
        project = app_context_with_project.get_app_state().current_project
        original = Image(name="Beach", storage_mode="copied", image_ext="png")
        original.set_bytes(b"data")
        project.add_item(original, parent_id=gallery_id)

        command = CopyImagesCommand(app_context_with_project, image_ids=[original.id], target_gallery_id=gallery_id)
        command.execute()
        copy_id = command.created_image_ids[0]

        command.undo()

        assert project.find_item(copy_id) is None
        assert project.find_item(original.id) is not None, "original must survive undo"
