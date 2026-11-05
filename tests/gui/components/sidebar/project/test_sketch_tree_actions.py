"""Project-tree actions for sketches: Add Sketch, opening, and dropping onto one."""
import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QTreeWidgetItem, QTreeWidgetItemIterator

from pandaplot.app import build_app_context
from pandaplot.gui.components.sidebar.project.project_view_panel import ProjectViewPanel
from pandaplot.models.events.event_types import UIEvents
from pandaplot.models.project import Project
from pandaplot.models.project.items import Folder, Note, Sketch


@pytest.fixture
def panel(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    app_context = build_app_context()
    project = Project(name="Tree")
    project.add_item(Folder(id="folder", name="Drawings"))
    project.add_item(Sketch(id="sketch", name="Diagram"), parent_id="folder")
    project.add_item(Note(id="note", name="Loose note"))
    panel = ProjectViewPanel(app_context=app_context)
    qtbot.addWidget(panel)
    app_context.get_app_state().load_project(project)
    return panel, project, app_context


def _tree_item(panel: ProjectViewPanel, item_id: str) -> QTreeWidgetItem:
    iterator = QTreeWidgetItemIterator(panel.tree)
    while iterator.value():
        tree_item = iterator.value()
        data = tree_item.data(0, Qt.ItemDataRole.UserRole)
        if data and data.get("id") == item_id:
            return tree_item
        iterator += 1
    raise AssertionError(f"no tree item for {item_id}")


def test_context_menu_offers_add_sketch(panel):
    tree_panel, _project, _context = panel

    assert tree_panel.context_menu.add_sketch_action.text() == "Add Sketch"


def test_add_sketch_creates_it_in_the_selected_folder(panel):
    tree_panel, project, _context = panel
    tree_panel.tree.setCurrentItem(_tree_item(tree_panel, "folder"))

    tree_panel.context_menu.add_sketch_action.trigger()

    folder = project.find_item("folder")
    assert isinstance(folder, Folder)
    created = [item for item in folder.get_items() if isinstance(item, Sketch) and item.id != "sketch"]
    assert [sketch.name for sketch in created] == ["New Sketch 2"]
    assert _tree_item(tree_panel, created[0].id).text(0) == "✏️ New Sketch 2"


def test_double_clicking_a_sketch_requests_its_tab(panel):
    tree_panel, _project, app_context = panel
    requests = []
    app_context.event_bus.subscribe(UIEvents.TAB_OPEN_REQUESTED, requests.append)

    sketch_row = _tree_item(tree_panel, "sketch")
    # A real double-click makes the row current before the handler runs.
    tree_panel.tree.setCurrentItem(sketch_row)

    tree_panel.command_manager.on_item_double_clicked(sketch_row, 0)

    assert [request["item_id"] for request in requests] == ["sketch"]


def test_dropping_onto_a_sketch_moves_the_item_into_the_sketchs_folder(qtbot, panel):
    tree_panel, project, _context = panel
    tree = tree_panel.tree
    tree.expandAll()
    tree_panel.resize(500, 600)
    tree_panel.show()
    qtbot.waitExposed(tree)
    tree.setCurrentItem(_tree_item(tree_panel, "note"))
    target = tree.visualItemRect(_tree_item(tree_panel, "sketch"))

    tree.dropEvent(QDropEvent(
        QPointF(target.center()), Qt.DropAction.MoveAction, QMimeData(), Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
    ))

    note = project.find_item("note")
    assert note is not None
    assert note.parent_id == "folder"
