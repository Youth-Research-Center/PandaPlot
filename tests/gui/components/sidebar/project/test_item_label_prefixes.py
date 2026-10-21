"""Regression tests: item-type prefixes in tree labels survive inline rename.

Before the shared prefix map, the rename paths only knew the folder, note,
dataset and chart prefixes and cut them off by slicing two characters. A
gallery renamed inline kept its "🖼️ " in the new name, and a rename that was
rejected restored every other type with the chart prefix.
"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStyleOptionViewItem, QTreeWidget, QTreeWidgetItem, QTreeWidgetItemIterator

from pandaplot.app import build_app_context
from pandaplot.gui.components.sidebar.project.item_name_delegate import ItemNameDelegate
from pandaplot.gui.components.sidebar.project.project_view_panel import ProjectViewPanel
from pandaplot.models.project import Project
from pandaplot.models.project.items import Folder, ImageGallery, Note, Sketch


@pytest.fixture
def tree_with_gallery(qtbot):
    tree = QTreeWidget()
    qtbot.addWidget(tree)
    item = QTreeWidgetItem(["🖼️ Album"])
    item.setData(0, Qt.ItemDataRole.UserRole, {"type": "imagegallery", "id": "g"})
    tree.addTopLevelItem(item)
    return tree, item


def test_delegate_editor_shows_the_name_without_a_multi_character_prefix(tree_with_gallery):
    tree, item = tree_with_gallery
    delegate = ItemNameDelegate()

    editor = delegate.createEditor(tree.viewport(), QStyleOptionViewItem(), tree.indexFromItem(item))

    assert editor.text() == "Album"


def test_delegate_keeps_the_prefix_of_the_item_type_after_rename(tree_with_gallery):
    tree, item = tree_with_gallery
    delegate = ItemNameDelegate()
    editor = delegate.createEditor(tree.viewport(), QStyleOptionViewItem(), tree.indexFromItem(item))
    editor.setText("Holiday")

    delegate.setModelData(editor, tree.model(), tree.indexFromItem(item))

    assert item.text(0) == "🖼️ Holiday"


@pytest.fixture
def panel(qtbot, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    app_context = build_app_context()
    project = Project(name="Labels")
    project.add_item(ImageGallery(id="gallery", name="Album"))
    project.add_item(Sketch(id="sketch", name="Diagram"))
    project.add_item(Note(id="note", name="Notes"))
    project.add_item(Folder(id="folder", name="Empty"))
    panel = ProjectViewPanel(app_context=app_context)
    qtbot.addWidget(panel)
    # Loading emits PROJECT_LOADED, which is how the panel fills its tree.
    app_context.get_app_state().load_project(project)
    return panel, project


def _tree_item(panel: ProjectViewPanel, item_id: str) -> QTreeWidgetItem:
    iterator = QTreeWidgetItemIterator(panel.tree)
    while iterator.value():
        tree_item = iterator.value()
        data = tree_item.data(0, Qt.ItemDataRole.UserRole)
        if data and data.get("id") == item_id:
            return tree_item
        iterator += 1
    raise AssertionError(f"no tree item for {item_id}")


@pytest.mark.parametrize(("item_id", "label"), [("gallery", "🖼️ Album"), ("sketch", "✏️ Diagram"), ("note", "📝 Notes")])
def test_tree_labels_use_the_item_type_prefix(panel, item_id, label):
    tree_panel, _project = panel

    assert _tree_item(tree_panel, item_id).text(0) == label


def test_inline_rename_of_a_gallery_does_not_put_the_prefix_in_its_name(panel):
    tree_panel, project = panel

    _tree_item(tree_panel, "gallery").setText(0, "🖼️ Holiday")

    assert project.find_item("gallery").name == "Holiday"


# An empty gallery or folder is falsy (ItemCollection defines __len__), which
# once made a rejected rename blank its label.
@pytest.mark.parametrize(("item_id", "label"), [("sketch", "✏️ Diagram"), ("gallery", "🖼️ Album"), ("folder", "📁 Empty")])
def test_rejected_rename_restores_the_item_types_own_prefix(panel, item_id, label):
    tree_panel, _project = panel
    tree_item = _tree_item(tree_panel, item_id)

    tree_item.setText(0, "   ")

    assert tree_item.text(0) == label
