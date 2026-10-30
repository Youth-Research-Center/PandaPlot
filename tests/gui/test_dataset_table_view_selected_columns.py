"""Tests for DatasetTableView.get_selected_column_ids.

This is the single shared implementation of "which columns has the user
selected?", relied on by all three chart-creation entry points (dataset tab
button, project-tree context menu, wizard column picker).
"""
from unittest.mock import Mock

import pandas as pd
import pytest
from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.tabs.dataset.dataset_table_view import DatasetTableView
from pandaplot.gui.components.tabs.dataset.pandas_table_model import PandasTableModel
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    return ctx


@pytest.fixture
def table_view(app_context):
    data = pd.DataFrame({"Date": [1, 2, 3], "Revenue": [4, 5, 6], "Cost": [7, 8, 9]})
    dataset = Dataset(id="ds-1", name="Sales", data=data)
    model = PandasTableModel(app_context, dataset)
    view = DatasetTableView(app_context, model)
    return view, dataset


def _select_columns(view, columns: list[int]):
    selection_model = view.selectionModel()
    selection_model.clearSelection()
    for column in columns:
        selection_model.select(
            view.model().index(0, column),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Columns,
        )


def test_no_selection_returns_empty_list(table_view):
    view, _ = table_view

    assert view.get_selected_column_ids() == []


def test_single_selected_column_returns_its_stable_id(table_view):
    view, dataset = table_view

    _select_columns(view, [1])

    assert view.get_selected_column_ids() == [dataset.column_id("Revenue")]


def test_multiple_selected_columns_are_returned_in_column_order(table_view):
    view, dataset = table_view

    # Selected out of order on purpose; the result must follow column order.
    _select_columns(view, [2, 0])

    assert view.get_selected_column_ids() == [
        dataset.column_id("Date"),
        dataset.column_id("Cost"),
    ]


def test_columns_without_a_stable_id_are_excluded(table_view, caplog):
    view, dataset = table_view
    real_column_id = dataset.column_id

    def _unresolvable_date(name):
        return None if name == "Date" else real_column_id(name)

    dataset.column_id = _unresolvable_date
    _select_columns(view, [0, 1])

    with caplog.at_level("WARNING"):
        ids = view.get_selected_column_ids()

    assert ids == [real_column_id("Revenue")]
    assert any("Date" in record.getMessage() for record in caplog.records)


def test_paste_keeps_blank_lines_in_place_and_strips_crlf():
    """A spreadsheet copy uses CRLF line endings and can contain blank rows.
    The blank row must still occupy its row (later rows must not shift up)
    as an empty row as wide as the block (EditBatchCommand rejects ragged
    rows), and the "\\r" must not leak into the last cell of each row."""
    from pandaplot.commands.project.dataset.edit_batch_command import EditBatchCommand

    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    ctx.command_executor = Mock()
    data = pd.DataFrame({"a": ["x", "y", "z"], "b": ["p", "q", "r"]}, dtype=object)
    dataset = Dataset(id="ds-paste", name="Paste", data=data)
    view = DatasetTableView(ctx, PandasTableModel(ctx, dataset))
    view.selectionModel().select(view.model().index(0, 0), QItemSelectionModel.SelectionFlag.ClearAndSelect)
    QApplication.clipboard().setText("1\t2\r\n\r\n3\t4\r\n")

    view.pasteSelection()

    command = ctx.command_executor.execute_command.call_args.args[0]
    assert isinstance(command, EditBatchCommand)
    assert command.new_data == [["1", "2"], ["", ""], ["3", "4"]]
