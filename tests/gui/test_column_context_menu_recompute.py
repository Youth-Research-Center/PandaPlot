"""The column header context menu offers "Recompute formula column(s)" only for non-live formula columns (#154)."""

from unittest.mock import Mock

import pandas as pd
import pytest
from PySide6.QtWidgets import QWidget

from pandaplot.commands.project.dataset.recompute_formula_columns_command import RecomputeFormulaColumnsCommand
from pandaplot.gui.components.tabs.dataset.column_context_menu import ColumnHeaderContextMenu
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.formula_column import FormulaColumnSpec
from pandaplot.models.project.project import Project
from pandaplot.services.theme.theme_manager import ThemeManager

RECOMPUTE_TEXT = "Recompute formula column(s)"


@pytest.fixture
def setup(qtbot):
    project = Project(name="P")
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"a": [1.0, 2.0], "plain": [1.0, 2.0], "b": [2.0, 4.0], "live_c": [3.0, 5.0]}))
    project.add_item(dataset)
    a_id = dataset.column_id("a")
    dataset.set_formula_column(dataset.column_id("b"), FormulaColumnSpec(expression="x * 2", source_column_ids=[a_id]))
    dataset.set_formula_column(dataset.column_id("live_c"), FormulaColumnSpec(expression="x + 1", source_column_ids=[a_id], live=True))

    app_context = Mock()
    app_context.app_state.current_project = project
    app_context.get_manager.return_value = Mock(spec=ThemeManager)
    app_context.get_manager.return_value.build_context_menu_stylesheet.return_value = ""
    parent = QWidget()
    qtbot.addWidget(parent)
    return app_context, parent


def _texts(menu):
    return [action.text() for action in menu.actions()]


def _menu(setup, columns):
    app_context, parent = setup
    return ColumnHeaderContextMenu(app_context, parent, "ds-1", columns)


def test_offered_for_a_non_live_formula_column(setup):
    assert RECOMPUTE_TEXT in _texts(_menu(setup, [2]))


@pytest.mark.parametrize("columns", [[0], [1], [3]])
def test_hidden_for_plain_and_live_columns(setup, columns):
    assert RECOMPUTE_TEXT not in _texts(_menu(setup, columns))


def test_offered_when_any_selected_column_qualifies(setup):
    assert RECOMPUTE_TEXT in _texts(_menu(setup, [0, 3, 2]))


def test_triggering_executes_the_command_for_the_selection(setup):
    app_context, _ = setup
    menu = _menu(setup, [2])
    next(action for action in menu.actions() if action.text() == RECOMPUTE_TEXT).trigger()

    (command,), _ = app_context.command_executor.execute_command.call_args
    assert isinstance(command, RecomputeFormulaColumnsCommand)
    assert command.dataset_id == "ds-1"
    assert command.column_positions == [2]
