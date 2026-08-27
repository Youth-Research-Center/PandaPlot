"""
Tests for the logging behavior added to MoveItemCommand.execute(). This file
intentionally does not attempt full command coverage -- only the newly-added
warning-log paths, following the mock/fixture conventions used in
tests/commands/project/item/test_delete_item_command.py.
"""

import logging
from unittest.mock import Mock

import pytest

from pandaplot.commands.project.item.move_item_command import MoveItemCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.state import AppContext, AppState


class TestMoveItemCommandLogging:
    """Test suite for MoveItemCommand's warning-log paths."""

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
        project.remove_item = Mock()
        project.add_item = Mock()
        return project

    def test_execute_logs_a_warning_when_no_project_loaded(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False

        command = MoveItemCommand(app_context, item_id="item-123", target_folder_id="root")

        with caplog.at_level(logging.WARNING):
            command.execute()

        assert "MoveItemCommand.execute" in caplog.text

    def test_execute_logs_a_warning_when_current_project_is_none(self, mock_app_context, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None

        command = MoveItemCommand(app_context, item_id="item-123", target_folder_id="root")

        with caplog.at_level(logging.WARNING):
            command.execute()

        assert "MoveItemCommand.execute" in caplog.text

    def test_execute_logs_a_warning_when_no_item_id_specified(self, mock_app_context, sample_project, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        command = MoveItemCommand(app_context, item_id=None, target_folder_id="root")

        with caplog.at_level(logging.WARNING):
            command.execute()

        assert "MoveItemCommand.execute" in caplog.text

    def test_execute_logs_a_warning_when_item_not_found(self, mock_app_context, sample_project, caplog):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        sample_project.find_item.return_value = None

        command = MoveItemCommand(app_context, item_id="missing-item", target_folder_id="root")

        with caplog.at_level(logging.WARNING):
            command.execute()

        assert "missing-item" in caplog.text

    def test_cleanup_does_not_raise(self, mock_app_context):
        app_context, app_state, ui_controller = mock_app_context

        command = MoveItemCommand(app_context, item_id="item-123", target_folder_id="root")
        command.move_performed = True

        command.cleanup()
