import pytest
from unittest.mock import Mock, patch

from pandaplot.commands.project.note.create_note_command import CreateNoteCommand
from pandaplot.models.project.items.note import Note
from pandaplot.models.project.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.gui.controllers.ui_controller import UIController


class TestCreateNoteCommand:
    """Test suite for CreateNoteCommand."""
    
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
        project.add_item = Mock()
        project.remove_item = Mock()
        return project

    def test_init_default_values(self, mock_app_context):
        """Test command initialization with default values."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = CreateNoteCommand(app_context)
        
        assert command.app_context == app_context
        assert command.app_state == app_state
        assert command.ui_controller == ui_controller
        assert command.note_name is None
        assert command.content == ""
        assert command.folder_id is None
        assert command.created_note_id is None
        assert command.created_note is None
        assert command.project is None

    def test_init_with_parameters(self, mock_app_context):
        """Test command initialization with parameters."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = CreateNoteCommand(app_context, "Test Note", "Test content", "folder-123")
        
        assert command.note_name == "Test Note"
        assert command.content == "Test content"
        assert command.folder_id == "folder-123"

    def test_execute_no_project_loaded(self, mock_app_context):
        """Test execute when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = CreateNoteCommand(app_context, "Test Note")
        result = command.execute()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "New Note", 
            "Please open or create a project first."
        )

    def test_execute_no_current_project(self, mock_app_context):
        """Test execute when current project is None."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None
        
        command = CreateNoteCommand(app_context, "Test Note")
        result = command.execute()
        
        assert result is False

    def test_execute_with_default_name(self, mock_app_context, sample_project):
        """Test execute with default note name."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = CreateNoteCommand(app_context)  # No name provided
        
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value = Mock()
            mock_uuid.return_value.__str__ = Mock(return_value="test-uuid")
            
            result = command.execute()
        
        assert result is True
        assert command.created_note_id == "test-uuid"
        assert command.created_note.name == "New Note"
        assert command.created_note.content == ""
        sample_project.add_item.assert_called_once()
        app_state.event_bus.emit.assert_called_once_with('note_created', {
            'project': sample_project,
            'note_id': "test-uuid",
            'note_name': "New Note",
            'folder_id': None,
            'note': command.created_note
        })

    def test_execute_with_specified_name_and_content(self, mock_app_context, sample_project):
        """Test execute with specified note name and content."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = CreateNoteCommand(app_context, "Custom Note", "Custom content", "folder-123")
        
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value = Mock()
            mock_uuid.return_value.__str__ = Mock(return_value="test-uuid")
            
            result = command.execute()
        
        assert result is True
        assert command.created_note.name == "Custom Note"
        assert command.created_note.content == "Custom content"
        sample_project.add_item.assert_called_once_with(command.created_note, parent_id="folder-123")

    def test_execute_with_folder_id(self, mock_app_context, sample_project):
        """Test execute with folder ID."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = CreateNoteCommand(app_context, "Test Note", "", "parent-folder")
        
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value = Mock()
            mock_uuid.return_value.__str__ = Mock(return_value="test-uuid")
            
            result = command.execute()
        
        assert result is True
        sample_project.add_item.assert_called_once_with(command.created_note, parent_id="parent-folder")
        
        # Check event data
        call_args = app_state.event_bus.emit.call_args[0]
        event_data = call_args[1]
        assert event_data['folder_id'] == "parent-folder"

    def test_execute_with_exception(self, mock_app_context, sample_project):
        """Test execute when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # Make add_item raise an exception
        sample_project.add_item.side_effect = Exception("Test error")
        
        command = CreateNoteCommand(app_context, "Test Note")
        result = command.execute()
        
        assert result is False
        ui_controller.show_error_message.assert_called_once()
        assert "Failed to create note: Test error" in ui_controller.show_error_message.call_args[0][1]

    def test_undo_successful(self, mock_app_context, sample_project):
        """Test successful undo operation."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # Create a mock note
        mock_note = Mock(spec=Note)
        sample_project.find_item.return_value = mock_note
        
        command = CreateNoteCommand(app_context, "Test Note")
        command.created_note_id = "test-id"
        command.created_note = mock_note
        
        command.undo()
        
        sample_project.find_item.assert_called_once_with("test-id")
        sample_project.remove_item.assert_called_once_with(mock_note)
        app_state.event_bus.emit.assert_called_once_with('note_deleted', {
            'project': sample_project,
            'note_id': "test-id",
            'note': mock_note
        })

    def test_undo_no_note_id(self, mock_app_context):
        """Test undo when no note ID is set."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = CreateNoteCommand(app_context)
        command.undo()  # Should not crash
        
        # No assertions needed - just verify it doesn't crash

    def test_undo_no_project(self, mock_app_context):
        """Test undo when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = CreateNoteCommand(app_context)
        command.created_note_id = "test-id"
        command.undo()  # Should not crash

    def test_undo_note_not_found(self, mock_app_context, sample_project):
        """Test undo when note is not found in project."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # find_item returns None
        sample_project.find_item.return_value = None
        
        command = CreateNoteCommand(app_context)
        command.created_note_id = "test-id"
        command.created_note = Mock(spec=Note)
        
        command.undo()
        
        sample_project.find_item.assert_called_once_with("test-id")
        sample_project.remove_item.assert_not_called()  # Should not try to remove None

    def test_undo_with_exception(self, mock_app_context, sample_project):
        """Test undo when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # Make find_item raise an exception
        sample_project.find_item.side_effect = Exception("Test error")
        
        command = CreateNoteCommand(app_context)
        command.created_note_id = "test-id"
        
        command.undo()
        
        ui_controller.show_error_message.assert_called_once()
        assert "Failed to undo create note: Test error" in ui_controller.show_error_message.call_args[0][1]

    def test_redo_successful(self, mock_app_context, sample_project):
        """Test successful redo operation."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # Create a mock note
        mock_note = Mock(spec=Note)
        mock_note.name = "Test Note"
        
        command = CreateNoteCommand(app_context, "Test Note")
        command.created_note_id = "test-id"
        command.created_note = mock_note
        command.folder_id = "parent-folder"
        
        result = command.redo()
        
        assert result is True
        sample_project.add_item.assert_called_once_with(mock_note, parent_id="parent-folder")
        app_state.event_bus.emit.assert_called_once_with('note_created', {
            'project': sample_project,
            'note_id': "test-id",
            'note_name': "Test Note",
            'folder_id': "parent-folder",
            'note': mock_note
        })

    def test_redo_no_note(self, mock_app_context, sample_project):
        """Test redo when no note is available."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = CreateNoteCommand(app_context)
        # Don't execute first, just try to redo
        result = command.redo()
        
        assert result is False  # redo returns False when conditions not met

    def test_redo_no_project(self, mock_app_context):
        """Test redo when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        command = CreateNoteCommand(app_context, "Test Note")
        command.created_note_id = "test-id"
        command.created_note = Mock(spec=Note)
        result = command.redo()
        assert result is False

    def test_redo_with_exception(self, mock_app_context, sample_project):
        """Test redo when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # Make add_item raise an exception
        sample_project.add_item.side_effect = Exception("Test error")
        
        mock_note = Mock(spec=Note)
        mock_note.name = "Test Note"
        
        command = CreateNoteCommand(app_context)
        command.created_note_id = "test-id"
        command.created_note = mock_note
        
        result = command.redo()
        
        assert result is False
        ui_controller.show_error_message.assert_called_once()
        assert "Failed to redo create note: Test error" in ui_controller.show_error_message.call_args[0][1]

    def test_note_properties(self, mock_app_context, sample_project):
        """Test that created note has correct properties."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = CreateNoteCommand(app_context, "My Note", "My content")
        
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value = Mock()
            mock_uuid.return_value.__str__ = Mock(return_value="unique-id")
            
            command.execute()
        
        assert command.created_note.id == "unique-id"
        assert command.created_note.name == "My Note"
        assert command.created_note.content == "My content"

    def test_note_id_generation(self, mock_app_context, sample_project):
        """Test that note ID is properly generated."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = CreateNoteCommand(app_context, "Test Note")
        
        with patch('uuid.uuid4') as mock_uuid:
            expected_uuid = Mock()
            expected_uuid.__str__ = Mock(return_value="generated-uuid-123")
            mock_uuid.return_value = expected_uuid
            
            command.execute()
        
        assert command.created_note_id == "generated-uuid-123"
        mock_uuid.assert_called_once()

    def test_command_state_isolation(self, mock_app_context, sample_project):
        """Test that multiple command instances don't interfere with each other."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command1 = CreateNoteCommand(app_context, "Note 1")
        command2 = CreateNoteCommand(app_context, "Note 2")
        
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.side_effect = [
                Mock(__str__=Mock(return_value="id-1")),
                Mock(__str__=Mock(return_value="id-2"))
            ]
            
            command1.execute()
            command2.execute()
        
        assert command1.created_note_id == "id-1"
        assert command2.created_note_id == "id-2"
        assert command1.created_note.name == "Note 1"
        assert command2.created_note.name == "Note 2"
        assert command1.created_note is not command2.created_note

    def test_event_data_structure(self, mock_app_context, sample_project):
        """Test that emitted events have correct data structure."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = CreateNoteCommand(app_context, "Event Note", "Event content", "parent-123")
        
        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value = Mock()
            mock_uuid.return_value.__str__ = Mock(return_value="event-id")
            
            command.execute()
        
        # Check the event was emitted with correct structure
        app_state.event_bus.emit.assert_called_once()
        event_name, event_data = app_state.event_bus.emit.call_args[0]
        
        assert event_name == 'note_created'
        assert 'project' in event_data
        assert 'note_id' in event_data
        assert 'note_name' in event_data
        assert 'folder_id' in event_data
        assert 'note' in event_data
        
        assert event_data['project'] == sample_project
        assert event_data['note_id'] == "event-id"
        assert event_data['note_name'] == "Event Note"
        assert event_data['folder_id'] == "parent-123"
        assert event_data['note'] == command.created_note
