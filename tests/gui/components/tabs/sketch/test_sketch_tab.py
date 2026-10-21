"""Tests for SketchTab: creation through the tab factory and redrawing on change."""
import logging

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from pandaplot.app import build_app_context, create_tab_factory
from pandaplot.commands.project.sketch import AddSketchElementCommand
from pandaplot.gui.components.tabs.sketch.sketch_tab import SketchTab
from pandaplot.gui.core.widget_extension import unsubscribe_widget_tree
from pandaplot.models.events import ProjectEvents, SketchEvents
from pandaplot.models.events.event_data import SketchChangedData
from pandaplot.models.events.event_types import ThemeEvents
from pandaplot.models.project import Project
from pandaplot.models.project.items.sketch import LineElement, Sketch, SketchLayer
from pandaplot.services.theme.theme_manager import ThemeManager


class _Container(QWidget):
    """Stands in for TabContainer: records title updates from its child tab."""

    def __init__(self):
        super().__init__()
        self.titles: list[str] = []

    def update_tab_title(self, _widget: QWidget, new_title: str) -> None:
        self.titles.append(new_title)


@pytest.fixture
def app_context(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return build_app_context()


@pytest.fixture
def sketch(app_context) -> Sketch:
    sketch = Sketch(id="sketch-1", name="Diagram", layers=[SketchLayer(id="layer")])
    project = Project(name="Tabs")
    project.add_item(sketch)
    app_context.get_app_state().load_project(project)
    return sketch


@pytest.fixture
def container(qtbot):
    # qtbot only holds a weak reference, so the fixture keeps the container
    # (and the tab it parents) alive for the whole test.
    container = _Container()
    qtbot.addWidget(container)
    return container


@pytest.fixture
def tab(app_context, sketch, container):
    tab = create_tab_factory().create_tab(app_context, sketch, parent=container)
    assert isinstance(tab, SketchTab)
    return tab


def test_tab_identifies_its_sketch(tab):
    assert tab.get_tab_title() == "✏️ Diagram"
    assert tab.get_tab_data() == {"type": "sketch", "id": "sketch-1"}


def test_a_drawing_command_redraws_the_canvas_and_undo_redraws_again(app_context, sketch, tab):
    executor = app_context.get_command_executor()

    executor.execute_command(AddSketchElementCommand(app_context, sketch, "layer", LineElement(id="line", dx=10.0)))
    assert tab.canvas.element_item("line") is not None

    executor.undo()
    assert tab.canvas.element_item("line") is None


def test_changes_to_another_sketch_do_not_redraw(app_context, sketch, tab):
    sketch.add_element("layer", LineElement(id="unannounced"))

    app_context.event_bus.emit(SketchEvents.SKETCH_CHANGED, SketchChangedData(sketch_id="other").to_dict())

    assert tab.canvas.element_item("unannounced") is None


def test_renaming_the_sketch_updates_the_tab_title(app_context, sketch, tab, container):
    sketch.update_name("Circuit")

    app_context.event_bus.emit(ProjectEvents.PROJECT_ITEM_RENAMED, {"item_id": "sketch-1", "new_name": "Circuit"})

    assert container.titles == ["✏️ Circuit"]


def test_renaming_another_item_leaves_the_title_alone(app_context, tab, container):
    app_context.event_bus.emit(ProjectEvents.PROJECT_ITEM_RENAMED, {"item_id": "other", "new_name": "X"})

    assert container.titles == []


def test_first_show_fits_the_canvas(qtbot, tab, container):
    container.resize(400, 300)
    tab.resize(400, 300)
    container.show()
    qtbot.waitExposed(tab)

    visible = tab.canvas.mapToScene(tab.canvas.viewport().rect()).boundingRect()
    assert visible.contains(tab.canvas.sceneRect().adjusted(1.0, 1.0, -1.0, -1.0))


def test_closing_the_tab_like_tab_container_leaves_no_live_subscriptions(qtbot, caplog, app_context, sketch, tab):
    """EventBus swallows callback exceptions, so check the log: a tab that
    kept a subscription would log 'Internal C++ object already deleted'."""
    # TabContainer._handle_close unsubscribes the whole widget tree before
    # deleteLater(), because the destroyed signal arrives too late.
    unsubscribe_widget_tree(tab)
    tab.setParent(None)
    tab.deleteLater()
    qtbot.wait(10)

    with caplog.at_level(logging.ERROR):
        app_context.event_bus.emit(SketchEvents.SKETCH_CHANGED, SketchChangedData(sketch_id=sketch.id).to_dict())
        app_context.event_bus.emit(ProjectEvents.PROJECT_ITEM_RENAMED, {"item_id": sketch.id, "new_name": "X"})

    assert [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR] == []


def test_frame_colours_follow_the_theme(app_context, tab, monkeypatch):
    theme_manager = app_context.get_manager(ThemeManager)
    light = theme_manager.get_design_tokens()
    assert tab.canvas._surround_color == QColor(light["border_panel"])

    dark = {**light, "border_panel": "#3A3D40", "border_control": "#4A4D52"}
    monkeypatch.setattr(theme_manager, "get_design_tokens", lambda: dark)
    app_context.event_bus.emit(ThemeEvents.THEME_CHANGED, {})

    assert tab.canvas._surround_color == QColor("#3A3D40")
    assert tab.canvas._paper_border_color == QColor("#4A4D52")
