import io
from zipfile import ZipFile

from pandaplot.models.project.items.image import Image
from pandaplot.storage.image_data_manager import ImageDataManager


def _round_trip(image: Image) -> Image:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as zf:
        ImageDataManager().save(image, zf, "items/test-image")

    buffer.seek(0)
    with ZipFile(buffer, "r") as zf:
        return ImageDataManager().load(Image, zf, "items/test-image", schema_version=1)


class TestImageDataManagerCopied:
    def test_round_trip_stores_bytes_and_metadata(self):
        image = Image(id="img-1", name="Cat", storage_mode="copied", image_ext="png",
                       width=64, height=32, source_file="/tmp/cat.png")
        image.set_bytes(b"fake-png-bytes")

        loaded = _round_trip(image)

        assert loaded.id == "img-1"
        assert loaded.name == "Cat"
        assert loaded.storage_mode == "copied"
        assert loaded.image_ext == "png"
        assert loaded.width == 64
        assert loaded.height == 32
        assert loaded.get_bytes() == b"fake-png-bytes"

    def test_zip_contains_blob_entry(self):
        image = Image(id="img-2", name="Dog", storage_mode="copied", image_ext="jpg")
        image.set_bytes(b"jpeg-bytes")

        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as zf:
            ImageDataManager().save(image, zf, "items/img-2")
            names = zf.namelist()

        assert "items/img-2.jpg" in names
        assert "items/img-2.json" in names

    def test_save_with_missing_bytes_does_not_raise_and_skips_blob(self):
        """
        Regression test: an Image with storage_mode='copied' but no bytes in
        memory (e.g. restored via DeleteItemCommand.undo(), which recreates
        the item from to_dict()/from_dict() data that never includes bytes)
        must not abort the whole project save. Only the JSON metadata should
        be written; the blob entry should be skipped.
        """
        image = Image(id="img-5", name="Ghost", storage_mode="copied", image_ext="png")
        assert image.get_bytes() is None

        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as zf:
            ImageDataManager().save(image, zf, "items/img-5")  # must not raise
            names = zf.namelist()

        assert names == ["items/img-5.json"]

    def test_size_bytes_round_trips_through_save_load(self):
        image = Image(id="img-10", name="Sized", storage_mode="copied", image_ext="png",
                       width=10, height=10, size_bytes=12345)
        image.set_bytes(b"x" * 12345)

        loaded = _round_trip(image)

        assert loaded.size_bytes == 12345

    def test_load_with_missing_blob_does_not_raise(self):
        """
        Loading a 'copied' image whose blob entry is absent from the zip
        (the on-disk counterpart of the save-with-missing-bytes case above)
        must not crash with KeyError; bytes should just be None.
        """
        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as zf:
            zf.writestr(
                "items/img-6.json",
                '{"id": "img-6", "name": "Ghost", "storage_mode": "copied", "image_ext": "png"}',
            )

        buffer.seek(0)
        with ZipFile(buffer, "r") as zf:
            loaded = ImageDataManager().load(Image, zf, "items/img-6", schema_version=1)  # must not raise

        assert loaded.get_bytes() is None
        assert loaded.name == "Ghost"


class TestImageDataManagerExternal:
    def test_round_trip_stores_only_metadata(self):
        image = Image(id="img-3", name="Linked", storage_mode="external",
                       source_file="https://example.com/pic.png", image_ext="png",
                       width=10, height=10)

        loaded = _round_trip(image)

        assert loaded.storage_mode == "external"
        assert loaded.source_file == "https://example.com/pic.png"
        assert loaded.get_bytes() is None

    def test_zip_contains_no_blob_entry(self):
        image = Image(id="img-4", name="Linked", storage_mode="external",
                       source_file="/tmp/pic.png", image_ext="png")

        buffer = io.BytesIO()
        with ZipFile(buffer, "w") as zf:
            ImageDataManager().save(image, zf, "items/img-4")
            names = zf.namelist()

        assert names == ["items/img-4.json"]


class TestDeleteUndoSaveDoesNotCorruptProject:
    def test_delete_then_undo_then_save_does_not_raise(self, tmp_path):
        """
        Regression test for the reported corruption scenario: delete an Image
        (storage_mode='copied'), undo the delete (which recreates the Image
        via to_dict()/from_dict() -- and from_dict never carries bytes, by
        design), then save the project. This must not raise, and the saved
        zip must remain a valid project file containing project.json.
        """
        from unittest.mock import Mock

        from pandaplot.app import create_project_data_manager
        from pandaplot.commands.base_command import CommandResult
        from pandaplot.commands.project.item import DeleteItemCommand
        from pandaplot.models.project import Project
        from pandaplot.models.project.items import Image
        from pandaplot.models.state import AppContext, AppState

        project = Project("Test Project")
        image = Image(id="img-del-1", name="Cat", storage_mode="copied",
                      image_ext="png", width=10, height=10)
        image.set_bytes(b"real-bytes")
        project.add_item(image)

        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        app_state.has_project = True
        app_state.current_project = project
        app_state.event_bus = Mock()
        app_context.get_app_state.return_value = app_state
        ui_controller = Mock()
        ui_controller.show_question.return_value = True
        app_context.get_ui_controller.return_value = ui_controller

        command = DeleteItemCommand(app_context, item_id="img-del-1")
        assert command.execute() is CommandResult.SUCCESS
        assert project.find_item("img-del-1") is None

        assert command.undo() is CommandResult.SUCCESS
        restored = project.find_item("img-del-1")
        assert restored is not None
        assert restored.get_bytes() is None  # bytes are genuinely gone

        filepath = str(tmp_path / "project.pandaplot")
        manager = create_project_data_manager()
        manager.save(project, filepath)  # must not raise / must not corrupt the file

        # The saved file must be a valid, openable zip containing project.json.
        with ZipFile(filepath, "r") as zf:
            assert "project.json" in zf.namelist()

        reloaded = manager.load(filepath)
        reloaded_image = reloaded.find_item("img-del-1")
        assert reloaded_image is not None
        assert reloaded_image.get_bytes() is None


class TestImageRegisteredInFactory:
    def test_image_and_gallery_types_are_registered(self):
        from pandaplot.app import create_project_data_manager
        from pandaplot.models.project.items import Image, ImageGallery

        manager = create_project_data_manager()
        factory = manager.data_factory

        assert factory.resolve_item_class("image") is Image
        assert factory.resolve_item_class("imagegallery") is ImageGallery
