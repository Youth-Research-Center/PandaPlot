# tests/commands/project/image/test_create_image_gallery_command.py
#
# Mirrors tests/commands/project/folder/test_create_folder_command.py's
# fixture setup (see conftest.py in this directory for the AppContext/
# app_state/ui_controller mock construction this test relies on).

import logging
from unittest.mock import Mock

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.image.create_image_gallery_command import (
    CreateImageGalleryCommand,
)
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project import Project
from pandaplot.models.project.items import ImageGallery
from pandaplot.models.state import AppContext, AppState


class TestCreateImageGalleryCommand:
    def test_execute_creates_gallery_with_given_name(self, app_context_with_project):
        command = CreateImageGalleryCommand(app_context_with_project, gallery_name="My Gallery")

        assert command.execute() is CommandResult.SUCCESS
        project = app_context_with_project.get_app_state().current_project
        gallery = project.find_item(command.created_gallery_id)
        assert isinstance(gallery, ImageGallery)
        assert gallery.name == "My Gallery"

    def test_execute_generates_default_name_when_none_given(self, app_context_with_project):
        command = CreateImageGalleryCommand(app_context_with_project)

        assert command.execute() is CommandResult.SUCCESS
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

        assert command.redo() is CommandResult.SUCCESS
        project = app_context_with_project.get_app_state().current_project
        assert project.find_item(command.created_gallery_id) is not None


class TestCreateImageGalleryCommandNoProject:
    """Matches Create Chart/Import Data/New Note: no project yet must offer
    to create one on the spot instead of leaving the user at a dead end."""

    @pytest.fixture
    def mock_app_context(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock(spec=UIController)

        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller
        app_state.has_project = False
        app_state.current_project = None
        app_state.event_bus = Mock()

        return app_context, app_state, ui_controller

    def test_execute_returns_false_when_user_declines_project_offer(self, mock_app_context):
        app_context, app_state, ui_controller = mock_app_context
        ui_controller.show_action_or_cancel.return_value = False

        command = CreateImageGalleryCommand(app_context, gallery_name="Trip")
        result = command.execute()

        assert result is CommandResult.FAILURE
        ui_controller.show_action_or_cancel.assert_called_once()

    def test_execute_continues_after_the_user_creates_a_project(self, mock_app_context):
        app_context, app_state, ui_controller = mock_app_context
        ui_controller.show_action_or_cancel.return_value = True

        project = Project(name="Test Project")

        def _execute_command(_command):
            app_state.has_project = True
            app_state.current_project = project

        app_context.get_command_executor.return_value.execute_command.side_effect = _execute_command

        command = CreateImageGalleryCommand(app_context, gallery_name="Trip")
        result = command.execute()

        assert result is CommandResult.SUCCESS
        assert project.find_item(command.created_gallery_id) is command.created_gallery


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
            assert command.execute() is CommandResult.FAILURE
        assert "CreateImageGalleryCommand.execute" in caplog.text

    def test_execute_logs_a_warning_when_gallery_name_is_empty(self, app_context_with_project, caplog):
        command = CreateImageGalleryCommand(app_context_with_project, gallery_name="   ")

        with caplog.at_level(logging.WARNING):
            assert command.execute() is CommandResult.FAILURE
        assert "CreateImageGalleryCommand.execute" in caplog.text

    def test_redo_logs_a_warning_when_current_project_is_none(self, app_context_with_project, caplog):
        command = CreateImageGalleryCommand(app_context_with_project, gallery_name="Trip")
        command.execute()
        command.undo()

        app_context_with_project.get_app_state().current_project = None

        with caplog.at_level(logging.WARNING):
            assert command.redo() is CommandResult.FAILURE
        assert "CreateImageGalleryCommand.redo" in caplog.text
