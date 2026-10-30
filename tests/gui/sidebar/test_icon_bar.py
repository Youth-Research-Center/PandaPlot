"""Regression tests for IconBar's active-panel-button indicator.

IconBar.set_active_button drives the sidebar's "which panel is open" nav
indicator via the shared [segment="true"][selected="true"] QSS rule (see
_apply_button_theme). Before this test, nothing exercised
set_active_button/add_panel_button, so a regression in the active/inactive
bookkeeping (e.g. marking every button selected, or failing to clear the
previous selection) would have gone unnoticed.
"""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QWidget

from pandaplot.gui.components.sidebar.icon_bar import IconBar
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
def icon_bar(app_context):
    parent = QWidget()
    bar = IconBar(app_context, parent)
    # Keep the parent alive for the fixture's lifetime: without a Python
    # reference, the QWidget parent can be garbage-collected out from under
    # the underlying C++ layout, deleting IconBar's button_layout with it.
    bar._test_parent = parent
    return bar


def test_set_active_button_marks_only_the_named_button_selected(icon_bar):
    button_a = icon_bar.add_panel_button("panel_a", "A")
    button_b = icon_bar.add_panel_button("panel_b", "B")

    icon_bar.set_active_button("panel_a")

    assert button_a.property("selected") is True
    assert button_b.property("selected") is False
    assert button_a.property("navActive") is True
    assert button_b.property("navActive") is False


def test_set_active_button_switches_between_buttons(icon_bar):
    button_a = icon_bar.add_panel_button("panel_a", "A")
    button_b = icon_bar.add_panel_button("panel_b", "B")

    icon_bar.set_active_button("panel_a")
    icon_bar.set_active_button("panel_b")

    assert button_a.property("selected") is False
    assert button_b.property("selected") is True
    assert button_a.property("navActive") is False
    assert button_b.property("navActive") is True


def test_icon_only_buttons_have_accessible_names(icon_bar):
    button = icon_bar.add_panel_button("chart_properties", "📈")

    assert button.accessibleName() == "Chart Properties panel"
    assert button.toolTip() == "Chart Properties panel"
    assert icon_bar.settings_button.accessibleName() == "Settings"
