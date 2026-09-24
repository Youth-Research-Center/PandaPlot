"""Test suite for PandasTableModel.data() NaN handling.

Regression tests for a bug where pandas/numpy NaN values were displayed
as the literal string "nan" instead of empty cells.
"""
from unittest.mock import Mock

import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.tabs.dataset.pandas_table_model import PandasTableModel
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def mock_app_context():
    """Create a mock AppContext with minimal necessary setup."""
    app_context = Mock(spec=AppContext)
    app_context.event_bus = Mock()
    app_context.event_bus.subscribe = Mock()
    return app_context


@pytest.fixture
def sample_dataset():
    """Create a dataset with mixed data: NaN, normal values, and literal "nan" string."""
    data = pd.DataFrame({
        "float_col": [1.5, float("nan"), 3.5],
        "str_col": ["a", "nan", "c"],
        "int_col": [1, 2, 3],
    })
    return Dataset(id="test-ds", name="Test Dataset", data=data)


def test_nan_float_displays_as_empty_string(mock_app_context, sample_dataset):
    """A float NaN in float_col should display as empty string, not "nan"."""
    model = PandasTableModel(mock_app_context, sample_dataset)

    # Row 1, Col 0 is the NaN cell (float_col column, second row)
    index = model.index(1, 0)
    value = model.data(index, Qt.ItemDataRole.DisplayRole)

    assert value == "", f"Expected empty string for NaN, got: {value!r}"


def test_normal_float_displays_as_string(mock_app_context, sample_dataset):
    """A normal float value should display as its string representation."""
    model = PandasTableModel(mock_app_context, sample_dataset)

    # Row 0, Col 0 is 1.5
    index = model.index(0, 0)
    value = model.data(index, Qt.ItemDataRole.DisplayRole)

    assert value == "1.5", f"Expected '1.5', got: {value!r}"


def test_literal_nan_string_displays_as_nan(mock_app_context, sample_dataset):
    """A literal string 'nan' should display as 'nan', not as empty."""
    model = PandasTableModel(mock_app_context, sample_dataset)

    # Row 1, Col 1 is the literal string "nan" in str_col
    index = model.index(1, 1)
    value = model.data(index, Qt.ItemDataRole.DisplayRole)

    assert value == "nan", f"Expected 'nan' string, got: {value!r}"


def test_edit_role_also_handles_nan(mock_app_context, sample_dataset):
    """EditRole should also return empty string for NaN."""
    model = PandasTableModel(mock_app_context, sample_dataset)

    # Row 1, Col 0 is the NaN cell
    index = model.index(1, 0)
    value = model.data(index, Qt.ItemDataRole.EditRole)

    assert value == "", f"Expected empty string for NaN in EditRole, got: {value!r}"


def test_other_role_returns_none(mock_app_context, sample_dataset):
    """Other roles should return None."""
    model = PandasTableModel(mock_app_context, sample_dataset)

    index = model.index(0, 0)
    value = model.data(index, Qt.ItemDataRole.ToolTipRole)

    assert value is None


def test_invalid_index_returns_none(mock_app_context, sample_dataset):
    """Invalid index should return None."""
    model = PandasTableModel(mock_app_context, sample_dataset)

    # Create an invalid index
    invalid_index = model.index(-1, -1)
    value = model.data(invalid_index, Qt.ItemDataRole.DisplayRole)

    assert value is None
