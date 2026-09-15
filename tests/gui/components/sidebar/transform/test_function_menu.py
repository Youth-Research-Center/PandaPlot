"""Tests for the shared "Insert function" menu builder."""
import pytest
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from pandaplot.gui.components.sidebar.transform.function_menu import build_function_menu


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def templates():
    return {
        "Math": [
            {"name": "Double", "description": "Double the values", "code": "x * 2"},
            {"name": "Square root", "description": "Square root", "code": "np.sqrt(x)"},
        ],
        "Stats": [
            {"name": "Z-score", "description": "Standardize", "code": "(x - x.mean()) / x.std()"},
        ],
    }


def test_builds_one_submenu_per_category(templates):
    parent = QWidget()
    menu = build_function_menu(parent, templates, on_insert=lambda code: None)

    submenu_titles = [action.menu().title() for action in menu.actions() if action.menu()]
    assert submenu_titles == ["Math", "Stats"]


def test_builds_one_action_per_template_entry(templates):
    parent = QWidget()
    menu = build_function_menu(parent, templates, on_insert=lambda code: None)

    # Materialize actions list to work with PySide6's memory management
    actions = list(menu.actions())
    math_menu = next(a.menu() for a in actions if a.menu() and a.menu().title() == "Math")
    action_texts = [a.text() for a in math_menu.actions()]
    assert action_texts == ["Double", "Square root"]


def test_action_tooltip_shows_description_and_code(templates):
    parent = QWidget()
    menu = build_function_menu(parent, templates, on_insert=lambda code: None)

    # Materialize actions list to work with PySide6's memory management
    actions = list(menu.actions())
    math_menu = next(a.menu() for a in actions if a.menu() and a.menu().title() == "Math")
    double_action = next(a for a in math_menu.actions() if a.text() == "Double")
    assert double_action.toolTip() == "Double the values  →  x * 2"


def test_triggering_an_action_calls_on_insert_with_its_code(templates):
    parent = QWidget()
    inserted = []
    menu = build_function_menu(parent, templates, on_insert=inserted.append)

    # Materialize actions list to work with PySide6's memory management
    actions = list(menu.actions())
    math_menu = next(a.menu() for a in actions if a.menu() and a.menu().title() == "Math")
    double_action = next(a for a in math_menu.actions() if a.text() == "Double")
    double_action.trigger()

    assert inserted == ["x * 2"]


def test_menu_shows_tooltips(templates):
    parent = QWidget()
    menu = build_function_menu(parent, templates, on_insert=lambda code: None)

    assert isinstance(menu, QMenu)
    assert menu.toolTipsVisible() is True
