from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QImage

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.image.create_image_gallery_command import CreateImageGalleryCommand
from pandaplot.commands.project.image.edit_image_command import EditImageCommand
from pandaplot.models.project.items import Image


def _make_png_bytes(width: int = 10, height: int = 10) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(0xFF0000)
    img.save(buffer, "PNG")
    return bytes(buffer.data())


class TestEditImageCommand:
    def test_execute_and_undo_redo(self, app_context_with_project):
        # Create gallery and image
        gallery_cmd = CreateImageGalleryCommand(app_context_with_project, gallery_name="Gallery")
        gallery_cmd.execute()
        gallery_id = gallery_cmd.created_gallery_id

        project = app_context_with_project.get_app_state().current_project

        old_data = _make_png_bytes(20, 20)
        image = Image(id="img-edit-1", name="Original", width=20, height=20, storage_mode="external")
        image.set_bytes(old_data)
        project.add_item(image, parent_id=gallery_id)

        new_data = _make_png_bytes(10, 15)
        edit_cmd = EditImageCommand(
            app_context_with_project, image_id="img-edit-1",
            new_bytes=new_data, new_width=10, new_height=15, new_ext="png"
        )

        # Execute
        res = edit_cmd.execute()
        assert res is CommandResult.SUCCESS
        assert image.width == 10
        assert image.height == 15
        assert image.storage_mode == "copied"
        assert image.get_bytes() == new_data
        assert image.size_bytes == len(new_data)

        # Undo
        undo_res = edit_cmd.undo()
        assert undo_res is CommandResult.SUCCESS
        assert image.width == 20
        assert image.height == 20
        assert image.storage_mode == "external"
        assert image.get_bytes() == old_data

        # Redo
        redo_res = edit_cmd.redo()
        assert redo_res is CommandResult.SUCCESS
        assert image.width == 10
        assert image.height == 15
        assert image.get_bytes() == new_data

    def test_execute_emits_content_changed_not_renamed(self, app_context_with_project):
        from pandaplot.models.events.event_types import ProjectEvents

        gallery_cmd = CreateImageGalleryCommand(app_context_with_project, gallery_name="Gallery")
        gallery_cmd.execute()
        gallery_id = gallery_cmd.created_gallery_id
        project = app_context_with_project.get_app_state().current_project

        image = Image(id="img-edit-2", name="Original", width=20, height=20, storage_mode="external")
        image.set_bytes(_make_png_bytes(20, 20))
        project.add_item(image, parent_id=gallery_id)

        edit_cmd = EditImageCommand(
            app_context_with_project, image_id="img-edit-2",
            new_bytes=_make_png_bytes(10, 15), new_width=10, new_height=15, new_ext="png"
        )
        edit_cmd.execute()
        edit_cmd.undo()

        event_bus = app_context_with_project.get_app_state().event_bus
        emitted_types = [call.args[0] for call in event_bus.emit.call_args_list]
        assert emitted_types.count(ProjectEvents.PROJECT_ITEM_CONTENT_CHANGED) == 2
        assert ProjectEvents.PROJECT_ITEM_RENAMED not in emitted_types

    def test_cleanup_releases_the_held_byte_buffers(self, app_context_with_project):
        """Commands that retain undo snapshots must override cleanup() to
        release large held resources when dropped from the stacks outside
        the normal undo/redo lifecycle (see Command.cleanup) -- otherwise
        an evicted/cleared command keeps both image byte buffers alive
        through any remaining reference to it."""
        gallery_cmd = CreateImageGalleryCommand(app_context_with_project, gallery_name="Gallery")
        gallery_cmd.execute()
        gallery_id = gallery_cmd.created_gallery_id
        project = app_context_with_project.get_app_state().current_project

        old_data = _make_png_bytes(20, 20)
        image = Image(id="img-edit-3", name="Original", width=20, height=20, storage_mode="external")
        image.set_bytes(old_data)
        project.add_item(image, parent_id=gallery_id)

        new_data = _make_png_bytes(10, 15)
        edit_cmd = EditImageCommand(
            app_context_with_project, image_id="img-edit-3",
            new_bytes=new_data, new_width=10, new_height=15, new_ext="png"
        )
        edit_cmd.execute()
        assert edit_cmd.old_bytes == old_data
        assert edit_cmd.new_bytes == new_data

        edit_cmd.cleanup()

        assert edit_cmd.old_bytes is None
        assert edit_cmd.new_bytes == b""

    def test_redo_after_a_failed_undo_does_not_lose_the_original_bytes(self, app_context_with_project):
        """CommandExecutor pushes a command onto the redo stack even when
        undo() returns FAILURE (not just on success) -- undo()'s failure
        branches all return before restoring the item, so the item can
        still be in its edited (new) state when redo() runs next. redo()
        re-entering execute() must not recapture old_bytes at that point,
        or the true pre-edit snapshot would be silently replaced with the
        already-edited bytes, making the original permanently
        unrecoverable."""
        gallery_cmd = CreateImageGalleryCommand(app_context_with_project, gallery_name="Gallery")
        gallery_cmd.execute()
        gallery_id = gallery_cmd.created_gallery_id
        project = app_context_with_project.get_app_state().current_project

        old_data = _make_png_bytes(20, 20)
        image = Image(id="img-edit-4", name="Original", width=20, height=20, storage_mode="external")
        image.set_bytes(old_data)
        project.add_item(image, parent_id=gallery_id)

        new_data = _make_png_bytes(10, 15)
        edit_cmd = EditImageCommand(
            app_context_with_project, image_id="img-edit-4",
            new_bytes=new_data, new_width=10, new_height=15, new_ext="png"
        )
        edit_cmd.execute()
        assert edit_cmd.old_bytes == old_data

        # Simulate the item's undo failing without raising (e.g. the
        # project was momentarily unavailable) -- the image stays in its
        # edited state, exactly as CommandExecutor would leave it after
        # pushing this command onto the redo stack despite the FAILURE.
        app_state = app_context_with_project.get_app_state()
        app_state.has_project = False
        undo_res = edit_cmd.undo()
        assert undo_res is CommandResult.FAILURE
        assert image.get_bytes() == new_data  # unchanged -- undo bailed out early

        # Recovery: the project becomes available again, and the user
        # triggers redo (CommandExecutor already moved this command to
        # the redo stack despite the failed undo).
        app_state.has_project = True
        redo_res = edit_cmd.redo()
        assert redo_res is CommandResult.SUCCESS

        # The critical assertion: old_bytes must still be the TRUE
        # original, not overwritten with the already-edited new_data.
        assert edit_cmd.old_bytes == old_data

        # And a subsequent undo must actually be able to restore it.
        assert edit_cmd.undo() is CommandResult.SUCCESS
        assert image.get_bytes() == old_data
