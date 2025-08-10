"""
Unit tests for CreateFolderCommand.
"""

import pytest
from unittest.mock import Mock, patch

from pandaplot.commands.project.folder.create_folder_command import CreateFolderCommand
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.project import Project
from pandaplot.models.project.items.folder import Folder


class TestCreateFolderCommand:
    """Test cases for CreateFolderCommand."""

    @pytest.fixture
    def mock_app_context(self):
        """Create a mock AppContext with required dependencies."""
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock(spec=UIController)
        
        # Add event_bus mock to app_state
        event_bus = Mock()
        app_state.event_bus = event_bus
        
        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller
        
        return app_context, app_state, ui_controller

    @pytest.fixture
    def sample_project(self):
        """Create a sample project for testing."""
        project = Project(name="Test Project")
        return project

    def test_init_default_values(self, mock_app_context):
        """Test command initialization with default values."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = CreateFolderCommand(app_context)
        
        assert command.app_context == app_context
        assert command.app_state == app_state
        assert command.ui_controller == ui_controller
        assert command.folder_name is None
        assert command.parent_id is None
        assert command.created_folder_id is None
        assert command.created_folder is None
        assert command.project is None

    def test_init_with_parameters(self, mock_app_context):
        """Test command initialization with parameters."""
        app_context, app_state, ui_controller = mock_app_context
        folder_name = "Test Folder"
        parent_id = "test-parent-123"
        
        command = CreateFolderCommand(app_context, folder_name, parent_id)
        
        assert command.folder_name == folder_name
        assert command.parent_id == parent_id

    def test_execute_no_project_loaded(self, mock_app_context):
        """Test execute when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = CreateFolderCommand(app_context)
        result = command.execute()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Create Folder", 
            "Please open or create a project first."
        )

    def test_execute_no_current_project(self, mock_app_context):
        """Test execute when has_project is True but current_project is None."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None
        
        command = CreateFolderCommand(app_context)
        result = command.execute()
        
        assert result is False

    def test_execute_with_default_name_generation(self, mock_app_context, sample_project):
        """Test execute with default name generation when no existing folders."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = CreateFolderCommand(app_context)
        result = command.execute()
        
        assert result is True
        assert command.created_folder_id is not None
        assert command.created_folder is not None
        assert command.created_folder.name == "New Folder 1"
        
        # Check that folder was added to project
        assert command.created_folder_id in sample_project.items_index
        folder = sample_project.find_item(command.created_folder_id)
        assert isinstance(folder, Folder)
        assert folder.name == "New Folder 1"

    def test_execute_with_existing_folders_name_generation(self, mock_app_context, sample_project):
        """Test execute with default name generation when folders already exist."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # Add existing folders to project
        existing_folder1 = Folder(name="Existing Folder 1")
        existing_folder2 = Folder(name="Existing Folder 2")
        sample_project.add_item(existing_folder1)
        sample_project.add_item(existing_folder2)
        
        command = CreateFolderCommand(app_context)
        result = command.execute()
        
        assert result is True
        assert command.created_folder.name == "New Folder 3"  # Should be 3rd folder

    def test_execute_with_specified_name(self, mock_app_context, sample_project):
        """Test execute with a specified folder name."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        folder_name = "Custom Folder Name"
        command = CreateFolderCommand(app_context, folder_name)
        result = command.execute()
        
        assert result is True
        assert command.created_folder.name == folder_name
        
        # Check event emission
        event_bus = app_state.event_bus
        event_bus.emit.assert_called_once_with('folder_created', {
            'project': sample_project,
            'folder_id': command.created_folder_id,
            'folder_name': folder_name,
            'parent_id': None,
            'folder': command.created_folder
        })

    def test_execute_with_parent_id(self, mock_app_context, sample_project):
        """Test execute with a specific parent_id."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # Create a parent folder
        parent_folder = Folder(name="Parent Folder")
        sample_project.add_item(parent_folder)
        
        folder_name = "Child Folder"
        command = CreateFolderCommand(app_context, folder_name, parent_folder.id)
        result = command.execute()
        
        assert result is True
        assert command.parent_id == parent_folder.id
        
        # Check that the child folder has the correct parent
        child_folder = sample_project.find_item(command.created_folder_id)
        assert child_folder.parent_id == parent_folder.id

    def test_execute_with_empty_name_after_strip(self, mock_app_context, sample_project):
        """Test execute with name that becomes empty after stripping."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = CreateFolderCommand(app_context, "   ")  # Only whitespace
        result = command.execute()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Create Folder", 
            "Folder name cannot be empty."
        )

    def test_execute_with_whitespace_name(self, mock_app_context, sample_project):
        """Test execute with name that has leading/trailing whitespace."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        folder_name = "  Valid Folder Name  "
        command = CreateFolderCommand(app_context, folder_name)
        result = command.execute()
        
        assert result is True
        assert command.created_folder.name == "Valid Folder Name"  # Stripped

    def test_execute_with_exception(self, mock_app_context, sample_project):
        """Test execute when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # Mock project.add_item to raise an exception
        sample_project.add_item = Mock(side_effect=Exception("Test exception"))
        
        command = CreateFolderCommand(app_context, "Test Folder")
        result = command.execute()
        
        assert result is False
        ui_controller.show_error_message.assert_called_once()
        error_call = ui_controller.show_error_message.call_args
        assert error_call[0][0] == "Create Folder Error"
        assert "Failed to create folder: Test exception" in error_call[0][1]

    def test_undo_successful(self, mock_app_context, sample_project):
        """Test successful undo operation."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = CreateFolderCommand(app_context, "Test Folder")
        
        # First execute the command
        result = command.execute()
        assert result is True
        
        # Verify folder was added
        assert command.created_folder_id in sample_project.items_index
        
        # Now undo
        command.undo()
        
        # Verify folder was removed
        assert command.created_folder_id not in sample_project.items_index
        assert sample_project.find_item(command.created_folder_id) is None
        
        # Check event emission for undo
        event_bus = app_state.event_bus
        assert event_bus.emit.call_count == 2  # One for create, one for delete
        delete_event_call = event_bus.emit.call_args_list[1]
        assert delete_event_call[0][0] == 'folder_deleted'
        assert delete_event_call[0][1]['folder_id'] == command.created_folder_id

    def test_undo_no_folder_id(self, mock_app_context, sample_project):
        """Test undo when no folder_id is set."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = CreateFolderCommand(app_context)
        # Don't execute, just try to undo
        command.undo()
        
        # Should complete without error (no folder to remove)

    def test_undo_no_project(self, mock_app_context):
        """Test undo when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = CreateFolderCommand(app_context)
        command.created_folder_id = "test-id"  # Set manually
        command.undo()
        
        # Should complete without error

    def test_undo_with_exception(self, mock_app_context, sample_project):
        """Test undo when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = CreateFolderCommand(app_context, "Test Folder")
        
        # Execute first
        result = command.execute()
        assert result is True
        
        # Mock remove_item to raise an exception
        sample_project.remove_item = Mock(side_effect=Exception("Undo test exception"))
        
        command.undo()
        
        ui_controller.show_error_message.assert_called()
        error_call = ui_controller.show_error_message.call_args
        assert error_call[0][0] == "Undo Error"
        assert "Failed to undo create folder: Undo test exception" in error_call[0][1]

    def test_redo_successful(self, mock_app_context, sample_project):
        """Test successful redo operation."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = CreateFolderCommand(app_context, "Test Folder")
        
        # Execute, undo, then redo
        result = command.execute()
        assert result is True
        
        original_folder_id = command.created_folder_id
        original_folder_name = command.created_folder.name
        
        command.undo()
        assert sample_project.find_item(original_folder_id) is None
        
        result = command.redo()
        assert result is True
        
        # Check that the same folder object was re-added (not a new one)
        assert command.created_folder_id == original_folder_id
        assert command.created_folder.name == original_folder_name
        assert sample_project.find_item(original_folder_id) is not None

    def test_redo_no_folder(self, mock_app_context, sample_project):
        """Test redo when no folder is available."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = CreateFolderCommand(app_context)
        # Don't execute first, just try to redo
        result = command.redo()
        
        assert result is False  # redo returns False when conditions not met

    def test_redo_no_project(self, mock_app_context):
        """Test redo when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = CreateFolderCommand(app_context, "Test Folder")
        command.created_folder_id = "test-id"
        command.created_folder = Folder(name="Test Folder")
        
        result = command.redo()
        
        assert result is False

    def test_redo_with_exception(self, mock_app_context, sample_project):
        """Test redo when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = CreateFolderCommand(app_context, "Test Folder")
        
        # Execute first
        result = command.execute()
        assert result is True
        
        # Mock add_item to raise an exception on redo
        sample_project.add_item = Mock(side_effect=Exception("Redo test exception"))
        
        result = command.redo()
        
        assert result is False
        ui_controller.show_error_message.assert_called()
        error_call = ui_controller.show_error_message.call_args
        assert error_call[0][0] == "Redo Error"
        assert "Failed to redo create folder: Redo test exception" in error_call[0][1]

    def test_folder_properties(self, mock_app_context, sample_project):
        """Test that the created Folder object has correct properties."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        folder_name = "Test Properties Folder"
        command = CreateFolderCommand(app_context, folder_name)
        result = command.execute()
        
        assert result is True
        
        # Get the created folder
        folder = sample_project.find_item(command.created_folder_id)
        assert isinstance(folder, Folder)
        
        # Check folder properties
        assert folder.id == command.created_folder_id
        assert folder.name == folder_name
        assert folder.parent_id == sample_project.root.id  # Should be added to root

    @patch('uuid.uuid4')
    def test_folder_id_generation(self, mock_uuid, mock_app_context, sample_project):
        """Test that folder ID is generated correctly."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # Mock UUID generation
        test_uuid = "test-uuid-12345"
        mock_uuid.return_value = Mock()
        mock_uuid.return_value.__str__ = Mock(return_value=test_uuid)
        
        command = CreateFolderCommand(app_context, "Test Folder")
        result = command.execute()
        
        assert result is True
        assert command.created_folder_id == test_uuid
        
        # Verify the folder exists with the expected ID
        folder = sample_project.find_item(test_uuid)
        assert folder is not None
        assert folder.id == test_uuid

    def test_command_state_isolation(self, mock_app_context):
        """Test that multiple command instances don't interfere with each other."""
        app_context, app_state, ui_controller = mock_app_context
        
        command1 = CreateFolderCommand(app_context, "Folder 1", "parent1")
        command2 = CreateFolderCommand(app_context, "Folder 2", "parent2")
        
        assert command1.folder_name == "Folder 1"
        assert command2.folder_name == "Folder 2"
        assert command1.parent_id == "parent1"
        assert command2.parent_id == "parent2"
        assert command1.created_folder_id is None
        assert command2.created_folder_id is None
        
        # Modifying one shouldn't affect the other
        command1.created_folder_id = "test-id-1"
        assert command2.created_folder_id is None

    def test_event_data_structure(self, mock_app_context, sample_project):
        """Test that events contain all expected data."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        folder_name = "Event Test Folder"
        parent_id = "test-parent"
        command = CreateFolderCommand(app_context, folder_name, parent_id)
        
        result = command.execute()
        assert result is True
        
        # Check the event data structure
        event_bus = app_state.event_bus
        event_call = event_bus.emit.call_args
        
        assert event_call[0][0] == 'folder_created'
        event_data = event_call[0][1]
        
        expected_keys = {'project', 'folder_id', 'folder_name', 'parent_id', 'folder'}
        assert set(event_data.keys()) == expected_keys
        
        assert event_data['project'] == sample_project
        assert event_data['folder_id'] == command.created_folder_id
        assert event_data['folder_name'] == folder_name
        assert event_data['parent_id'] == parent_id
        assert event_data['folder'] == command.created_folder
