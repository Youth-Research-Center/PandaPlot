"""Test suite for PandasTableModel.data() NaN handling.

Regression tests for a bug where pandas/numpy NaN values were displayed
as the literal string "nan" instead of empty cells.
"""
from unittest.mock import Mock

import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy
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


def test_header_tooltip_explains_a_formula_column(mock_app_context, sample_dataset):
    """Issue #154: the header's "fx" marker needs a tooltip saying what it
    means and which expression produced the column."""
    from pandaplot.models.project.items.formula_column import FormulaColumnSpec
    sample_dataset.set_formula_column(
        sample_dataset.column_id("int_col"),
        FormulaColumnSpec(expression="x * 2", source_column_ids=[sample_dataset.column_id("float_col")], live=True),
    )
    model = PandasTableModel(mock_app_context, sample_dataset)

    tooltip = model.headerData(2, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole)

    assert "recomputes automatically" in tooltip
    assert "x * 2" in tooltip


def test_header_tooltip_is_absent_for_a_plain_column(mock_app_context, sample_dataset):
    model = PandasTableModel(mock_app_context, sample_dataset)

    assert model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole) is None


def test_header_display_role_still_returns_the_plain_column_name(mock_app_context, sample_dataset):
    model = PandasTableModel(mock_app_context, sample_dataset)

    assert model.headerData(0, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) == "float_col"


@pytest.fixture
def formula_dataset():
    """a is plain; b is a live formula over a; c is a static formula over a."""
    from pandaplot.models.project.items.formula_column import FormulaColumnSpec
    dataset = Dataset(id="ds", name="Formulas", data=pd.DataFrame({
        "a": [1.0, 2.0], "b": [2.0, 4.0], "c": [3.0, 6.0],
    }))
    a_id = dataset.column_id("a")
    dataset.set_formula_column(dataset.column_id("b"), FormulaColumnSpec(
        expression="x * 2", source_column_ids=[a_id], live=True))
    dataset.set_formula_column(dataset.column_id("c"), FormulaColumnSpec(
        expression="x * 3", source_column_ids=[a_id], live=False))
    return dataset


class TestLiveFormulaColumnsAreReadOnly:
    """A live formula column is derived: change its source, not its values."""

    def test_cells_of_a_live_formula_column_are_not_editable(self, mock_app_context, formula_dataset):
        model = PandasTableModel(mock_app_context, formula_dataset)

        flags = model.flags(model.index(0, 1))

        assert not flags & Qt.ItemFlag.ItemIsEditable
        assert flags & Qt.ItemFlag.ItemIsSelectable  # still selectable and copyable
        assert flags & Qt.ItemFlag.ItemIsEnabled

    def test_plain_and_static_formula_cells_stay_editable(self, mock_app_context, formula_dataset):
        model = PandasTableModel(mock_app_context, formula_dataset)

        assert model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable
        assert model.flags(model.index(0, 2)) & Qt.ItemFlag.ItemIsEditable

    def test_set_data_on_a_live_formula_cell_is_rejected_without_a_command(self, mock_app_context, formula_dataset):
        mock_app_context.command_executor = Mock()
        model = PandasTableModel(mock_app_context, formula_dataset)

        assert model.setData(model.index(0, 1), "99") is False

        mock_app_context.command_executor.execute_command.assert_not_called()
        assert formula_dataset.data["b"].tolist() == [2.0, 4.0]

    def test_a_live_cell_explains_why_it_is_locked(self, mock_app_context, formula_dataset):
        model = PandasTableModel(mock_app_context, formula_dataset)

        tooltip = model.data(model.index(0, 1), Qt.ItemDataRole.ToolTipRole)

        assert "live formula" in tooltip
        assert "source" in tooltip

    def test_other_cells_have_no_tooltip(self, mock_app_context, formula_dataset):
        model = PandasTableModel(mock_app_context, formula_dataset)

        assert model.data(model.index(0, 0), Qt.ItemDataRole.ToolTipRole) is None
        assert model.data(model.index(0, 2), Qt.ItemDataRole.ToolTipRole) is None

    def test_the_live_header_tooltip_says_the_column_is_read_only(self, mock_app_context, formula_dataset):
        model = PandasTableModel(mock_app_context, formula_dataset)

        tooltip = model.headerData(1, Qt.Orientation.Horizontal, Qt.ItemDataRole.ToolTipRole)

        assert "read-only" in tooltip


class TestHeaderRefresh:
    def test_a_data_change_repaints_the_headers_of_the_affected_columns(self, mock_app_context, formula_dataset):
        """The "fx" / "fx live" marker is painted from the formula registry,
        which a replacing transform changes along with the column's values --
        so the header has to be told, not just the cells."""
        model = PandasTableModel(mock_app_context, formula_dataset)
        spy = QSignalSpy(model.headerDataChanged)

        model.on_dataset_changed({"start_index": (0, 1), "end_index": (1, 2)})

        assert spy.count() == 1
        orientation, first, last = spy.at(0)
        assert orientation == Qt.Orientation.Horizontal
        assert (first, last) == (1, 2)

    def test_a_single_cell_edit_repaints_that_columns_header(self, mock_app_context, formula_dataset):
        model = PandasTableModel(mock_app_context, formula_dataset)
        spy = QSignalSpy(model.headerDataChanged)

        model.on_dataset_changed({"start_index": (0, 0), "end_index": (0, 0)})

        assert spy.count() == 1
        assert tuple(spy.at(0)[1:]) == (0, 0)

    def test_the_cells_are_still_repainted(self, mock_app_context, formula_dataset):
        model = PandasTableModel(mock_app_context, formula_dataset)
        spy = QSignalSpy(model.dataChanged)

        model.on_dataset_changed({"start_index": (0, 1), "end_index": (1, 1)})

        assert spy.count() == 1


def test_rerunning_a_transform_as_a_formula_repaints_the_replaced_columns_header():
    """End to end through the real event bus: a replacing transform changes
    the registry (and the column's values), and the header must follow."""
    from pandaplot.commands.base_command import CommandResult
    from pandaplot.commands.project.dataset.transform_column_command import TransformColumnCommand
    from pandaplot.gui.components.tabs.dataset.pheader_view import formula_marker
    from pandaplot.models.events.event_bus import EventBus
    from pandaplot.models.project.project import Project

    event_bus = EventBus()
    project = Project(name="P")
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"a": [1.0, 2.0], "b": [0.0, 0.0]}))
    project.add_item(dataset)
    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = event_bus
    app_context = Mock(spec=AppContext)
    app_context.app_state = app_state
    app_context.get_app_state.return_value = app_state
    app_context.event_bus = event_bus
    model = PandasTableModel(app_context, dataset)
    spy = QSignalSpy(model.headerDataChanged)
    assert formula_marker(dataset, "b") == ""

    command = TransformColumnCommand(app_context, "ds-1", {
        "new_column_name": "b", "transform_type": "column", "source_columns": ["a"],
        "expression": "x * 2", "replace_existing": True, "as_formula": True,
    })
    assert command.execute() is CommandResult.SUCCESS

    assert formula_marker(dataset, "b") == "fx"
    repainted = [tuple(spy.at(i)[1:]) for i in range(spy.count())]
    assert any(first <= 1 <= last for first, last in repainted)

    spy = QSignalSpy(model.headerDataChanged)
    assert command.undo() is CommandResult.SUCCESS
    assert formula_marker(dataset, "b") == ""
    repainted = [tuple(spy.at(i)[1:]) for i in range(spy.count())]
    assert any(first <= 1 <= last for first, last in repainted)
    model.unsubscribe_all()
