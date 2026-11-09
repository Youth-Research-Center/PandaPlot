"""The dataset cell, column and row context menus show theme-tinted bundled icons next to their text labels."""

import re
from unittest.mock import Mock

import pandas as pd
import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QMenu

from pandaplot.gui.components.tabs.dataset.cell_context_menu import CellContextMenu
from pandaplot.gui.components.tabs.dataset.column_context_menu import ColumnHeaderContextMenu
from pandaplot.gui.components.tabs.dataset.row_context_menu import RowHeaderContextMenu
from pandaplot.gui.resources.icon_library import build_icon
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.formula_column import FormulaColumnSpec
from pandaplot.models.project.project import Project
from pandaplot.services.theme.theme_manager import ThemeManager

TOKENS = {
    "text_primary": "#1C1E26",
    "text_muted": "#6B7280",
    "accent_icon_active": "#404BAC",
    "text_disabled": "#AEB2BC",
    "text_on_accent": "#FFFFFF",
}
ICON_SIZE = 16
NON_ASCII = re.compile(r"[^\x00-\x7f]")

CELL_ICONS = {
    "Add row(s) below": "rows-plus-bottom",
    "Add row(s) above": "rows-plus-top",
    "Add column(s) to the right": "columns-plus-right",
    "Add column(s) to the left": "columns-plus-left",
    "Delete selected rows": "trash",
    "Delete selected columns": "trash",
}
ROW_ICONS = {
    "Add row(s) above": "rows-plus-top",
    "Add row(s) below": "rows-plus-bottom",
    "Delete selected row(s)": "trash",
}
COLUMN_ICONS = {
    "Add column(s) to the left": "columns-plus-left",
    "Add column(s) to the right": "columns-plus-right",
    "Rename column...": "textbox",
    "Change Data Type": "table",
    "Recompute formula column(s)": "arrows-clockwise",
    "Delete selected column(s)": "trash",
}
DTYPE_LABELS = {"Text/String", "Integer", "Decimal", "True/False", "Date/Time"}


@pytest.fixture
def app_context() -> Mock:
    project = Project(name="P")
    dataset = Dataset(id="ds1", name="Data", data=pd.DataFrame({"a": [1.0, 2.0], "b": [2.0, 4.0]}))
    project.add_item(dataset)
    dataset.set_formula_column(dataset.column_id("b"), FormulaColumnSpec(expression="x * 2", source_column_ids=[dataset.column_id("a")]))

    theme_manager = Mock(spec=ThemeManager)
    theme_manager.build_context_menu_stylesheet.return_value = ""
    theme_manager.get_design_tokens.return_value = dict(TOKENS)
    context = Mock()
    context.get_manager.return_value = theme_manager
    context.app_state.current_project = project
    return context


def _pixels(icon):
    return icon.pixmap(QSize(ICON_SIZE, ICON_SIZE)).toImage()


def _labelled_actions(menu: QMenu):
    return [action for action in menu.actions() if not action.isSeparator()]


def _assert_icons(menu: QMenu, expected_icons: dict[str, str]) -> None:
    actions = _labelled_actions(menu)
    assert {action.text() for action in actions} == set(expected_icons)
    for action in actions:
        assert NON_ASCII.search(action.text()) is None, f"{action.text()} contains emoji or non-ASCII text"
        expected = build_icon(expected_icons[action.text()], TOKENS["text_primary"], size=ICON_SIZE, disabled_color=TOKENS["text_disabled"])
        assert _pixels(action.icon()) == _pixels(expected), f"{action.text()} uses the wrong icon"


def test_cell_context_menu_icons(qapp, app_context):
    _assert_icons(CellContextMenu(app_context, None, dataset_id="ds1", indexes=[]), CELL_ICONS)


def test_row_context_menu_icons(qapp, app_context):
    _assert_icons(RowHeaderContextMenu(app_context, None, dataset_id="ds1", row_indices=[0]), ROW_ICONS)


def test_column_context_menu_icons(qapp, app_context):
    # Column 1 is a non-live formula column, so every optional entry is present.
    _assert_icons(ColumnHeaderContextMenu(app_context, None, dataset_id="ds1", column_indices=[1]), COLUMN_ICONS)


def test_column_context_menu_data_type_options_are_plain_text_choices(qapp, app_context):
    menu = ColumnHeaderContextMenu(app_context, None, dataset_id="ds1", column_indices=[1])
    dtype_menu = next(action.menu() for action in menu.actions() if action.text() == "Change Data Type")

    assert {action.text() for action in dtype_menu.actions()} == DTYPE_LABELS
    assert all(action.icon().isNull() for action in dtype_menu.actions())


def _strongest(icon: QIcon, mode: QIcon.Mode) -> QColor:
    image = icon.pixmap(QSize(32, 32), mode).toImage()
    pixels = (image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height()))
    return max(pixels, key=lambda pixel: pixel.alpha())


def _assert_hover_icons_are_on_accent(menu: QMenu) -> None:
    actions = [action for action in _labelled_actions(menu) if not action.icon().isNull()]
    assert actions
    for action in actions:
        active = _strongest(action.icon(), QIcon.Mode.Active)
        normal = _strongest(action.icon(), QIcon.Mode.Normal)
        assert (active.red(), active.green(), active.blue()) == (255, 255, 255), action.text()
        assert abs(normal.red() - 0x1C) < 12 and abs(normal.blue() - 0x26) < 12, action.text()


def test_cell_context_menu_hover_icons_are_readable_on_the_accent(qapp, app_context):
    _assert_hover_icons_are_on_accent(CellContextMenu(app_context, None, dataset_id="ds1", indexes=[]))


def test_row_context_menu_hover_icons_are_readable_on_the_accent(qapp, app_context):
    _assert_hover_icons_are_on_accent(RowHeaderContextMenu(app_context, None, dataset_id="ds1", row_indices=[0]))


def test_column_context_menu_hover_icons_are_readable_on_the_accent(qapp, app_context):
    _assert_hover_icons_are_on_accent(ColumnHeaderContextMenu(app_context, None, dataset_id="ds1", column_indices=[1]))
