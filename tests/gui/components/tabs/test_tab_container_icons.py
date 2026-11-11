"""TabContainer shows item-kind icons on tabs (docked, moved, popped out and re-docked) next to plain titles."""

import pytest
from PySide6.QtCore import QSize

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.tab_container import TabContainer
from pandaplot.gui.resources.item_icons import item_icon
from pandaplot.gui.resources.themed_icons import themed_icon
from pandaplot.models.project import Project
from pandaplot.models.project.items import Chart, Dataset, ImageGallery, Note, Sketch
from pandaplot.services.theme import ThemeManager
from tests.gui.icon_testing import assert_tinted, strongest_pixel

ICON_SIZE = QSize(16, 16)

ITEMS = [
    ("dataset", "dataset", "Sales"),
    ("chart", "chart", "Trend"),
    ("note", "note", "Notes"),
    ("sketch", "sketch", "Diagram"),
    ("gallery", "imagegallery", "Album"),
]


def _same_pixels(first, second) -> bool:
    return first.pixmap(ICON_SIZE).toImage() == second.pixmap(ICON_SIZE).toImage()


@pytest.fixture
def context():
    app_context = build_app_context()
    project = Project(name="Tabs")
    project.add_item(Dataset(id="dataset", name="Sales"))
    project.add_item(Chart(id="chart", name="Trend"))
    project.add_item(Note(id="note", name="Notes"))
    project.add_item(Sketch(id="sketch", name="Diagram"))
    project.add_item(ImageGallery(id="gallery", name="Album"))
    app_context.get_app_state().load_project(project)
    return app_context


@pytest.fixture
def container(qtbot, context, monkeypatch):
    # Opening tabs would otherwise write the tab session into the user's real config file.
    monkeypatch.setattr(TabContainer, "_persist_tab_session", lambda _self: None)
    tab_container = TabContainer(context, parent=None)
    qtbot.addWidget(tab_container)
    return tab_container


def _green_icons(context, monkeypatch) -> None:
    manager = context.get_manager(ThemeManager)
    real_tokens = manager.get_design_tokens()
    monkeypatch.setattr(manager, "get_design_tokens", lambda: {**real_tokens, "text_primary": "#00AA00"})


@pytest.mark.parametrize(("item_id", "item_type", "name"), ITEMS)
def test_opening_an_item_adds_a_tab_with_its_icon_and_plain_title(container, context, item_id, item_type, name):
    container.open_tab(item_id)

    pane = container.panes[0]
    index = pane.indexOf(container.get_tab_widget(item_id))
    assert pane.tabText(index) == name
    assert _same_pixels(pane.tabIcon(index), item_icon(context, item_type))


def test_the_note_tab_keeps_its_unsaved_marker_without_an_emoji(container, context):
    container.open_tab("note")
    note_tab = container.get_tab_widget("note")

    note_tab.note_editor.has_unsaved_changes = lambda: True

    assert note_tab.get_tab_title() == "Notes *"


def test_the_welcome_tab_has_the_house_icon_and_a_plain_title(qtbot, monkeypatch):
    app_context = build_app_context()
    monkeypatch.setattr(TabContainer, "_persist_tab_session", lambda _self: None)
    tab_container = TabContainer(app_context, parent=None)
    qtbot.addWidget(tab_container)

    pane = tab_container.panes[0]
    assert pane.count() == 1
    assert pane.tabText(0) == "Welcome"
    assert _same_pixels(pane.tabIcon(0), themed_icon(app_context, "house"))


def test_moving_a_tab_to_the_other_pane_keeps_its_icon(container, context):
    container.open_tab("dataset")
    container.open_tab("chart")
    chart_widget = container.get_tab_widget("chart")
    source = container._pane_of(chart_widget)

    container._handle_split(source, source.indexOf(chart_widget))

    target = container._pane_of(chart_widget)
    assert target is not source
    index = target.indexOf(chart_widget)
    assert target.tabText(index) == "Trend"
    assert _same_pixels(target.tabIcon(index), item_icon(context, "chart"))


def test_a_popped_out_tab_gives_its_window_the_icon_and_redocking_restores_the_tab_icon(container, context):
    container.open_tab("dataset")
    container.open_tab("chart")
    pane = container.panes[0]
    chart_widget = container.get_tab_widget("chart")

    container.popout_tab(pane, pane.indexOf(chart_widget))

    window = container.floating_windows["chart"]
    assert window.windowTitle() == "Trend"
    assert _same_pixels(window.windowIcon(), item_icon(context, "chart"))

    container.redock_tab("chart")

    target = container._pane_of(chart_widget)
    index = target.indexOf(chart_widget)
    assert target.tabText(index) == "Trend"
    assert _same_pixels(target.tabIcon(index), item_icon(context, "chart"))


def test_apply_theme_retints_the_tab_icons(container, context, monkeypatch):
    container.open_tab("dataset")
    container.open_tab("note")
    _green_icons(context, monkeypatch)

    container._apply_theme()

    pane = container.panes[0]
    for index in range(pane.count()):
        assert_tinted(strongest_pixel(pane.tabIcon(index)), "#00AA00")


def test_apply_theme_retints_the_floating_window_icon(container, context, monkeypatch):
    container.open_tab("dataset")
    container.open_tab("chart")
    pane = container.panes[0]
    container.popout_tab(pane, pane.indexOf(container.get_tab_widget("chart")))
    window = container.floating_windows["chart"]
    _green_icons(context, monkeypatch)

    window._apply_theme()

    assert_tinted(strongest_pixel(window.windowIcon()), "#00AA00")
