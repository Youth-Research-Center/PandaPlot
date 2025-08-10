import pytest
from unittest.mock import Mock

from pandaplot.commands.project.item.delete_item_command import DeleteItemCommand
from pandaplot.models.project.items.note import Note
from pandaplot.models.project.items.folder import Folder
from pandaplot.models.project.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState
from pandaplot.gui.controllers.ui_controller import UIController


class TestDeleteItemCommand:
    """Test suite for DeleteItemCommand."""
    
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
        project.remove_item = Mock()
        project.add_item = Mock()
        return project

    @pytest.fixture
    def sample_note(self):
        """Create a sample note for testing."""
        note = Note(id="note-123", name="Test Note", content="Test content")
        return note

    @pytest.fixture
    def sample_folder(self):
        """Create a sample folder for testing."""
        folder = Folder(id="folder-123", name="Test Folder")
        return folder

    def test_init_values(self, mock_app_context):
        """Test command initialization."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = DeleteItemCommand(app_context, "item-123")
        
        assert command.app_context == app_context
        assert command.app_state == app_state
        assert command.ui_controller == ui_controller
        assert command.item_id == "item-123"
        assert command.deleted_item_data is None
        assert command.deleted_item_class is None
        assert command.parent_item is None

    def test_execute_no_project_loaded(self, mock_app_context):
        """Test execute when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = DeleteItemCommand(app_context, "item-123")
        result = command.execute()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Delete Item", 
            "No project is currently loaded."
        )

    def test_execute_no_current_project(self, mock_app_context):
        """Test execute when current project is None."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None
        
        command = DeleteItemCommand(app_context, "item-123")
        result = command.execute()
        
        assert result is False

    def test_execute_item_not_found(self, mock_app_context, sample_project):
        """Test execute when item is not found."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # find_item returns None
        sample_project.find_item.return_value = None
        
        command = DeleteItemCommand(app_context, "item-123")
        result = command.execute()
        
        assert result is False
        sample_project.find_item.assert_called_once_with("item-123")
        ui_controller.show_warning_message.assert_called_once_with(
            "Delete Item", 
            "Item 'item-123' not found in the project."
        )

    def test_execute_user_cancels_deletion(self, mock_app_context, sample_project, sample_note):
        """Test execute when user cancels the deletion."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_note
        ui_controller.show_question.return_value = False  # User cancels
        
        command = DeleteItemCommand(app_context, "note-123")
        result = command.execute()
        
        assert result is False
        ui_controller.show_question.assert_called_once_with(
            "Delete Item",
            "Are you sure you want to delete the note 'Test Note'?\nThis action cannot be undone."
        )
        sample_project.remove_item.assert_not_called()

    def test_execute_successful_note_deletion(self, mock_app_context, sample_project, sample_note):
        """Test successful deletion of a note."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_note
        ui_controller.show_question.return_value = True  # User confirms
        
        command = DeleteItemCommand(app_context, "note-123")
        result = command.execute()
        
        assert result is True
        assert command.deleted_item_class == Note
        assert command.deleted_item_data is not None
        assert command.deleted_item_data['id'] == "note-123"
        assert command.deleted_item_data['name'] == "Test Note"
        assert command.deleted_item_data['content'] == "Test content"
        
        sample_project.remove_item.assert_called_once_with(sample_note)
        
        # Check event emission
        app_state.event_bus.emit.assert_called_once_with('item_deleted', {
            'project': sample_project,
            'item_id': "note-123",
            'item_type': "note",
            'item_name': "Test Note",
            'item_data': command.deleted_item_data
        })

    def test_execute_successful_folder_deletion(self, mock_app_context, sample_project, sample_folder):
        """Test successful deletion of a folder."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_folder
        ui_controller.show_question.return_value = True  # User confirms
        
        command = DeleteItemCommand(app_context, "folder-123")
        result = command.execute()
        
        assert result is True
        assert command.deleted_item_class == Folder
        assert command.deleted_item_data is not None
        assert command.deleted_item_data['id'] == "folder-123"
        assert command.deleted_item_data['name'] == "Test Folder"
        
        sample_project.remove_item.assert_called_once_with(sample_folder)

    def test_execute_with_parent_item(self, mock_app_context, sample_project, sample_note):
        """Test execute with item that has a parent."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # Set up parent relationship
        parent_folder = Folder(id="parent-123", name="Parent Folder")
        sample_note.parent_id = "parent-123"
        
        def find_item_side_effect(item_id):
            if item_id == "note-123":
                return sample_note
            elif item_id == "parent-123":
                return parent_folder
            return None
        
        sample_project.find_item.side_effect = find_item_side_effect
        ui_controller.show_question.return_value = True
        
        command = DeleteItemCommand(app_context, "note-123")
        result = command.execute()
        
        assert result is True
        assert command.parent_item == parent_folder

    def test_execute_with_exception(self, mock_app_context, sample_project, sample_note):
        """Test execute when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_note
        ui_controller.show_question.return_value = True
        sample_project.remove_item.side_effect = Exception("Test error")
        
        command = DeleteItemCommand(app_context, "note-123")
        result = command.execute()
        
        assert result is False
        ui_controller.show_error_message.assert_called_once()
        assert "Failed to delete item: Test error" in ui_controller.show_error_message.call_args[0][1]

    def test_undo_successful(self, mock_app_context, sample_project, sample_note):
        """Test successful undo operation."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = DeleteItemCommand(app_context, "note-123")
        command.deleted_item_class = Note
        command.deleted_item_data = sample_note.to_dict()
        
        result = command.undo()
        
        assert result is True
        
        # Verify add_item was called with recreated note
        sample_project.add_item.assert_called_once()
        restored_item = sample_project.add_item.call_args[0][0]
        assert isinstance(restored_item, Note)
        assert restored_item.id == "note-123"
        assert restored_item.name == "Test Note"
        assert restored_item.content == "Test content"
        
        # Check event emission
        app_state.event_bus.emit.assert_called_once_with('item_restored', {
            'project': sample_project,
            'item_id': "note-123",
            'item_type': "note",
            'item_name': "Test Note",
            'item': restored_item
        })

    def test_undo_with_parent(self, mock_app_context, sample_project, sample_note):
        """Test undo with parent item."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        parent_folder = Folder(id="parent-123", name="Parent Folder")
        
        command = DeleteItemCommand(app_context, "note-123")
        command.deleted_item_class = Note
        command.deleted_item_data = sample_note.to_dict()
        command.parent_item = parent_folder
        
        result = command.undo()
        
        assert result is True
        
        # Verify add_item was called with parent_id
        sample_project.add_item.assert_called_once()
        call_args = sample_project.add_item.call_args
        assert call_args[1]['parent_id'] == "parent-123"

    def test_undo_no_deleted_data(self, mock_app_context):
        """Test undo when no deleted data is stored."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = DeleteItemCommand(app_context, "item-123")
        # deleted_item_data is None
        result = command.undo()
        
        assert result is False

    def test_undo_no_project(self, mock_app_context):
        """Test undo when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = DeleteItemCommand(app_context, "item-123")
        command.deleted_item_class = Note
        command.deleted_item_data = {"id": "note-123", "name": "Test"}
        
        result = command.undo()
        
        assert result is False

    def test_undo_with_exception(self, mock_app_context, sample_project, sample_note):
        """Test undo when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.add_item.side_effect = Exception("Test error")
        
        command = DeleteItemCommand(app_context, "note-123")
        command.deleted_item_class = Note
        command.deleted_item_data = sample_note.to_dict()
        
        result = command.undo()
        
        assert result is False
        ui_controller.show_error_message.assert_called_once()
        assert "Failed to undo delete item: Test error" in ui_controller.show_error_message.call_args[0][1]

    def test_redo_successful(self, mock_app_context, sample_project, sample_note):
        """Test successful redo operation."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_note
        
        command = DeleteItemCommand(app_context, "note-123")
        command.deleted_item_class = Note
        command.deleted_item_data = sample_note.to_dict()
        
        result = command.redo()
        
        assert result is True
        sample_project.remove_item.assert_called_once_with(sample_note)
        
        # Check event emission
        app_state.event_bus.emit.assert_called_once_with('item_deleted', {
            'project': sample_project,
            'item_id': "note-123",
            'item_type': "note",
            'item_name': "Test Note",
            'item_data': command.deleted_item_data
        })

    def test_redo_no_deleted_data(self, mock_app_context):
        """Test redo when no deleted data is stored."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = DeleteItemCommand(app_context, "item-123")
        # deleted_item_data is None
        result = command.redo()
        
        assert result is False

    def test_redo_item_not_found(self, mock_app_context, sample_project):
        """Test redo when item is not found."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = None
        
        command = DeleteItemCommand(app_context, "note-123")
        command.deleted_item_class = Note
        command.deleted_item_data = {"id": "note-123", "name": "Test"}
        
        result = command.redo()
        
        assert result is False

    def test_redo_with_exception(self, mock_app_context, sample_project, sample_note):
        """Test redo when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_note
        sample_project.remove_item.side_effect = Exception("Test error")
        
        command = DeleteItemCommand(app_context, "note-123")
        command.deleted_item_class = Note
        command.deleted_item_data = sample_note.to_dict()
        
        result = command.redo()
        
        assert result is False
        ui_controller.show_error_message.assert_called_once()
        assert "Failed to redo delete item: Test error" in ui_controller.show_error_message.call_args[0][1]

    def test_different_item_types(self, mock_app_context, sample_project):
        """Test deletion of different item types."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        ui_controller.show_question.return_value = True
        
        # Test different item types
        test_cases = [
            (Note(id="note-1", name="Test Note"), "note"),
            (Folder(id="folder-1", name="Test Folder"), "folder"),
        ]
        
        for item, expected_type in test_cases:
            sample_project.find_item.return_value = item
            sample_project.remove_item.reset_mock()
            app_state.event_bus.emit.reset_mock()
            
            command = DeleteItemCommand(app_context, item.id)
            result = command.execute()
            
            assert result is True
            assert command.deleted_item_class is type(item)
            sample_project.remove_item.assert_called_once_with(item)
            
            # Check event emission
            event_call = app_state.event_bus.emit.call_args
            assert event_call[0][0] == 'item_deleted'
            assert event_call[0][1]['item_type'] == expected_type

    def test_serialization_round_trip(self, mock_app_context, sample_project):
        """Test that items can be properly serialized and deserialized."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # Create a note with complex data
        original_note = Note(
            id="complex-note",
            name="Complex Note",
            content="This is complex content with\nmultiple lines",
            tags=["tag1", "tag2"]
        )
        original_note.parent_id = "parent-123"
        original_note.metadata = {"custom": "data", "number": 42}
        
        command = DeleteItemCommand(app_context, "complex-note")
        command.deleted_item_class = Note
        command.deleted_item_data = original_note.to_dict()
        
        # Simulate undo to recreate the item
        result = command.undo()
        
        assert result is True
        
        # Verify the recreated item matches the original
        sample_project.add_item.assert_called_once()
        recreated_item = sample_project.add_item.call_args[0][0]
        
        assert isinstance(recreated_item, Note)
        assert recreated_item.id == original_note.id
        assert recreated_item.name == original_note.name
        assert recreated_item.content == original_note.content
        assert recreated_item.tags == original_note.tags
        assert recreated_item.parent_id == original_note.parent_id
        assert recreated_item.metadata == original_note.metadata

    def test_event_data_structure(self, mock_app_context, sample_project, sample_note):
        """Test that emitted events have correct data structure."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_note
        ui_controller.show_question.return_value = True
        
        command = DeleteItemCommand(app_context, "note-123")
        command.execute()
        
        # Check delete event structure
        app_state.event_bus.emit.assert_called_once()
        event_name, event_data = app_state.event_bus.emit.call_args[0]
        
        assert event_name == 'item_deleted'
        assert 'project' in event_data
        assert 'item_id' in event_data
        assert 'item_type' in event_data
        assert 'item_name' in event_data
        assert 'item_data' in event_data
        
        assert event_data['project'] == sample_project
        assert event_data['item_id'] == "note-123"
        assert event_data['item_type'] == "note"
        assert event_data['item_name'] == "Test Note"
        assert event_data['item_data'] == command.deleted_item_data

    def test_command_state_isolation(self, mock_app_context, sample_project):
        """Test that multiple command instances don't interfere with each other."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        ui_controller.show_question.return_value = True
        
        note1 = Note(id="note-1", name="Note 1")
        note2 = Note(id="note-2", name="Note 2")
        
        def find_item_side_effect(item_id):
            if item_id == "note-1":
                return note1
            elif item_id == "note-2":
                return note2
            return None
        
        sample_project.find_item.side_effect = find_item_side_effect
        
        command1 = DeleteItemCommand(app_context, "note-1")
        command2 = DeleteItemCommand(app_context, "note-2")
        
        command1.execute()
        command2.execute()
        
        # Verify each command has its own state
        assert command1.deleted_item_class == Note
        assert command2.deleted_item_class == Note
        assert command1.deleted_item_data is not None
        assert command2.deleted_item_data is not None
        assert command1.deleted_item_data['id'] == "note-1"
        assert command2.deleted_item_data['id'] == "note-2"
        assert command1.deleted_item_data['name'] == "Note 1"
        assert command2.deleted_item_data['name'] == "Note 2"
