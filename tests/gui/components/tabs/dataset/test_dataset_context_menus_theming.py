"""These context menus used to hardcode a light-mode-only stylesheet
(#ffffff/#0078d4/#e5f3ff) that never reacted to the app theme -- a real
dark-mode bug (issue #214). They must now render from ThemeManager's shared
build_context_menu_stylesheet()."""
import sys
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.tabs.dataset.cell_context_menu import CellContextMenu
from pandaplot.gui.components.tabs.dataset.column_context_menu import ColumnHeaderContextMenu
from pandaplot.gui.components.tabs.dataset.row_context_menu import RowHeaderContextMenu
from pandaplot.services.theme.theme_manager import ThemeManager

# The menu icons are tinted from these design tokens.
ICON_TOKENS = {"text_primary": "#1C1E26", "text_muted": "#6B7280", "accent_icon_active": "#404BAC", "text_disabled": "#AEB2BC"}


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _app_context_with_theme():
    theme_manager = Mock(spec=ThemeManager)
    theme_manager.build_context_menu_stylesheet.return_value = "QMenu { background-color: #2A2C2E; }"
    theme_manager.get_design_tokens.return_value = dict(ICON_TOKENS)
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
