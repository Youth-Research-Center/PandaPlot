# tests/commands/project/image/test_create_image_gallery_command.py
#
# Mirrors tests/commands/project/folder/test_create_folder_command.py's
# fixture setup (see conftest.py in this directory for the AppContext/
# app_state/ui_controller mock construction this test relies on).

import logging

from pandaplot.commands.project.image.create_image_gallery_command import (
    CreateImageGalleryCommand,
)
from pandaplot.models.project.items import ImageGallery


class TestCreateImageGalleryCommand:
    def test_execute_creates_gallery_with_given_name(self, app_context_with_project):
        command = CreateImageGalleryCommand(app_context_with_project, gallery_name="My Gallery")

        assert command.execute() is True
        project = app_context_with_project.get_app_state().current_project
        gallery = project.find_item(command.created_gallery_id)
        assert isinstance(gallery, ImageGallery)
        assert gallery.name == "My Gallery"

    def test_execute_generates_default_name_when_none_given(self, app_context_with_project):
        command = CreateImageGalleryCommand(app_context_with_project)

        assert command.execute() is True
        project = app_context_with_project.get_app_state().current_project
        gallery = project.find_item(command.created_gallery_id)
        assert gallery.name.startswith("New Image Gallery")

    def test_undo_removes_created_gallery(self, app_context_with_project):
        command = CreateImageGalleryCommand(app_context_with_project, gallery_name="Trip")
        command.execute()
        gallery_id = command.created_gallery_id

        command.undo()

        project = app_context_with_project.get_app_state().current_project
        assert project.find_item(gallery_id) is None

    def test_redo_restores_created_gallery(self, app_context_with_project):
        command = CreateImageGalleryCommand(app_context_with_project, gallery_name="Trip")
        command.execute()
        command.undo()

        assert command.redo() is True
        project = app_context_with_project.get_app_state().current_project
        assert project.find_item(command.created_gallery_id) is not None


class TestCreateImageGalleryCommandCleanup:
    def test_cleanup_releases_cached_project_reference(self, app_context_with_project):
        command = CreateImageGalleryCommand(app_context_with_project, gallery_name="Trip")
        command.execute()
        assert command.project is not None

        command.cleanup()

        assert command.project is None
        assert command.created_gallery is not None
        assert command.created_gallery_id is not None


class TestCreateImageGalleryCommandLogging:
    def test_execute_logs_a_warning_when_current_project_is_none(self, app_context_with_project, caplog):
        app_context_with_project.get_app_state().current_project = None

        command = CreateImageGalleryCommand(app_context_with_project, gallery_name="Trip")

        with caplog.at_level(logging.WARNING):
            assert command.execute() is False
        assert "CreateImageGalleryCommand.execute" in caplog.text

    def test_execute_logs_a_warning_when_gallery_name_is_empty(self, app_context_with_project, caplog):
        command = CreateImageGalleryCommand(app_context_with_project, gallery_name="   ")

        with caplog.at_level(logging.WARNING):
            assert command.execute() is False
        assert "CreateImageGalleryCommand.execute" in caplog.text

    def test_redo_logs_a_warning_when_current_project_is_none(self, app_context_with_project, caplog):
        command = CreateImageGalleryCommand(app_context_with_project, gallery_name="Trip")
        command.execute()
        command.undo()

        app_context_with_project.get_app_state().current_project = None

        with caplog.at_level(logging.WARNING):
            assert command.redo() is False
        assert "CreateImageGalleryCommand.redo" in caplog.text
