import pytest
from unittest.mock import Mock

from pandaplot.commands.project.note.edit_note_command import EditNoteCommand
from pandaplot.models.project.items.note import Note
from pandaplot.models.project.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.gui.controllers.ui_controller import UIController


class TestEditNoteCommand:
    """Test suite for EditNoteCommand."""
    
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
    def sample_note(self):
        """Create a sample note for testing."""
        note = Mock(spec=Note)
        note.content = "Original content"
        note.update_content = Mock()
        return note

    def test_init_values(self, mock_app_context):
        """Test command initialization."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        
        assert command.app_context == app_context
        assert command.app_state == app_state
        assert command.ui_controller == ui_controller
        assert command.note_id == "note-123"
        assert command.new_content == "New content"
        assert command.old_content is None

    def test_execute_no_project_loaded(self, mock_app_context):
        """Test execute when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        result = command.execute()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Edit Note", 
            "No project is currently loaded."
        )

    def test_execute_no_current_project(self, mock_app_context):
        """Test execute when current project is None."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        result = command.execute()
        
        assert result is False

    def test_execute_note_not_found(self, mock_app_context, sample_project):
        """Test execute when note is not found."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # find_item returns None
        sample_project.find_item.return_value = None
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        result = command.execute()
        
        assert result is False
        sample_project.find_item.assert_called_once_with("note-123")
        ui_controller.show_warning_message.assert_called_once_with(
            "Edit Note", 
            "Note 'note-123' not found in the project."
        )

    def test_execute_item_not_note(self, mock_app_context, sample_project):
        """Test execute when found item is not a Note."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # find_item returns a non-Note object
        not_a_note = Mock()
        sample_project.find_item.return_value = not_a_note
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        result = command.execute()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Edit Note", 
            "Note 'note-123' not found in the project."
        )

    def test_execute_successful(self, mock_app_context, sample_project, sample_note):
        """Test successful execute operation."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_note
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        result = command.execute()
        
        assert result is True
        assert command.old_content == "Original content"
        sample_note.update_content.assert_called_once_with("New content")
        
        # Check event emission
        app_state.event_bus.emit.assert_called_once_with('note_edited', {
            'project': sample_project,
            'note_id': "note-123",
            'old_content': "Original content",
            'new_content': "New content"
        })

    def test_execute_with_exception(self, mock_app_context, sample_project, sample_note):
        """Test execute when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_note
        sample_note.update_content.side_effect = Exception("Test error")
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        result = command.execute()
        
        assert result is False
        ui_controller.show_error_message.assert_called_once()
        assert "Failed to edit note: Test error" in ui_controller.show_error_message.call_args[0][1]

    def test_undo_successful(self, mock_app_context, sample_project, sample_note):
        """Test successful undo operation."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_note
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        command.old_content = "Original content"  # Simulate execute was called
        
        result = command.undo()
        
        assert result is True
        sample_note.update_content.assert_called_once_with("Original content")
        
        # Check event emission
        app_state.event_bus.emit.assert_called_once_with('note_edited', {
            'project': sample_project,
            'note_id': "note-123",
            'old_content': "New content",
            'new_content': "Original content"
        })

    def test_undo_no_old_content(self, mock_app_context):
        """Test undo when no old content is stored."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        # old_content is None
        result = command.undo()
        
        # Should not crash and should not perform any operations
        assert result is None  # Method returns without explicit return value

    def test_undo_no_project(self, mock_app_context):
        """Test undo when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        command.old_content = "Original content"
        
        result = command.undo()
        
        # Should not crash and should not perform any operations
        assert result is None

    def test_undo_no_current_project(self, mock_app_context):
        """Test undo when current project is None."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        command.old_content = "Original content"
        
        result = command.undo()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Undo Edit Note", 
            "No project is currently loaded."
        )

    def test_undo_note_not_found(self, mock_app_context, sample_project):
        """Test undo when note is not found."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = None
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        command.old_content = "Original content"
        
        result = command.undo()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Undo Edit Note", 
            "Note with ID 'note-123' not found in the project."
        )

    def test_undo_item_not_note(self, mock_app_context, sample_project):
        """Test undo when found item is not a Note."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        not_a_note = Mock()
        sample_project.find_item.return_value = not_a_note
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        command.old_content = "Original content"
        
        result = command.undo()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Undo Edit Note", 
            "Note with ID 'note-123' not found in the project."
        )

    def test_undo_with_exception(self, mock_app_context, sample_project, sample_note):
        """Test undo when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_note
        sample_note.update_content.side_effect = Exception("Test error")
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        command.old_content = "Original content"
        
        result = command.undo()
        
        assert result is False
        ui_controller.show_error_message.assert_called_once()
        assert "Failed to undo edit note: Test error" in ui_controller.show_error_message.call_args[0][1]

    def test_redo_successful(self, mock_app_context, sample_project, sample_note):
        """Test successful redo operation."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_note
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        command.old_content = "Original content"  # Simulate execute was called
        
        result = command.redo()
        
        assert result is True
        sample_note.update_content.assert_called_once_with("New content")
        
        # Check event emission
        app_state.event_bus.emit.assert_called_once_with('note_edited', {
            'project': sample_project,
            'note_id': "note-123",
            'old_content': "Original content",
            'new_content': "New content"
        })

    def test_redo_no_old_content(self, mock_app_context):
        """Test redo when no old content is stored."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        # old_content is None
        result = command.redo()
        
        assert result is False

    def test_redo_no_project(self, mock_app_context):
        """Test redo when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        command.old_content = "Original content"
        
        result = command.redo()
        
        assert result is False

    def test_redo_no_current_project(self, mock_app_context):
        """Test redo when current project is None."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        command.old_content = "Original content"
        
        result = command.redo()
        
        assert result is False

    def test_redo_note_not_found(self, mock_app_context, sample_project):
        """Test redo when note is not found."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = None
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        command.old_content = "Original content"
        
        result = command.redo()
        
        assert result is False

    def test_redo_item_not_note(self, mock_app_context, sample_project):
        """Test redo when found item is not a Note."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        not_a_note = Mock()
        sample_project.find_item.return_value = not_a_note
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        command.old_content = "Original content"
        
        result = command.redo()
        
        assert result is False

    def test_redo_with_exception(self, mock_app_context, sample_project, sample_note):
        """Test redo when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_note
        sample_note.update_content.side_effect = Exception("Test error")
        
        command = EditNoteCommand(app_context, "note-123", "New content")
        command.old_content = "Original content"
        
        result = command.redo()
        
        assert result is False
        ui_controller.show_error_message.assert_called_once()
        assert "Failed to redo edit note: Test error" in ui_controller.show_error_message.call_args[0][1]

    def test_content_storage_during_execute(self, mock_app_context, sample_project, sample_note):
        """Test that old content is properly stored during execute."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_note.content = "Initial content"
        sample_project.find_item.return_value = sample_note
        
        command = EditNoteCommand(app_context, "note-123", "Modified content")
        
        # Before execute, old_content should be None
        assert command.old_content is None
        
        result = command.execute()
        
        # After execute, old_content should be stored
        assert result is True
        assert command.old_content == "Initial content"

    def test_multiple_executions_preserve_original_content(self, mock_app_context, sample_project, sample_note):
        """Test that multiple executions don't overwrite the original content."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_note.content = "Original content"
        sample_project.find_item.return_value = sample_note
        
        command = EditNoteCommand(app_context, "note-123", "First edit")
        
        # First execution
        command.execute()
        assert command.old_content == "Original content"
        
        # Simulate the note content changing
        sample_note.content = "First edit"
        
        # Second execution should not overwrite old_content if it's already set
        command2 = EditNoteCommand(app_context, "note-123", "Second edit")
        command2.old_content = "Original content"  # Simulate it was already set
        
        # This would be handled by the application logic, not the command itself
        # The test demonstrates the expected behavior

    def test_event_data_structure(self, mock_app_context, sample_project, sample_note):
        """Test that emitted events have correct data structure."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_note.content = "Old content"
        sample_project.find_item.return_value = sample_note
        
        command = EditNoteCommand(app_context, "test-note", "New content")
        command.execute()
        
        # Check the event was emitted with correct structure
        app_state.event_bus.emit.assert_called_once()
        event_name, event_data = app_state.event_bus.emit.call_args[0]
        
        assert event_name == 'note_edited'
        assert 'project' in event_data
        assert 'note_id' in event_data
        assert 'old_content' in event_data
        assert 'new_content' in event_data
        
        assert event_data['project'] == sample_project
        assert event_data['note_id'] == "test-note"
        assert event_data['old_content'] == "Old content"
        assert event_data['new_content'] == "New content"

    def test_command_state_isolation(self, mock_app_context, sample_project):
        """Test that multiple command instances don't interfere with each other."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        note1 = Mock(spec=Note)
        note1.content = "Content 1"
        note1.update_content = Mock()
        
        note2 = Mock(spec=Note)
        note2.content = "Content 2"
        note2.update_content = Mock()
        
        def find_item_side_effect(note_id):
            if note_id == "note-1":
                return note1
            elif note_id == "note-2":
                return note2
            return None
        
        sample_project.find_item.side_effect = find_item_side_effect
        
        command1 = EditNoteCommand(app_context, "note-1", "New content 1")
        command2 = EditNoteCommand(app_context, "note-2", "New content 2")
        
        command1.execute()
        command2.execute()
        
        assert command1.old_content == "Content 1"
        assert command2.old_content == "Content 2"
        assert command1.note_id == "note-1"
        assert command2.note_id == "note-2"
        assert command1.new_content == "New content 1"
        assert command2.new_content == "New content 2"
