"""
Tests for the logging behavior added to RenameItemCommand.execute()/undo().
This file intentionally does not attempt full command coverage -- only the
newly-added warning-log paths, following the mock/fixture conventions used in
tests/commands/project/item/test_delete_item_command.py.
"""

import logging
from unittest.mock import Mock

import pytest

from pandaplot.commands.project.item.rename_item_command import RenameItemCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.state import AppContext, AppState


class TestRenameItemCommandLogging:
    """Test suite for RenameItemCommand's warning-log paths."""

    @pytest.fixture
    def mock_app_context(self):
        """Create mock app context with all dependencies."""
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock(spec=UIController)

        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller

        app_state.event_bus = Mock()
        app_state.event_bus.emit = Mock()

        return app_context, app_state, ui_controller

    @pytest.fixture
    def sample_project(self):
        """Create a mock project for testing."""
        project = Mock()
        project.find_item = Mock()
        return project

    def test_execute_logs_a_warning_when_no_project_loaded(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False

        command = RenameItemCommand(app_context, item_id="item-123", new_name="New Name")

        with caplog.at_level(logging.WARNING):
            assert command.execute() is False
        assert "RenameItemCommand.execute" in caplog.text

    def test_execute_logs_a_warning_when_current_project_is_none(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None

        command = RenameItemCommand(app_context, item_id="item-123", new_name="New Name")

        with caplog.at_level(logging.WARNING):
            assert command.execute() is False
        assert "RenameItemCommand.execute" in caplog.text

    def test_execute_logs_a_warning_when_item_not_found(self, mock_app_context, sample_project, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        sample_project.find_item.return_value = None

        command = RenameItemCommand(app_context, item_id="missing-item", new_name="New Name")

        with caplog.at_level(logging.WARNING):
            assert command.execute() is False
        assert "missing-item" in caplog.text

    def test_cleanup_releases_old_name(self, mock_app_context):
        app_context, app_state, ui_controller = mock_app_context

        command = RenameItemCommand(app_context, item_id="item-123", new_name="New Name")
        command.old_name = "Old Name"

        command.cleanup()

        assert command.old_name is None

    def test_undo_logs_a_warning_when_current_project_is_none(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None

        command = RenameItemCommand(app_context, item_id="item-123", new_name="New Name")
        command.old_name = "Old Name"

        with caplog.at_level(logging.WARNING):
            command.undo()
        assert "RenameItemCommand.undo" in caplog.text

    def test_undo_logs_a_warning_when_item_not_found(self, mock_app_context, sample_project, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        sample_project.find_item.return_value = None

        command = RenameItemCommand(app_context, item_id="missing-item", new_name="New Name")
        command.old_name = "Old Name"

        with caplog.at_level(logging.WARNING):
            command.undo()
        assert "missing-item" in caplog.text
