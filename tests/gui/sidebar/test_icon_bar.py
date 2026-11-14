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
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QPoint
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from pandaplot.gui.components.sidebar.icon_bar import IconBar
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.config import Theme
from tests.gui.icon_testing import assert_tinted, strongest_pixel
from tests.gui.theme_testing import design_tokens, surface_palette


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# Expected light-theme colours; each mock gets its own `design_tokens()` copy.
DESIGN_TOKENS = design_tokens()

# Sentinel icon colours far from every light-theme token, so a missed re-tint after the theme change cannot pass.
DARK_DESIGN_TOKENS = design_tokens(Theme.DARK, text_muted="#C0392B", accent_icon_active="#2ECC71")


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    ctx.get_manager.return_value.get_design_tokens.return_value = design_tokens()
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
    button_a = icon_bar.add_panel_button("panel_a", icon_name="folder")
    button_b = icon_bar.add_panel_button("panel_b", icon_name="table")

    icon_bar.set_active_button("panel_a")

    assert button_a.property("selected") is True
    assert button_b.property("selected") is False
    assert button_a.property("navActive") is True
    assert button_b.property("navActive") is False


def test_set_active_button_switches_between_buttons(icon_bar):
    button_a = icon_bar.add_panel_button("panel_a", icon_name="folder")
    button_b = icon_bar.add_panel_button("panel_b", icon_name="table")

    icon_bar.set_active_button("panel_a")
    icon_bar.set_active_button("panel_b")

    assert button_a.property("selected") is False
    assert button_b.property("selected") is True
    assert button_a.property("navActive") is False
    assert button_b.property("navActive") is True


def test_icon_only_buttons_have_accessible_names(icon_bar):
    button = icon_bar.add_panel_button("chart_properties", icon_name="chart-line")

    assert button.accessibleName() == "Chart Properties panel"
    assert button.toolTip() == "Chart Properties panel"
    assert icon_bar.settings_button.accessibleName() == "Settings"


def test_panel_button_label_uses_given_panel_title(icon_bar):
    button = icon_bar.add_panel_button("fit", label="Curve Fitting", icon_name="function")

    assert button.accessibleName() == "Curve Fitting panel"
    assert button.toolTip() == "Curve Fitting panel"


def test_sidebar_labels_panel_buttons_with_the_panel_title(app_context, qtbot):
    from PySide6.QtWidgets import QLabel

    from pandaplot.gui.components.sidebar.sidebar import CollapsibleSidebar

    app_context.get_manager.return_value.get_surface_palette.return_value = surface_palette()
    sidebar = CollapsibleSidebar(app_context=app_context, parent=None)
    qtbot.addWidget(sidebar)
    titled = QWidget()
    titled.title_label = QLabel("  Curve Fitting ")
    untitled = QWidget()

    sidebar.add_panel("fit", titled, icon_name="function")
    sidebar.add_panel("chart_properties", untitled, icon_name="chart-line")

    assert sidebar.icon_bar.panels["fit"].accessibleName() == "Curve Fitting panel"
    assert sidebar.icon_bar.panels["chart_properties"].accessibleName() == "Chart Properties panel"


def test_sidebar_does_not_strip_any_prefix_from_the_panel_title(app_context, qtbot):
    from PySide6.QtWidgets import QLabel

    from pandaplot.gui.components.sidebar.sidebar import CollapsibleSidebar

    app_context.get_manager.return_value.get_surface_palette.return_value = surface_palette()
    sidebar = CollapsibleSidebar(app_context=app_context, parent=None)
    qtbot.addWidget(sidebar)
    titled = QWidget()
    titled.title_label = QLabel("Fit Curve Fitting")

    sidebar.add_panel("fit", titled, icon_name="function")

    assert sidebar.icon_bar.panels["fit"].accessibleName() == "Fit Curve Fitting panel"


def test_panel_button_shows_a_bundled_icon_and_no_text(icon_bar):
    button = icon_bar.add_panel_button("fit", label="Curve Fitting", icon_name="function")

    assert button.text() == ""
    assert not button.icon().isNull()
    assert button.accessibleName() == "Curve Fitting panel"


