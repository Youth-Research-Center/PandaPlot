import pytest
from unittest.mock import Mock

from pandaplot.commands.project.folder.rename_folder_command import RenameFolderCommand
from pandaplot.models.project.items.folder import Folder
from pandaplot.models.project.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.gui.controllers.ui_controller import UIController


class TestRenameFolderCommand:
    """Test suite for RenameFolderCommand."""
    
    @pytest.fixture
    def mock_app_context(self):
        """Create mock app context with all dependencies."""
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock(spec=UIController)
        
        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller
        
        # Setup event bus
        app_state.event_bus = Mock()
        app_state.event_bus.emit = Mock()
        
        return app_context, app_state, ui_controller
    
    @pytest.fixture
    def sample_project(self):
        """Create a sample project for testing."""
        project = Project("Test Project")
        project.find_item = Mock()
        return project

    @pytest.fixture
    def sample_folder(self):
        """Create a sample folder for testing."""
        folder = Mock(spec=Folder)
        folder.name = "Original Folder"
        return folder

    def test_init_default_values(self, mock_app_context):
        """Test command initialization with default values."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = RenameFolderCommand(app_context)
        
        assert command.app_context == app_context
        assert command.app_state == app_state
        assert command.ui_controller == ui_controller
        assert command.folder_id is None
        assert command.new_name is None
        assert command.old_name is None

    def test_init_with_parameters(self, mock_app_context):
        """Test command initialization with parameters."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = RenameFolderCommand(app_context, "folder-123", "New Folder Name")
        
        assert command.folder_id == "folder-123"
        assert command.new_name == "New Folder Name"
        assert command.old_name is None

    def test_execute_no_project_loaded(self, mock_app_context):
        """Test execute when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        result = command.execute()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Rename Folder", 
            "No project is currently loaded."
        )

    def test_execute_no_current_project(self, mock_app_context):
        """Test execute when current project is None."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        result = command.execute()
        
        assert result is False

    def test_execute_no_folder_id(self, mock_app_context, sample_project):
        """Test execute when folder ID is not provided."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = RenameFolderCommand(app_context, None, "New Name")
        result = command.execute()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Rename Folder", 
            "Folder ID and new name are required."
        )

    def test_execute_no_new_name(self, mock_app_context, sample_project):
        """Test execute when new name is not provided."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = RenameFolderCommand(app_context, "folder-123", None)
        result = command.execute()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Rename Folder", 
            "Folder ID and new name are required."
        )

    def test_execute_folder_not_found(self, mock_app_context, sample_project):
        """Test execute when folder is not found."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # find_item returns None
        sample_project.find_item.return_value = None
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        result = command.execute()
        
        assert result is False
        sample_project.find_item.assert_called_once_with("folder-123")
        ui_controller.show_warning_message.assert_called_once_with(
            "Rename Folder", 
            "Folder with ID 'folder-123' not found in the project."
        )

    def test_execute_item_not_folder(self, mock_app_context, sample_project):
        """Test execute when found item is not a Folder."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # find_item returns a non-Folder object
        not_a_folder = Mock()
        sample_project.find_item.return_value = not_a_folder
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        result = command.execute()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Rename Folder", 
            "Folder with ID 'folder-123' not found in the project."
        )

    def test_execute_successful(self, mock_app_context, sample_project, sample_folder):
        """Test successful execute operation."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_folder
        
        command = RenameFolderCommand(app_context, "folder-123", "Renamed Folder")
        result = command.execute()
        
        assert result is True
        assert command.old_name == "Original Folder"
        assert sample_folder.name == "Renamed Folder"
        
        # Check event emission
        app_state.event_bus.emit.assert_called_once_with('folder_renamed', {
            'project': sample_project,
            'folder_id': "folder-123",
            'old_name': "Original Folder",
            'new_name': "Renamed Folder",
            'folder': sample_folder
        })

    def test_execute_with_exception(self, mock_app_context, sample_project, sample_folder):
        """Test execute when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_folder
        
        # Make setting name raise an exception
        def setter_with_exception(self, value):
            raise Exception("Test error")
        
        type(sample_folder).name = property(lambda self: "Original", setter_with_exception)
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        result = command.execute()
        
        assert result is False
        ui_controller.show_error_message.assert_called_once()
        assert "Failed to rename folder: Test error" in ui_controller.show_error_message.call_args[0][1]

    def test_undo_successful(self, mock_app_context, sample_project, sample_folder):
        """Test successful undo operation."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_folder
        sample_folder.name = "New Name"  # Simulate it was renamed
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        command.old_name = "Original Name"  # Simulate execute was called
        
        result = command.undo()
        
        assert result is True
        assert sample_folder.name == "Original Name"
        
        # Check event emission
        app_state.event_bus.emit.assert_called_once_with('folder_renamed', {
            'project': sample_project,
            'folder_id': "folder-123",
            'old_name': "New Name",
            'new_name': "Original Name",
            'folder': sample_folder
        })

    def test_undo_no_old_name(self, mock_app_context):
        """Test undo when no old name is stored."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        # old_name is None
        result = command.undo()
        
        # Should not crash and should not perform any operations
        assert result is None

    def test_undo_no_folder_id(self, mock_app_context):
        """Test undo when no folder ID is stored."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = RenameFolderCommand(app_context, None, "New Name")
        command.old_name = "Original Name"
        
        result = command.undo()
        
        # Should not crash and should not perform any operations
        assert result is None

    def test_undo_no_project(self, mock_app_context):
        """Test undo when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        command.old_name = "Original Name"
        
        result = command.undo()
        
        # Should not crash and should not perform any operations
        assert result is None

    def test_undo_no_current_project(self, mock_app_context):
        """Test undo when current project is None."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        command.old_name = "Original Name"
        
        result = command.undo()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Undo Rename Folder", 
            "No project is currently loaded."
        )

    def test_undo_folder_not_found(self, mock_app_context, sample_project):
        """Test undo when folder is not found."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = None
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        command.old_name = "Original Name"
        
        result = command.undo()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Undo Rename Folder", 
            "Folder with ID 'folder-123' not found in the project."
        )

    def test_undo_item_not_folder(self, mock_app_context, sample_project):
        """Test undo when found item is not a Folder."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        not_a_folder = Mock()
        sample_project.find_item.return_value = not_a_folder
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        command.old_name = "Original Name"
        
        result = command.undo()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Undo Rename Folder", 
            "Folder with ID 'folder-123' not found in the project."
        )

    def test_undo_with_exception(self, mock_app_context, sample_project, sample_folder):
        """Test undo when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_folder
        
        # Make setting name raise an exception
        def setter_with_exception(self, value):
            raise Exception("Test error")
        
        type(sample_folder).name = property(lambda self: "Current", setter_with_exception)
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        command.old_name = "Original Name"
        
        result = command.undo()
        
        assert result is False
        ui_controller.show_error_message.assert_called_once()
        assert "Failed to undo rename folder: Test error" in ui_controller.show_error_message.call_args[0][1]

    def test_redo_successful(self, mock_app_context, sample_project, sample_folder):
        """Test successful redo operation."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_folder
        sample_folder.name = "Original Name"  # Simulate it was undone
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        command.old_name = "Original Name"  # Simulate execute was called
        
        result = command.redo()
        
        assert result is True
        assert sample_folder.name == "New Name"
        
        # Check event emission
        app_state.event_bus.emit.assert_called_once_with('folder_renamed', {
            'project': sample_project,
            'folder_id': "folder-123",
            'old_name': "Original Name",
            'new_name': "New Name",
            'folder': sample_folder
        })

    def test_redo_no_old_name(self, mock_app_context):
        """Test redo when no old name is stored."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        # old_name is None
        result = command.redo()
        
        assert result is False

    def test_redo_no_folder_id(self, mock_app_context):
        """Test redo when no folder ID is stored."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = RenameFolderCommand(app_context, None, "New Name")
        command.old_name = "Original Name"
        
        result = command.redo()
        
        assert result is False

    def test_redo_no_new_name(self, mock_app_context):
        """Test redo when no new name is stored."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = RenameFolderCommand(app_context, "folder-123", None)
        command.old_name = "Original Name"
        
        result = command.redo()
        
        assert result is False

    def test_redo_no_project(self, mock_app_context):
        """Test redo when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        command.old_name = "Original Name"
        
        result = command.redo()
        
        assert result is False

    def test_redo_no_current_project(self, mock_app_context):
        """Test redo when current project is None."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        command.old_name = "Original Name"
        
        result = command.redo()
        
        assert result is False

    def test_redo_folder_not_found(self, mock_app_context, sample_project):
        """Test redo when folder is not found."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = None
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        command.old_name = "Original Name"
        
        result = command.redo()
        
        assert result is False

    def test_redo_item_not_folder(self, mock_app_context, sample_project):
        """Test redo when found item is not a Folder."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        not_a_folder = Mock()
        sample_project.find_item.return_value = not_a_folder
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        command.old_name = "Original Name"
        
        result = command.redo()
        
        assert result is False

    def test_redo_with_exception(self, mock_app_context, sample_project, sample_folder):
        """Test redo when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_folder
        
        # Make setting name raise an exception
        def setter_with_exception(self, value):
            raise Exception("Test error")
        
        type(sample_folder).name = property(lambda self: "Current", setter_with_exception)
        
        command = RenameFolderCommand(app_context, "folder-123", "New Name")
        command.old_name = "Original Name"
        
        result = command.redo()
        
        assert result is False
        ui_controller.show_error_message.assert_called_once()
        assert "Failed to redo rename folder: Test error" in ui_controller.show_error_message.call_args[0][1]

    def test_name_storage_during_execute(self, mock_app_context, sample_project, sample_folder):
        """Test that old name is properly stored during execute."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_folder.name = "Initial Name"
        sample_project.find_item.return_value = sample_folder
        
        command = RenameFolderCommand(app_context, "folder-123", "Modified Name")
        
        # Before execute, old_name should be None
        assert command.old_name is None
        
        result = command.execute()
        
        # After execute, old_name should be stored
        assert result is True
        assert command.old_name == "Initial Name"

    def test_event_data_structure(self, mock_app_context, sample_project, sample_folder):
        """Test that emitted events have correct data structure."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_folder.name = "Old Name"
        sample_project.find_item.return_value = sample_folder
        
        command = RenameFolderCommand(app_context, "test-folder", "New Name")
        command.execute()
        
        # Check the event was emitted with correct structure
        app_state.event_bus.emit.assert_called_once()
        event_name, event_data = app_state.event_bus.emit.call_args[0]
        
        assert event_name == 'folder_renamed'
        assert 'project' in event_data
        assert 'folder_id' in event_data
        assert 'old_name' in event_data
        assert 'new_name' in event_data
        assert 'folder' in event_data
        
        assert event_data['project'] == sample_project
        assert event_data['folder_id'] == "test-folder"
        assert event_data['old_name'] == "Old Name"
        assert event_data['new_name'] == "New Name"
        assert event_data['folder'] == sample_folder

    def test_command_state_isolation(self, mock_app_context, sample_project):
        """Test that multiple command instances don't interfere with each other."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        folder1 = Mock(spec=Folder)
        folder1.name = "Folder 1"
        
        folder2 = Mock(spec=Folder)
        folder2.name = "Folder 2"
        
        def find_item_side_effect(folder_id):
            if folder_id == "folder-1":
                return folder1
            elif folder_id == "folder-2":
                return folder2
            return None
        
        sample_project.find_item.side_effect = find_item_side_effect
        
        command1 = RenameFolderCommand(app_context, "folder-1", "Renamed 1")
        command2 = RenameFolderCommand(app_context, "folder-2", "Renamed 2")
        
        command1.execute()
        command2.execute()
        
        assert command1.old_name == "Folder 1"
        assert command2.old_name == "Folder 2"
        assert command1.folder_id == "folder-1"
        assert command2.folder_id == "folder-2"
        assert command1.new_name == "Renamed 1"
        assert command2.new_name == "Renamed 2"
        assert folder1.name == "Renamed 1"
        assert folder2.name == "Renamed 2"
