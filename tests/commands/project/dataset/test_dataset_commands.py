"""Tests for dataset commands and the DatasetCommand base class."""

import pytest
import pandas as pd
from unittest.mock import Mock

from pandaplot.commands.project.dataset.dataset_command import DatasetCommand
from pandaplot.commands.project.dataset.delete_rows_command import DeleteRowsCommand
from pandaplot.commands.project.dataset.delete_columns_command import DeleteColumnsCommand
from pandaplot.commands.project.dataset.add_rows_command import AddRowsCommand
from pandaplot.commands.project.dataset.add_columns_command import AddColumnsCommand
from pandaplot.commands.project.dataset.edit_command import EditCommand
from pandaplot.commands.project.dataset.edit_batch_command import EditBatchCommand
from pandaplot.commands.project.dataset.change_column_dtype_command import ChangeColumnDtypeCommand
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items import Folder
from pandaplot.models.project import Project
from pandaplot.models.state import AppState, AppContext
from pandaplot.gui.controllers.ui_controller import UIController


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_app_context():
    """Create mock app context with all dependencies."""
    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    ui_controller = Mock(spec=UIController)

    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = ui_controller
    app_context.app_state = app_state

    app_state.event_bus = Mock()
    app_state.event_bus.emit = Mock()
    app_context.event_bus = app_state.event_bus

    return app_context, app_state, ui_controller


@pytest.fixture
def sample_dataset():
    """Create a sample dataset with numeric data."""
    df = pd.DataFrame({
        'x': [1.0, 2.0, 3.0, 4.0, 5.0],
        'y': [10.0, 20.0, 30.0, 40.0, 50.0],
        'label': ['a', 'b', 'c', 'd', 'e'],
    })
    return Dataset(id='ds-1', name='Test Dataset', data=df)


@pytest.fixture
def sample_project(sample_dataset):
    """Create a project containing a sample dataset."""
    project = Project('Test Project')
    project.add_item(sample_dataset)
    return project


def _setup_project(app_state, project):
    """Wire up app_state so it looks like a project is loaded."""
    app_state.has_project = True
    app_state.current_project = project


# ===========================================================================
# DatasetCommand base class
# ===========================================================================

