"""Tests for CreateImageFromBytesCommand -- adds an Image item built from
already-in-memory bytes (e.g. a rendered chart snapshot), unlike
ImportImagesCommand which only imports from a file path or URL."""
from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.image.create_image_from_bytes_command import CreateImageFromBytesCommand
from pandaplot.models.project.items import Image, ImageGallery


def test_execute_creates_a_copied_image_in_the_gallery(app_context_with_project):
    project = app_context_with_project.get_app_state().current_project
    gallery = ImageGallery(name="Chart Snapshots")
    project.add_item(gallery)

    command = CreateImageFromBytesCommand(
        app_context_with_project, gallery_id=gallery.id, name="My Chart",
        png_bytes=b"fake-png-bytes", width=100, height=80,
    )
    assert command.execute() is CommandResult.SUCCESS
    assert command.created_image_id is not None

    image = project.find_item(command.created_image_id)
    assert isinstance(image, Image)
    assert image.name == "My Chart"
    assert image.storage_mode == "copied"
    assert image.width == 100
    assert image.height == 80
    assert image.get_bytes() == b"fake-png-bytes"
    assert image.parent_id == gallery.id


def test_execute_fails_when_gallery_not_found(app_context_with_project):
    command = CreateImageFromBytesCommand(
        app_context_with_project, gallery_id="missing-gallery", name="My Chart",
        png_bytes=b"fake-png-bytes", width=100, height=80,
    )
    assert command.execute() is CommandResult.FAILURE
    assert command.created_image_id is None


def test_undo_then_redo_restores_the_image(app_context_with_project):
    project = app_context_with_project.get_app_state().current_project
    gallery = ImageGallery(name="Chart Snapshots")
    project.add_item(gallery)

    command = CreateImageFromBytesCommand(
        app_context_with_project, gallery_id=gallery.id, name="My Chart",
        png_bytes=b"fake-png-bytes", width=100, height=80,
    )
    command.execute()
    image_id = command.created_image_id

    assert command.undo() is CommandResult.SUCCESS
    assert project.find_item(image_id) is None

    assert command.redo() is CommandResult.SUCCESS
    restored = project.find_item(image_id)
    assert isinstance(restored, Image)
    assert restored.get_bytes() == b"fake-png-bytes"