def test_panel_button_requires_an_icon_name(icon_bar):
    with pytest.raises(TypeError):
        icon_bar.add_panel_button("panel_a")


def test_panel_button_takes_no_positional_icon_text(icon_bar):
    with pytest.raises(TypeError):
        icon_bar.add_panel_button("panel_a", "A", icon_name="folder")


def test_active_panel_button_icon_is_retinted_with_the_active_colour(icon_bar):
    button = icon_bar.add_panel_button("fit", icon_name="function")

    _assert_tinted(button, DESIGN_TOKENS["text_muted"])

    icon_bar.set_active_button("fit")

    _assert_tinted(button, DESIGN_TOKENS["accent_icon_active"])


def test_settings_button_uses_a_bundled_icon(icon_bar):
    assert icon_bar.settings_button.text() == ""
    assert not icon_bar.settings_button.icon().isNull()
    assert icon_bar.settings_button.accessibleName() == "Settings"


def _assert_tinted(button, expected_hex: str) -> None:
    assert_tinted(strongest_pixel(button.icon(), size=20), expected_hex)


def test_settings_button_gear_is_tinted_with_the_muted_text_colour(icon_bar):
    _assert_tinted(icon_bar.settings_button, DESIGN_TOKENS["text_muted"])


def test_theme_change_keeps_the_active_panel_state_and_retints_every_icon(icon_bar, app_context):
    active = icon_bar.add_panel_button("fit", icon_name="function")
    inactive = icon_bar.add_panel_button("explorer", icon_name="folder")
    icon_bar.set_active_button("fit")

    app_context.get_manager.return_value.get_design_tokens.return_value = dict(DARK_DESIGN_TOKENS)
    icon_bar._apply_theme()

    assert active.property("selected") is True
    assert active.property("navActive") is True
    assert inactive.property("selected") is False
    assert inactive.property("navActive") is False
    _assert_tinted(active, DARK_DESIGN_TOKENS["accent_icon_active"])
    _assert_tinted(inactive, DARK_DESIGN_TOKENS["text_muted"])
    _assert_tinted(icon_bar.settings_button, DARK_DESIGN_TOKENS["text_muted"])


def test_removing_the_active_panel_clears_the_stored_active_state(icon_bar):
    icon_bar.add_panel_button("fit", icon_name="function")
    icon_bar.set_active_button("fit")

    icon_bar.remove_panel_button("fit")
    readded = icon_bar.add_panel_button("fit", icon_name="function")
    icon_bar._apply_theme()

    assert readded.property("selected") is False
    assert readded.property("navActive") is False
    _assert_tinted(readded, DESIGN_TOKENS["text_muted"])


def test_sidebar_passes_icon_name_to_the_icon_bar(app_context, qtbot):
    from PySide6.QtWidgets import QLabel

    from pandaplot.gui.components.sidebar.sidebar import CollapsibleSidebar

    app_context.get_manager.return_value.get_surface_palette.return_value = surface_palette()
    sidebar = CollapsibleSidebar(app_context=app_context, parent=None)
    qtbot.addWidget(sidebar)
    titled = QWidget()
    titled.title_label = QLabel("Curve Fitting")

    sidebar.add_panel("fit", titled, icon_name="function")

    button = sidebar.icon_bar.panels["fit"]
    assert not button.icon().isNull()
    assert button.accessibleName() == "Curve Fitting panel"


def test_context_menu_is_deleted_after_closing(icon_bar, monkeypatch):
    opened: list[QMenu] = []

    def _make_nonblocking_menu(parent) -> QMenu:
        menu = QMenu(parent)
        opened.append(menu)
        menu.exec = lambda *_args: None
        return menu

    monkeypatch.setattr("pandaplot.gui.components.sidebar.icon_bar.QMenu", _make_nonblocking_menu)
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(5, 5), QPoint(5, 5))
    icon_bar.contextMenuEvent(event)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert len(opened) == 1
    assert not shiboken6.isValid(opened[0])
    assert icon_bar.findChildren(QMenu) == []