class TestDatasetCommandBase:
    """Tests for the shared _validate_and_get_dataset / _resolve_dataset helpers."""

    def test_validate_no_project(self, mock_app_context):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False

        cmd = DeleteRowsCommand(app_context, 'ds-1', [0])
        result = cmd._validate_and_get_dataset('Test')

        assert result is False
        ui_controller.show_warning_message.assert_called_once()

    def test_validate_project_none(self, mock_app_context):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = True
        app_state.current_project = None

        cmd = DeleteRowsCommand(app_context, 'ds-1', [0])
        result = cmd._validate_and_get_dataset('Test')

        assert result is False

    def test_validate_dataset_not_found(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = DeleteRowsCommand(app_context, 'nonexistent', [0])
        result = cmd._validate_and_get_dataset('Test')

        assert result is False
        ui_controller.show_error_message.assert_called_once()

    def test_validate_item_not_dataset(self, mock_app_context):
        app_context, app_state, ui_controller = mock_app_context
        project = Project('P')
        folder = Folder(id='folder-1', name='Not a dataset')
        project.add_item(folder)
        _setup_project(app_state, project)

        cmd = DeleteRowsCommand(app_context, 'folder-1', [0])
        result = cmd._validate_and_get_dataset('Test')

        assert result is False
        ui_controller.show_error_message.assert_called()

    def test_validate_success(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = DeleteRowsCommand(app_context, 'ds-1', [0])
        result = cmd._validate_and_get_dataset('Test')

        assert result is True
        assert cmd.dataset is sample_dataset
        assert cmd.project is sample_project

    def test_resolve_dataset_success(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = DeleteRowsCommand(app_context, 'ds-1', [0])
        ds = cmd._resolve_dataset()

        assert ds is sample_dataset

    def test_resolve_dataset_not_found(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = DeleteRowsCommand(app_context, 'nonexistent', [0])
        ds = cmd._resolve_dataset()

        assert ds is None


# ===========================================================================
# DeleteRowsCommand
# ===========================================================================

class TestDeleteRowsCommand:

    def test_execute_success(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = DeleteRowsCommand(app_context, 'ds-1', [1, 3])
        assert cmd.execute() is True

        assert len(sample_dataset.data) == 3
        assert list(sample_dataset.data['x']) == [1.0, 3.0, 5.0]
        app_state.event_bus.emit.assert_called_once()

    def test_execute_no_rows_specified(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = DeleteRowsCommand(app_context, 'ds-1', [])
        assert cmd.execute() is False
        ui_controller.show_warning_message.assert_called()

    def test_execute_invalid_row_position(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = DeleteRowsCommand(app_context, 'ds-1', [99])
        assert cmd.execute() is False
        ui_controller.show_error_message.assert_called()

    def test_undo_restores_data(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        original_data = sample_dataset.data.copy()
        cmd = DeleteRowsCommand(app_context, 'ds-1', [0])
        cmd.execute()
        assert len(sample_dataset.data) == 4

        cmd.undo()
        pd.testing.assert_frame_equal(sample_dataset.data, original_data)

    def test_redo_reapplies(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = DeleteRowsCommand(app_context, 'ds-1', [0])
        cmd.execute()
        cmd.undo()
        cmd.redo()

        assert len(sample_dataset.data) == 4


# ===========================================================================
# DeleteColumnsCommand
# ===========================================================================

class TestDeleteColumnsCommand:

    def test_execute_by_position(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = DeleteColumnsCommand(app_context, 'ds-1', [2])  # delete 'label'
        assert cmd.execute() is True
        assert list(sample_dataset.data.columns) == ['x', 'y']

    def test_execute_by_name(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = DeleteColumnsCommand(app_context, 'ds-1', ['label'])
        assert cmd.execute() is True
        assert 'label' not in sample_dataset.data.columns

    def test_execute_no_columns_specified(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = DeleteColumnsCommand(app_context, 'ds-1', [])
        assert cmd.execute() is False

    def test_undo_restores_columns(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        original = sample_dataset.data.copy()
        cmd = DeleteColumnsCommand(app_context, 'ds-1', ['y'])
        cmd.execute()
        assert 'y' not in sample_dataset.data.columns

        cmd.undo()
        pd.testing.assert_frame_equal(sample_dataset.data, original)


# ===========================================================================
# AddRowsCommand
# ===========================================================================

class TestAddRowsCommand:

    def test_execute_adds_rows_below(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = AddRowsCommand(app_context, 'ds-1', [2], side='below')
        assert cmd.execute() is True
        assert len(sample_dataset.data) == 6

    def test_execute_adds_rows_above(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = AddRowsCommand(app_context, 'ds-1', [0], side='above')
        assert cmd.execute() is True
        assert len(sample_dataset.data) == 6

    def test_execute_consecutive_positions(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = AddRowsCommand(app_context, 'ds-1', [1, 2, 3], side='below')
        assert cmd.execute() is True
        assert len(sample_dataset.data) == 8  # 5 + 3

    def test_execute_no_positions(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = AddRowsCommand(app_context, 'ds-1', [])
        assert cmd.execute() is False

    def test_execute_invalid_position(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = AddRowsCommand(app_context, 'ds-1', [99])
        assert cmd.execute() is False

    def test_undo(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        original = sample_dataset.data.copy()
        cmd = AddRowsCommand(app_context, 'ds-1', [0], side='below')
        cmd.execute()
        cmd.undo()

        pd.testing.assert_frame_equal(sample_dataset.data, original)


# ===========================================================================
# AddColumnsCommand
# ===========================================================================

class TestAddColumnsCommand:

    def test_execute_adds_column_right(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = AddColumnsCommand(app_context, 'ds-1', ['new_col'], [1], side='right')
        assert cmd.execute() is True
        assert 'new_col' in sample_dataset.data.columns

    def test_execute_adds_column_left(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = AddColumnsCommand(app_context, 'ds-1', ['new_col'], [0], side='left')
        assert cmd.execute() is True
        assert sample_dataset.data.columns[0] == 'new_col'

    def test_execute_duplicate_name(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = AddColumnsCommand(app_context, 'ds-1', ['x'], [0])
        assert cmd.execute() is False
        ui_controller.show_warning_message.assert_called()

    def test_undo(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        original = sample_dataset.data.copy()
        cmd = AddColumnsCommand(app_context, 'ds-1', ['new_col'], [0])
        cmd.execute()
        cmd.undo()

        pd.testing.assert_frame_equal(sample_dataset.data, original)


# ===========================================================================
# EditCommand
# ===========================================================================

class TestEditCommand:

    def test_execute_success(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = EditCommand(app_context, 'ds-1', (0, 0), 1.0, 999.0)
        assert cmd.execute() is True
        assert sample_dataset.data.iloc[0, 0] == 999.0

    def test_execute_no_project(self, mock_app_context):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False

        cmd = EditCommand(app_context, 'ds-1', (0, 0), 1.0, 999.0)
        assert cmd.execute() is False

    def test_undo(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = EditCommand(app_context, 'ds-1', (0, 0), 1.0, 999.0)
        cmd.execute()

        cmd.undo()
        assert sample_dataset.data.iloc[0, 0] == 1.0

    def test_redo(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = EditCommand(app_context, 'ds-1', (0, 0), 1.0, 999.0)
        cmd.execute()
        cmd.undo()
        cmd.redo()

        assert sample_dataset.data.iloc[0, 0] == 999.0

    def test_emits_event(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = EditCommand(app_context, 'ds-1', (2, 1), 30.0, 77.0)
        cmd.execute()

        app_context.event_bus.emit.assert_called_once()


# ===========================================================================
# EditBatchCommand
# ===========================================================================

class TestEditBatchCommand:

    def test_execute_success(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        new_data = [[100.0, 200.0], [300.0, 400.0]]
        cmd = EditBatchCommand(app_context, 'ds-1', 0, 0, new_data)
        assert cmd.execute() is True

        assert sample_dataset.data.iloc[0, 0] == 100.0
        assert sample_dataset.data.iloc[0, 1] == 200.0
        assert sample_dataset.data.iloc[1, 0] == 300.0
        assert sample_dataset.data.iloc[1, 1] == 400.0

    def test_execute_no_data(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = EditBatchCommand(app_context, 'ds-1', 0, 0, [])
        assert cmd.execute() is False

    def test_undo_restores_values(self, mock_app_context, sample_project, sample_dataset):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        original_val = sample_dataset.data.iloc[0, 0]
        cmd = EditBatchCommand(app_context, 'ds-1', 0, 0, [[999.0]])
        cmd.execute()
        cmd.undo()

        assert sample_dataset.data.iloc[0, 0] == original_val

    def test_execute_within_bounds(self, mock_app_context, sample_project, sample_dataset):
        """Batch edit within existing bounds should succeed."""
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        new_data = [[100.0], [200.0]]
        cmd = EditBatchCommand(app_context, 'ds-1', 3, 0, new_data)
        assert cmd.execute() is True
        assert sample_dataset.data.iloc[3, 0] == 100.0
        assert sample_dataset.data.iloc[4, 0] == 200.0


# ===========================================================================
# ChangeColumnDtypeCommand
# ===========================================================================

class TestChangeColumnDtypeCommand:

    def test_execute_string_to_float(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        ds = sample_project.find_item('ds-1')
        df = pd.DataFrame({'nums': ['1.5', '2.5', '3.5']})
        ds.set_data(df)

        cmd = ChangeColumnDtypeCommand(app_context, 'ds-1', 0, 'float64')
        assert cmd.execute() is True
        assert pd.api.types.is_float_dtype(ds.data['nums'])

    def test_execute_same_dtype_noop(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        ds = sample_project.find_item('ds-1')
        original_dtype = str(ds.data['x'].dtype)

        cmd = ChangeColumnDtypeCommand(app_context, 'ds-1', 0, original_dtype)
        assert cmd.execute() is True  # succeeds but is a no-op
        ui_controller.show_info_message.assert_called()

    def test_execute_invalid_column_index(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        cmd = ChangeColumnDtypeCommand(app_context, 'ds-1', 99, 'float64')
        assert cmd.execute() is False

    def test_undo_restores_dtype(self, mock_app_context, sample_project):
        app_context, app_state, ui_controller = mock_app_context
        _setup_project(app_state, sample_project)

        ds = sample_project.find_item('ds-1')
        df = pd.DataFrame({'nums': [1, 2, 3]})
        ds.set_data(df)
        original = ds.data['nums'].copy()

        cmd = ChangeColumnDtypeCommand(app_context, 'ds-1', 0, 'string')
        cmd.execute()
        cmd.undo()

        pd.testing.assert_series_equal(ds.data['nums'], original)


# ===========================================================================
# Cross-cutting: no-project / not-a-dataset guards
# ===========================================================================

class TestDatasetCommandGuards:
    """Verify that all commands fail gracefully when project/dataset is missing."""

    @pytest.mark.parametrize('CommandClass, extra_args', [
        (DeleteRowsCommand, [[0]]),
        (DeleteColumnsCommand, [[0]]),
        (AddRowsCommand, [[0]]),
        (AddColumnsCommand, [['col'], [0]]),
        (EditCommand, [(0, 0), 1, 2]),
        (EditBatchCommand, [0, 0, [[1]]]),
        (ChangeColumnDtypeCommand, [0, 'float64']),
    ])
    def test_no_project_returns_false(self, mock_app_context, CommandClass, extra_args):
        app_context, app_state, ui_controller = mock_app_context
        app_state.has_project = False

        cmd = CommandClass(app_context, 'ds-1', *extra_args)
        assert cmd.execute() is False
