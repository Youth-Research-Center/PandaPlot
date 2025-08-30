"""
Unit tests for ImportCsvCommand.
"""

import pytest
import pandas as pd
import tempfile
import os
from unittest.mock import Mock, patch
from pathlib import Path

from pandaplot.commands.project.dataset import ImportCsvCommand
from pandaplot.models.events.event_types import DatasetEvents
from pandaplot.models.state import (AppState, AppContext)
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project import Project
from pandaplot.models.project.items import Dataset


class TestImportCsvCommand:
    """Test cases for ImportCsvCommand."""

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

    @pytest.fixture
    def sample_csv_file(self):
        """Create a temporary CSV file for testing."""
        # Create sample data
        data = {
            'Name': ['Alice', 'Bob', 'Charlie'],
            'Age': [25, 30, 35],
            'City': ['New York', 'London', 'Tokyo']
        }
        df = pd.DataFrame(data)
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            df.to_csv(f.name, index=False)
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    @pytest.fixture
    def empty_csv_file(self):
        """Create an empty CSV file for testing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("")  # Empty file
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    @pytest.fixture
    def csv_with_no_data_rows(self):
        """Create a CSV file with headers but no data rows."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write("Name,Age,City\n")  # Headers only, no data rows
            temp_path = f.name
        
        yield temp_path
        
        # Cleanup
        if os.path.exists(temp_path):
            os.unlink(temp_path)

    def test_init_default_values(self, mock_app_context):
        """Test command initialization with default values."""
        app_context, app_state, ui_controller = mock_app_context
        
        command = ImportCsvCommand(app_context)
        
        assert command.app_context == app_context
        assert command.app_state == app_state
        assert command.ui_controller == ui_controller
        assert command.folder_id is None
        assert command.file_path is None
        assert command.dataset_name is None
        assert command.dataset_id is None
        assert command.imported_data is None
        assert command.project is None

    def test_init_with_folder_id(self, mock_app_context):
        """Test command initialization with folder_id."""
        app_context, app_state, ui_controller = mock_app_context
        folder_id = "test-folder-123"
        
        command = ImportCsvCommand(app_context, folder_id)
        
        assert command.folder_id == folder_id

    def test_execute_no_project_loaded(self, mock_app_context):
        """Test execute when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = ImportCsvCommand(app_context)
        result = command.execute()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Import CSV", 
            "Please open or create a project first."
        )

    def test_execute_no_current_project(self, mock_app_context):
        """Test execute when has_project is True but current_project is None."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None
        
        command = ImportCsvCommand(app_context)
        result = command.execute()
        
        assert result is False

    def test_execute_user_cancels_dialog(self, mock_app_context, sample_project):
        """Test execute when user cancels the file dialog."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        ui_controller.show_import_csv_dialog.return_value = None  # User cancelled
        
        command = ImportCsvCommand(app_context)
        result = command.execute()
        
        assert result is False
        ui_controller.show_import_csv_dialog.assert_called_once()

    def test_execute_file_not_found(self, mock_app_context, sample_project):
        """Test execute with non-existent file path."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        ui_controller.show_import_csv_dialog.return_value = "/non/existent/file.csv"
        
        command = ImportCsvCommand(app_context)
        result = command.execute()
        
        assert result is False
        ui_controller.show_error_message.assert_called_once_with(
            "Import CSV", 
            "File not found: /non/existent/file.csv"
        )

    def test_execute_empty_csv_file(self, mock_app_context, sample_project, empty_csv_file):
        """Test execute with completely empty CSV file."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        ui_controller.show_import_csv_dialog.return_value = empty_csv_file
        
        command = ImportCsvCommand(app_context)
        result = command.execute()
        
        assert result is False
        ui_controller.show_error_message.assert_called_once()
        error_call = ui_controller.show_error_message.call_args
        assert error_call[0][0] == "Import CSV Error"
        assert "Failed to read CSV file:" in error_call[0][1]

    def test_execute_csv_with_no_data_rows(self, mock_app_context, sample_project, csv_with_no_data_rows):
        """Test execute with CSV file that has headers but no data rows."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        ui_controller.show_import_csv_dialog.return_value = csv_with_no_data_rows
        
        command = ImportCsvCommand(app_context)
        result = command.execute()
        
        assert result is False
        ui_controller.show_warning_message.assert_called_once_with(
            "Import CSV", 
            "The selected CSV file is empty."
        )

    def test_execute_invalid_csv_file(self, mock_app_context, sample_project):
        """Test execute with invalid CSV file."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        # Create file with UTF-16 encoding which pandas can't decode with default UTF-8
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', encoding='utf-16', delete=False) as f:
            f.write("Name,Age\nAlice,25")
            invalid_csv_path = f.name
        
        try:
            ui_controller.show_import_csv_dialog.return_value = invalid_csv_path
            
            command = ImportCsvCommand(app_context)
            result = command.execute()
            
            assert result is False
            ui_controller.show_error_message.assert_called_once()
            error_call = ui_controller.show_error_message.call_args
            assert error_call[0][0] == "Import CSV Error"
            assert "Failed to read CSV file:" in error_call[0][1]
        finally:
            if os.path.exists(invalid_csv_path):
                os.unlink(invalid_csv_path)

    def test_execute_successful_import(self, mock_app_context, sample_project, sample_csv_file):
        """Test successful CSV import."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        ui_controller.show_import_csv_dialog.return_value = sample_csv_file
        
        # Mock event bus
        event_bus = Mock()
        app_state.event_bus = event_bus
        
        command = ImportCsvCommand(app_context)
        result = command.execute()
        
        assert result is True
        assert command.dataset_id is not None
        assert command.dataset_name == Path(sample_csv_file).stem
        assert command.imported_data is not None
        assert len(command.imported_data) == 3  # 3 rows of data
        assert list(command.imported_data.columns) == ['Name', 'Age', 'City']
        
        # Check that dataset was added to project
        assert command.dataset_id in sample_project.items_index
        dataset = sample_project.find_item(command.dataset_id)
        assert isinstance(dataset, Dataset)
        assert dataset.name == command.dataset_name
        assert dataset.data is not None
        
        # Check event emission
        event_bus.emit.assert_called_once_with(DatasetEvents.DATASET_CREATED, {
            'project': sample_project,
            'dataset_id': command.dataset_id,
            'dataset_name': command.dataset_name,
            'folder_id': None,
            'dataset_data': dataset.data,
            'file_path': sample_csv_file,
            'dataframe': command.imported_data
        })
        
        # Check success message
        ui_controller.show_info_message.assert_called_once()
        info_call = ui_controller.show_info_message.call_args
        assert info_call[0][0] == "Import CSV"
        assert "Successfully imported" in info_call[0][1]
        assert "Rows: 3, Columns: 3" in info_call[0][1]

    def test_execute_with_folder_id(self, mock_app_context, sample_project, sample_csv_file):
        """Test successful CSV import with specific folder_id."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        ui_controller.show_import_csv_dialog.return_value = sample_csv_file
        
        # Mock event bus
        event_bus = Mock()
        app_state.event_bus = event_bus
        
        folder_id = "test-folder-123"
        command = ImportCsvCommand(app_context, folder_id)
        result = command.execute()
        
        assert result is True
        assert command.folder_id == folder_id
        
        # Check that dataset was added to project with correct parent
        dataset = sample_project.find_item(command.dataset_id)
        assert dataset is not None
        # Note: Since we don't have an actual folder in the project, 
        # the item will be added to root, but the folder_id should be passed
        # to the add_item method
        
        # Check event includes folder_id
        event_call = event_bus.emit.call_args
        assert event_call[0][1]['folder_id'] == folder_id

    def test_execute_with_exception(self, mock_app_context, sample_project, sample_csv_file):
        """Test execute when an unexpected exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        ui_controller.show_import_csv_dialog.return_value = sample_csv_file
        
        # Mock project.add_item to raise an exception
        sample_project.add_item = Mock(side_effect=Exception("Test exception"))
        
        command = ImportCsvCommand(app_context)
        result = command.execute()
        
        assert result is False
        ui_controller.show_error_message.assert_called_once()
        error_call = ui_controller.show_error_message.call_args
        assert error_call[0][0] == "Import CSV Error"
        assert "Failed to import CSV: Test exception" in error_call[0][1]

    def test_undo_successful(self, mock_app_context, sample_project, sample_csv_file):
        """Test successful undo operation."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        ui_controller.show_import_csv_dialog.return_value = sample_csv_file
        
        # Mock event bus
        event_bus = Mock()
        app_state.event_bus = event_bus
        
        command = ImportCsvCommand(app_context)
        
        # First execute the command
        result = command.execute()
        assert result is True
        
        # Verify dataset was added
        assert command.dataset_id in sample_project.items_index
        
        # Now undo
        command.undo()
        
        # Verify dataset was removed
        assert command.dataset_id not in sample_project.items_index
        assert sample_project.find_item(command.dataset_id) is None
        
        # Check event emission for undo
        assert event_bus.emit.call_count == 2  # One for import, one for removal
        remove_event_call = event_bus.emit.call_args_list[1]
        assert remove_event_call[0][0] == DatasetEvents.DATASET_DELETED
        assert remove_event_call[0][1]['dataset_id'] == command.dataset_id

    def test_undo_no_dataset_id(self, mock_app_context, sample_project):
        """Test undo when no dataset_id is set."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = ImportCsvCommand(app_context)
        # Don't execute, just try to undo
        command.undo()
        
        # Should complete without error (no dataset to remove)

    def test_undo_no_project(self, mock_app_context):
        """Test undo when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = ImportCsvCommand(app_context)
        command.dataset_id = "test-id"  # Set manually
        command.undo()
        
        # Should complete without error

    def test_undo_with_exception(self, mock_app_context, sample_project, sample_csv_file):
        """Test undo when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        ui_controller.show_import_csv_dialog.return_value = sample_csv_file
        
        command = ImportCsvCommand(app_context)
        
        # Execute first
        result = command.execute()
        assert result is True
        
        # Mock remove_item to raise an exception
        sample_project.remove_item = Mock(side_effect=Exception("Undo test exception"))
        
        command.undo()
        
        ui_controller.show_error_message.assert_called()
        error_call = ui_controller.show_error_message.call_args
        assert error_call[0][0] == "Undo Error"
        assert "Failed to undo CSV import: Undo test exception" in error_call[0][1]

    def test_redo_successful(self, mock_app_context, sample_project, sample_csv_file):
        """Test successful redo operation."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        ui_controller.show_import_csv_dialog.return_value = sample_csv_file
        
        command = ImportCsvCommand(app_context)
        
        # Execute, undo, then redo
        result = command.execute()
        assert result is True
        
        original_dataset_id = command.dataset_id
        
        command.undo()
        assert sample_project.find_item(original_dataset_id) is None
        
        # Reset the dialog mock for redo (it will be called again)
        ui_controller.show_import_csv_dialog.return_value = sample_csv_file
        
        result = command.redo()
        assert result is True
        
        # Note: redo calls execute again, so dataset_id will be different
        assert command.dataset_id is not None
        assert sample_project.find_item(command.dataset_id) is not None

    def test_redo_no_data(self, mock_app_context, sample_project):
        """Test redo when no imported data is available."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        
        command = ImportCsvCommand(app_context)
        # Don't execute first, just try to redo
        result = command.redo()
        
        assert result is None  # redo returns None when conditions not met

    def test_redo_no_project(self, mock_app_context):
        """Test redo when no project is loaded."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False
        
        command = ImportCsvCommand(app_context)
        command.dataset_id = "test-id"
        command.imported_data = pd.DataFrame({'test': [1, 2, 3]})
        
        result = command.redo()
        
        assert result is None

    def test_redo_with_exception(self, mock_app_context, sample_project, sample_csv_file):
        """Test redo when an exception occurs."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        ui_controller.show_import_csv_dialog.return_value = sample_csv_file
        
        command = ImportCsvCommand(app_context)
        
        # Execute first
        result = command.execute()
        assert result is True
        
        # Mock the dialog to raise an exception on redo (which calls execute)
        ui_controller.show_import_csv_dialog.side_effect = Exception("Redo test exception")
        
        result = command.redo()
        
        assert result is False
        ui_controller.show_error_message.assert_called()
        error_call = ui_controller.show_error_message.call_args
        # Since redo calls execute(), the error will be from execute(), not redo()
        assert error_call[0][0] == "Import CSV Error"
        assert "Failed to import CSV: Redo test exception" in error_call[0][1]

    def test_dataset_properties(self, mock_app_context, sample_project, sample_csv_file):
        """Test that the created Dataset object has correct properties."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        ui_controller.show_import_csv_dialog.return_value = sample_csv_file
        
        # Mock event bus
        event_bus = Mock()
        app_state.event_bus = event_bus
        
        command = ImportCsvCommand(app_context)
        result = command.execute()
        
        assert result is True
        
        # Get the created dataset
        dataset = sample_project.find_item(command.dataset_id)
        assert isinstance(dataset, Dataset)
        
        # Check dataset properties
        assert dataset.id == command.dataset_id
        assert dataset.name == Path(sample_csv_file).stem
        assert dataset.source_file == sample_csv_file
        assert dataset.data is not None
        assert len(dataset.data) == 3
        assert list(dataset.data.columns) == ['Name', 'Age', 'City']

    @patch('uuid.uuid4')
    def test_dataset_id_generation(self, mock_uuid, mock_app_context, sample_project, sample_csv_file):
        """Test that dataset ID is generated correctly."""
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = sample_project
        ui_controller.show_import_csv_dialog.return_value = sample_csv_file
        
        # Mock event bus
        event_bus = Mock()
        app_state.event_bus = event_bus
        
        # Mock UUID generation
        test_uuid = "test-uuid-12345"
        mock_uuid.return_value = Mock()
        mock_uuid.return_value.__str__ = Mock(return_value=test_uuid)
        
        command = ImportCsvCommand(app_context)
        result = command.execute()
        
        assert result is True
        assert command.dataset_id == test_uuid
        
        # Verify the dataset exists with the expected ID
        dataset = sample_project.find_item(test_uuid)
        assert dataset is not None
        assert dataset.id == test_uuid

    def test_command_state_isolation(self, mock_app_context):
        """Test that multiple command instances don't interfere with each other."""
        app_context, app_state, ui_controller = mock_app_context
        
        command1 = ImportCsvCommand(app_context, "folder1")
        command2 = ImportCsvCommand(app_context, "folder2")
        
        assert command1.folder_id == "folder1"
        assert command2.folder_id == "folder2"
        assert command1.dataset_id is None
        assert command2.dataset_id is None
        
        # Modifying one shouldn't affect the other
        command1.dataset_id = "test-id-1"
        assert command2.dataset_id is None
