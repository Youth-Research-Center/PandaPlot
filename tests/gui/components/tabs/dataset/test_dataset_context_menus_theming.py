"""These context menus used to hardcode a light-mode-only stylesheet
(#ffffff/#0078d4/#e5f3ff) that never reacted to the app theme -- a real
dark-mode bug (issue #214). They must now render from ThemeManager's shared
build_context_menu_stylesheet()."""
import sys
from unittest.mock import Mock, patch

import pandas as pd
import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QItemSelectionModel, QPoint
from PySide6.QtWidgets import QApplication, QMenu

from pandaplot.gui.components.tabs.dataset.cell_context_menu import CellContextMenu
from pandaplot.gui.components.tabs.dataset.column_context_menu import ColumnHeaderContextMenu
from pandaplot.gui.components.tabs.dataset.dataset_table_view import DatasetTableView
from pandaplot.gui.components.tabs.dataset.pandas_table_model import PandasTableModel
from pandaplot.gui.components.tabs.dataset.row_context_menu import RowHeaderContextMenu
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.services.theme.theme_manager import ThemeManager


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _app_context_with_theme():
    theme_manager = Mock(spec=ThemeManager)
    theme_manager.build_context_menu_stylesheet.return_value = "QMenu { background-color: #2A2C2E; }"
    app_context = Mock()
    app_context.get_manager.return_value = theme_manager
    app_context.command_executor = Mock()
    return app_context, theme_manager


def test_cell_context_menu_uses_theme_manager_stylesheet():
    app_context, theme_manager = _app_context_with_theme()
    menu = CellContextMenu(app_context, None, dataset_id="ds1", indexes=[])
    theme_manager.build_context_menu_stylesheet.assert_called_once()
    assert menu.styleSheet() == "QMenu { background-color: #2A2C2E; }"


def test_column_context_menu_uses_theme_manager_stylesheet():
    app_context, theme_manager = _app_context_with_theme()
    menu = ColumnHeaderContextMenu(app_context, None, dataset_id="ds1", column_indices=[0])
    theme_manager.build_context_menu_stylesheet.assert_called_once()
    assert menu.styleSheet() == "QMenu { background-color: #2A2C2E; }"


def test_row_context_menu_uses_theme_manager_stylesheet():
    app_context, theme_manager = _app_context_with_theme()
    menu = RowHeaderContextMenu(app_context, None, dataset_id="ds1", row_indices=[0])
    theme_manager.build_context_menu_stylesheet.assert_called_once()
    assert menu.styleSheet() == "QMenu { background-color: #2A2C2E; }"


def _make_dataset_table_view() -> DatasetTableView:
    app_context, _ = _app_context_with_theme()
    app_context.event_bus = Mock()
    app_context.app_state.current_project = None
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"A": [1, 2], "B": [3, 4]}))
    model = PandasTableModel(app_context, dataset)
    return DatasetTableView(app_context, model)


def test_cell_context_menu_is_deleted_after_closing():
    view = _make_dataset_table_view()
    view.selectionModel().select(
        view.model().index(0, 0),
        QItemSelectionModel.SelectionFlag.ClearAndSelect,
    )
    opened: list[CellContextMenu] = []

    def _exec_returns_immediately(menu: CellContextMenu, *_args) -> None:
        opened.append(menu)

    with patch.object(CellContextMenu, "exec", _exec_returns_immediately):
        view.openMenu(QPoint(5, 5))
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert len(opened) == 1
    assert not shiboken6.isValid(opened[0])
    assert view.findChildren(QMenu) == []


def test_column_header_context_menu_is_deleted_after_closing():
    view = _make_dataset_table_view()
    opened: list[ColumnHeaderContextMenu] = []

    def _exec_returns_immediately(menu: ColumnHeaderContextMenu, *_args) -> None:
        opened.append(menu)

    with (
        patch.object(view.horizontalHeader(), "logicalIndexAt", return_value=0),
        patch.object(ColumnHeaderContextMenu, "exec", _exec_returns_immediately),
    ):
        view._on_column_header_context_menu(QPoint(5, 5))
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert len(opened) == 1
    assert not shiboken6.isValid(opened[0])
    assert view.findChildren(QMenu) == []


def test_row_header_context_menu_is_deleted_after_closing():
    view = _make_dataset_table_view()
    opened: list[RowHeaderContextMenu] = []

    def _exec_returns_immediately(menu: RowHeaderContextMenu, *_args) -> None:
        opened.append(menu)

    with (
        patch.object(view.verticalHeader(), "logicalIndexAt", return_value=0),
        patch.object(RowHeaderContextMenu, "exec", _exec_returns_immediately),
    ):
        view._on_row_header_context_menu(QPoint(5, 5))
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert len(opened) == 1
    assert not shiboken6.isValid(opened[0])
    assert view.findChildren(QMenu) == []
