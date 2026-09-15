import logging
from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.item import DeleteItemCommand
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.events.event_types import ChartEvents, ProjectEvents
from pandaplot.models.project import Project
from pandaplot.models.project.items import Chart, Dataset, Folder, Note
from pandaplot.models.state import AppContext, AppState


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

        assert result is CommandResult.FAILURE
        ui_controller.show_warning_message.assert_called_once_with(
            "Delete Item",
            "No project is currently loaded."
        )

    def test_execute_no_project_loaded_logs_a_warning(self, mock_app_context, caplog):
        """Test execute logs a warning when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False

        command = DeleteItemCommand(app_context, "item-123")

        with caplog.at_level(logging.WARNING):
            result = command.execute()

        assert result is CommandResult.FAILURE
        assert "DeleteItemCommand.execute" in caplog.text

    def test_execute_no_current_project(self, mock_app_context):
        """Test execute when current project is None."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None

        command = DeleteItemCommand(app_context, "item-123")
        result = command.execute()

        assert result is CommandResult.FAILURE

    def test_execute_no_current_project_logs_a_warning(self, mock_app_context, caplog):
        """Test execute logs a warning when current_project is None."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None

        command = DeleteItemCommand(app_context, "item-123")

        with caplog.at_level(logging.WARNING):
            result = command.execute()

        assert result is CommandResult.FAILURE
        assert "DeleteItemCommand.execute" in caplog.text

    def test_execute_item_not_found(self, mock_app_context, sample_project):
        """Test execute when item is not found."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        # find_item returns None
        sample_project.find_item.return_value = None

        command = DeleteItemCommand(app_context, "item-123")
        result = command.execute()

        assert result is CommandResult.FAILURE
        sample_project.find_item.assert_called_once_with("item-123")
        ui_controller.show_warning_message.assert_called_once_with(
            "Delete Item",
            "Item 'item-123' not found in the project."
        )

    def test_execute_item_not_found_logs_a_warning(self, mock_app_context, sample_project, caplog):
        """Test execute logs a warning when item is not found."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        sample_project.find_item.return_value = None

        command = DeleteItemCommand(app_context, "item-123")

        with caplog.at_level(logging.WARNING):
            result = command.execute()

        assert result is CommandResult.FAILURE
        assert "item-123" in caplog.text

    def test_execute_user_cancels_deletion(self, mock_app_context, sample_project, sample_note):
        """Test execute when user cancels the deletion."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        sample_project.find_item.return_value = sample_note
        ui_controller.show_question.return_value = False  # User cancels
        
        command = DeleteItemCommand(app_context, "note-123")
        result = command.execute()
        
        assert result is CommandResult.FAILURE
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
        
        assert result is CommandResult.SUCCESS
        assert command.deleted_item_class == Note
        assert command.deleted_item_data is not None
        assert command.deleted_item_data["id"] == "note-123"
        assert command.deleted_item_data["name"] == "Test Note"
        assert command.deleted_item_data["content"] == "Test content"
        
        sample_project.remove_item.assert_called_once_with(sample_note)
        
        # Check event emission
        app_state.event_bus.emit.assert_called_once_with(ProjectEvents.PROJECT_ITEM_REMOVED, {
            "project": sample_project,
            "item_id": "note-123",
            "item_type": "note",
            "item_name": "Test Note",
            "item_data": command.deleted_item_data
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
        
        assert result is CommandResult.SUCCESS
        assert command.deleted_item_class == Folder
        assert command.deleted_item_data is not None
        assert command.deleted_item_data["id"] == "folder-123"
        assert command.deleted_item_data["name"] == "Test Folder"
        
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
        
        assert result is CommandResult.SUCCESS
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
        
        assert result is CommandResult.FAILURE
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

        assert result is CommandResult.SUCCESS

        # Verify add_item was called with recreated note
        sample_project.add_item.assert_called_once()
        restored_item = sample_project.add_item.call_args[0][0]
        assert isinstance(restored_item, Note)
        assert restored_item.id == "note-123"
        assert restored_item.name == "Test Note"
        assert restored_item.content == "Test content"
        
        # Check event emission
        app_state.event_bus.emit.assert_called_once_with(ProjectEvents.PROJECT_ITEM_ADDED, {
            "project": sample_project,
            "item_id": "note-123",
            "item_type": "note",
            "item_name": "Test Note",
            "item": restored_item
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

        assert result is CommandResult.SUCCESS

        # Verify add_item was called with parent_id
        sample_project.add_item.assert_called_once()
        call_args = sample_project.add_item.call_args
        assert call_args[1]["parent_id"] == "parent-123"

    def test_undo_no_deleted_data(self, mock_app_context):
        """Test undo when no deleted data is stored."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = DeleteItemCommand(app_context, "item-123")
        # deleted_item_data is None
        result = command.undo()

        assert result is CommandResult.FAILURE

    def test_undo_no_project(self, mock_app_context):
        """Test undo when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False

        command = DeleteItemCommand(app_context, "item-123")
        command.deleted_item_class = Note
        command.deleted_item_data = {"id": "note-123", "name": "Test"}

        result = command.undo()

        assert result is CommandResult.FAILURE

    def test_undo_logs_a_warning_when_current_project_is_none(self, mock_app_context, caplog):
        """Test undo logs a warning when has_project is True but current_project is None."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None

        command = DeleteItemCommand(app_context, "note-123")
        command.deleted_item_class = Note
        command.deleted_item_data = {"id": "note-123", "name": "Test"}

        with caplog.at_level(logging.WARNING):
            result = command.undo()

        assert result is CommandResult.FAILURE
        assert "DeleteItemCommand.undo" in caplog.text
        assert "note-123" in caplog.text

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

        assert result is CommandResult.FAILURE
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

        assert result is CommandResult.SUCCESS
        sample_project.remove_item.assert_called_once_with(sample_note)
        
        # Check event emission
        app_state.event_bus.emit.assert_called_once_with(ProjectEvents.PROJECT_ITEM_REMOVED, {
            "project": sample_project,
            "item_id": "note-123",
            "item_type": "note",
            "item_name": "Test Note",
            "item_data": command.deleted_item_data
        })

    def test_redo_no_deleted_data(self, mock_app_context):
        """Test redo when no deleted data is stored."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = DeleteItemCommand(app_context, "item-123")
        # deleted_item_data is None
        result = command.redo()

        assert result is CommandResult.FAILURE

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

        assert result is CommandResult.FAILURE

    def test_redo_item_not_found_logs_a_warning(self, mock_app_context, sample_project, caplog):
        """Test redo logs a warning when item is not found."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project

        sample_project.find_item.return_value = None

        command = DeleteItemCommand(app_context, "note-123")
        command.deleted_item_class = Note
        command.deleted_item_data = {"id": "note-123", "name": "Test"}

        with caplog.at_level(logging.WARNING):
            result = command.redo()

        assert result is CommandResult.FAILURE
        assert "note-123" in caplog.text

    def test_redo_logs_a_warning_when_current_project_is_none(self, mock_app_context, caplog):
        """Test redo logs a warning when has_project is True but current_project is None."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None

        command = DeleteItemCommand(app_context, "note-123")
        command.deleted_item_class = Note
        command.deleted_item_data = {"id": "note-123", "name": "Test"}

        with caplog.at_level(logging.WARNING):
            result = command.redo()

        assert result is CommandResult.FAILURE
        assert "DeleteItemCommand.redo" in caplog.text
        assert "note-123" in caplog.text

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

        assert result is CommandResult.FAILURE
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
            
            assert result is CommandResult.SUCCESS
            assert command.deleted_item_class is type(item)
            sample_project.remove_item.assert_called_once_with(item)
            
            # Check event emission
            event_call = app_state.event_bus.emit.call_args
            assert event_call[0][0] == ProjectEvents.PROJECT_ITEM_REMOVED
            assert event_call[0][1]["item_type"] == expected_type

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

        assert result is CommandResult.SUCCESS

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
        
        assert event_name == ProjectEvents.PROJECT_ITEM_REMOVED
        assert "project" in event_data
        assert "item_id" in event_data
        assert "item_type" in event_data
        assert "item_name" in event_data
        assert "item_data" in event_data
        
        assert event_data["project"] == sample_project
        assert event_data["item_id"] == "note-123"
        assert event_data["item_type"] == "note"
        assert event_data["item_name"] == "Test Note"
        assert event_data["item_data"] == command.deleted_item_data

    def test_cleanup_releases_undo_state(self, mock_app_context):
        """Test cleanup releases the deleted-item snapshot and parent reference."""
        app_context, app_state, ui_controller = mock_app_context

        command = DeleteItemCommand(app_context, "note-123")
        command.deleted_item_data = {"id": "note-123", "name": "Test"}
        command.deleted_item_class = Note
        command.parent_item = Folder(id="parent-123", name="Parent Folder")

        command.cleanup()

        assert command.deleted_item_data is None
        assert command.deleted_item_class is None
        assert command.parent_item is None

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
        assert command1.deleted_item_data["id"] == "note-1"
        assert command2.deleted_item_data["id"] == "note-2"
        assert command1.deleted_item_data["name"] == "Note 1"
        assert command2.deleted_item_data["name"] == "Note 2"


class TestDeleteItemCommandChartSeriesCascade:
    """Regression (#276): deleting a Dataset must strip any chart data
    series referencing it, not leave them dangling until the project
    reloads and series-to-dataset resolution starts failing at render
    time. Uses a real Project (not the mocked find_item/remove_item/
    add_item of the other tests' sample_project) so add/remove/find and
    the chart's own data_series list all behave for real."""

    @pytest.fixture
    def mock_app_context(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        ui_controller = Mock(spec=UIController)
        app_context.get_app_state.return_value = app_state
        app_context.get_ui_controller.return_value = ui_controller
        app_context.event_bus = Mock()
        app_state.event_bus = Mock()
        return app_context, app_state, ui_controller

    @pytest.fixture
    def project_with_chart(self):
        project = Project("Test Project")
        dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"x": [1, 2], "y": [3, 4]}))
        project.add_item(dataset)
        chart = Chart(id="chart-1", name="Chart")
        chart.add_data_series("ds-1", label="from ds-1")
        chart.add_data_series("ds-other", label="unrelated")
        project.add_item(chart)
        return project, dataset, chart

    def _make_command(self, mock_app_context, project, item_id):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = project
        ui_controller.show_question.return_value = True
        return DeleteItemCommand(app_context, item_id)

    def test_execute_removes_series_referencing_the_deleted_dataset(self, mock_app_context, project_with_chart):
        project, dataset, chart = project_with_chart
        command = self._make_command(mock_app_context, project, "ds-1")

        assert command.execute() is CommandResult.SUCCESS

        assert [s.dataset_id for s in chart.data_series] == ["ds-other"]

    def test_execute_emits_chart_updated_for_the_affected_chart(self, mock_app_context, project_with_chart):
        project, _dataset, chart = project_with_chart
        app_context, _app_state, _ui = mock_app_context
        command = self._make_command(mock_app_context, project, "ds-1")

        command.execute()

        app_context.event_bus.emit.assert_any_call(ChartEvents.CHART_UPDATED, {"chart_id": chart.id})

    def test_execute_leaves_unrelated_charts_untouched(self, mock_app_context, project_with_chart):
        """A chart with no series referencing the deleted dataset must not
        be snapshotted/touched at all."""
        project, dataset, chart = project_with_chart
        other_chart = Chart(id="chart-2", name="Other")
        other_chart.add_data_series("ds-other", label="unrelated only")
        project.add_item(other_chart)
        command = self._make_command(mock_app_context, project, "ds-1")

        command.execute()

        assert other_chart.id not in command._chart_snapshots
        assert len(other_chart.data_series) == 1

    def test_undo_restores_the_removed_series(self, mock_app_context, project_with_chart):
        project, dataset, chart = project_with_chart
        command = self._make_command(mock_app_context, project, "ds-1")
        command.execute()

        assert command.undo() is CommandResult.SUCCESS

        restored_chart = project.find_item("chart-1")
        assert [s.dataset_id for s in restored_chart.data_series] == ["ds-1", "ds-other"]

    def test_redo_removes_the_series_again(self, mock_app_context, project_with_chart):
        """Regression: redo must re-strip the series undo() just restored,
        not assume they're already gone."""
        project, dataset, chart = project_with_chart
        command = self._make_command(mock_app_context, project, "ds-1")
        command.execute()
        command.undo()

        assert command.redo() is CommandResult.SUCCESS

        restored_chart = project.find_item("chart-1")
        assert [s.dataset_id for s in restored_chart.data_series] == ["ds-other"]

    def test_redo_undo_round_trip_is_stable(self, mock_app_context, project_with_chart):
        """A second full undo/redo cycle must behave identically to the
        first -- guards against state left over from the first cycle
        (e.g. a stale snapshot) corrupting the second."""
        project, dataset, chart = project_with_chart
        command = self._make_command(mock_app_context, project, "ds-1")
        command.execute()

        command.undo()
        command.redo()
        command.undo()
        command.redo()

        restored_chart = project.find_item("chart-1")
        assert [s.dataset_id for s in restored_chart.data_series] == ["ds-other"]

    def test_deleting_an_unrelated_note_does_not_touch_any_chart(self, mock_app_context, project_with_chart):
        """A delete with no Dataset involved at all (_dataset_ids_under
        returns empty) must be a complete no-op for _strip_dangling_series
        -- in particular it must never call project.get_all_items() and
        risk an extra CHART_UPDATED emission for unrelated deletes."""
        project, dataset, chart = project_with_chart
        note = Note(id="note-1", name="Unrelated")
        project.add_item(note)
        app_context, _app_state, _ui = mock_app_context
        command = self._make_command(mock_app_context, project, "note-1")

        command.execute()

        app_context.event_bus.emit.assert_not_called()
        assert len(chart.data_series) == 2

    def test_deleting_a_folder_containing_the_dataset_also_strips_series(self, mock_app_context, project_with_chart):
        """project.remove_item() cascades a Folder delete to its children,
        so deleting a Folder containing the referenced Dataset must strip
        chart series the same way deleting the Dataset directly does."""
        project, dataset, chart = project_with_chart
        folder = Folder(id="folder-1", name="Container")
        project.add_item(folder)
        project.remove_item(dataset)
        project.add_item(dataset, parent_id="folder-1")
        command = self._make_command(mock_app_context, project, "folder-1")

        assert command.execute() is CommandResult.SUCCESS

        assert [s.dataset_id for s in chart.data_series] == ["ds-other"]
