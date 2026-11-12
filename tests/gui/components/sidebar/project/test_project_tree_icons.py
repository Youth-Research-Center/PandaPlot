"""The project tree shows an icon for each item kind and plain item names instead of emoji-prefixed labels."""

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QStyledItemDelegate, QTreeWidgetItem, QTreeWidgetItemIterator

from pandaplot.app import build_app_context
from pandaplot.gui.components.sidebar.project.project_view_panel import ProjectViewPanel
from pandaplot.gui.resources import icon_library
from pandaplot.gui.resources.item_icons import item_icon
from pandaplot.models.project import Project
from pandaplot.models.project.items import Chart, Dataset, Folder, Image, ImageGallery, ItemCollection, Note, Sketch
from pandaplot.services.theme import ThemeManager
from tests.gui.icon_testing import assert_tinted, hovered_selected_row_background, strongest_pixel

ICON_SIZE = QSize(16, 16)

ITEMS = [
    ("folder", "folder", "Empty"),
    ("collection", "collection", "Bundle"),
    ("note", "note", "Notes"),
    ("dataset", "dataset", "Sales"),
    ("chart", "chart", "Trend"),
    ("gallery", "imagegallery", "Album"),
    ("image", "image", "Photo"),
    ("sketch", "sketch", "Diagram"),
]


@pytest.fixture
def panel(qtbot):
    app_context = build_app_context()
    project = Project(name="Icons")
    project.add_item(Folder(id="folder", name="Empty"))
    project.add_item(ItemCollection(id="collection", name="Bundle"))
    project.add_item(Note(id="note", name="Notes"))
    project.add_item(Dataset(id="dataset", name="Sales"))
    project.add_item(Chart(id="chart", name="Trend"))
    project.add_item(ImageGallery(id="gallery", name="Album"))
    project.add_item(Image(id="image", name="Photo"))
    project.add_item(Sketch(id="sketch", name="Diagram"))
    panel = ProjectViewPanel(app_context=app_context)
    qtbot.addWidget(panel)
    # Loading emits PROJECT_LOADED, which is how the panel fills its tree.
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


def _all_tree_items(panel: ProjectViewPanel) -> list[QTreeWidgetItem]:
    items = []
    iterator = QTreeWidgetItemIterator(panel.tree)
    while iterator.value():
        items.append(iterator.value())
        iterator += 1
    return items


def _use_green_icon_text(context, monkeypatch) -> None:
    manager = context.get_manager(ThemeManager)
    real_tokens = manager.get_design_tokens()
    monkeypatch.setattr(manager, "get_design_tokens", lambda: {**real_tokens, "text_primary": "#00AA00"})


def _same_pixels(first, second) -> bool:
    return first.pixmap(ICON_SIZE).toImage() == second.pixmap(ICON_SIZE).toImage()


@pytest.mark.parametrize(("item_id", "item_type", "name"), ITEMS)
def test_tree_item_shows_the_plain_name_and_its_kind_icon(panel, item_id, item_type, name):
    tree_panel, _project, context = panel

    row = _tree_item(tree_panel, item_id)

    assert row.text(0) == name
    assert not row.icon(0).isNull()
    assert _same_pixels(row.icon(0), item_icon(context, item_type))


def test_project_root_shows_the_plain_name_and_the_project_icon(panel):
    tree_panel, _project, context = panel

    root = tree_panel.tree.topLevelItem(0)

    assert root.text(0) == "Icons"
    assert _same_pixels(root.icon(0), item_icon(context, "project"))


def test_item_kinds_have_distinct_icons(panel):
    tree_panel, _project, _context = panel
    note, dataset, chart, sketch = (_tree_item(tree_panel, item_id).icon(0) for item_id in ("note", "dataset", "chart", "sketch"))

    assert not _same_pixels(note, dataset)
    assert not _same_pixels(dataset, chart)
    assert not _same_pixels(chart, sketch)


def test_inline_rename_uses_the_typed_name(panel):
    tree_panel, project, _context = panel

    _tree_item(tree_panel, "gallery").setText(0, "Holiday")

    assert project.find_item("gallery").name == "Holiday"


def test_rename_trims_surrounding_whitespace(panel):
    tree_panel, project, _context = panel

    _tree_item(tree_panel, "note").setText(0, "  Journal  ")

    assert project.find_item("note").name == "Journal"


# An empty gallery or folder is falsy (ItemCollection defines __len__), which once made a rejected rename blank its label.
@pytest.mark.parametrize(("item_id", "name"), [("sketch", "Diagram"), ("gallery", "Album"), ("folder", "Empty")])
def test_rejected_rename_restores_the_plain_current_name(panel, item_id, name):
    tree_panel, _project, _context = panel
    row = _tree_item(tree_panel, item_id)

    row.setText(0, "   ")

    assert row.text(0) == name


def test_tree_edits_names_with_the_default_delegate(panel):
    tree_panel, _project, _context = panel

    assert type(tree_panel.tree.itemDelegate()) is QStyledItemDelegate


def test_retint_icons_recolours_every_item_without_emitting_item_changed(panel, monkeypatch):
    tree_panel, _project, context = panel
    _use_green_icon_text(context, monkeypatch)
    changes = []
    tree_panel.tree.itemChanged.connect(lambda item, column: changes.append((item.text(0), column)))
    rows = _all_tree_items(tree_panel)
    assert len(rows) == len(ITEMS) + 1

    tree_panel.project_tree_manager.retint_icons()

    for row in rows:
        assert_tinted(strongest_pixel(row.icon(0)), "#00AA00")
    assert changes == []


def test_retint_icons_keeps_the_kind_of_each_icon(panel, monkeypatch):
    tree_panel, _project, context = panel
    _use_green_icon_text(context, monkeypatch)

    tree_panel.project_tree_manager.retint_icons()

    for item_id, item_type, _name in ITEMS:
        assert _same_pixels(_tree_item(tree_panel, item_id).icon(0), item_icon(context, item_type))


def test_retint_icons_leaves_the_placeholder_alone(qtbot):
    tree_panel = ProjectViewPanel(app_context=build_app_context())
    qtbot.addWidget(tree_panel)

    tree_panel.project_tree_manager.retint_icons()

    assert tree_panel.tree.topLevelItemCount() == 1
    assert tree_panel.tree.topLevelItem(0).text(0) == "No project loaded"


def test_apply_theme_retints_the_tree_icons(panel, monkeypatch):
    tree_panel, _project, context = panel
    _use_green_icon_text(context, monkeypatch)

    tree_panel._apply_theme()

    assert_tinted(strongest_pixel(_tree_item(tree_panel, "dataset").icon(0)), "#00AA00")


def test_item_rebuild_after_a_rename_keeps_names_plain_and_icons_set(panel):
    tree_panel, project, context = panel

    _tree_item(tree_panel, "dataset").setText(0, "Revenue")

    row = _tree_item(tree_panel, "dataset")
    assert project.find_item("dataset").name == "Revenue"
    assert row.text(0) == "Revenue"
    assert _same_pixels(row.icon(0), item_icon(context, "dataset"))


def _selected_icon_pixel(row: QTreeWidgetItem):
    return strongest_pixel(row.icon(0).pixmap(ICON_SIZE, QIcon.Mode.Selected))


def test_selected_rows_use_a_white_icon_to_match_the_selected_text(panel):
    tree_panel, _project, _context = panel

    for item_id, _item_type, _name in ITEMS:
        assert_tinted(_selected_icon_pixel(_tree_item(tree_panel, item_id)), "#FFFFFF")
    assert_tinted(_selected_icon_pixel(tree_panel.tree.topLevelItem(0)), "#FFFFFF")


def test_retint_keeps_the_white_selected_icon(panel, monkeypatch):
    tree_panel, _project, context = panel
    _use_green_icon_text(context, monkeypatch)

    tree_panel.project_tree_manager.retint_icons()

    assert_tinted(_selected_icon_pixel(_tree_item(tree_panel, "chart")), "#FFFFFF")
    assert_tinted(strongest_pixel(_tree_item(tree_panel, "chart").icon(0)), "#00AA00")


def test_a_selected_row_keeps_the_accent_background_when_hovered(panel):
    tree_panel, _project, context = panel
    tree_panel.tree.expandAll()

    # A forged option stands in for the mouse: hover state is process-wide, so real mouse moves are unreliable in parallel runs.
    background = hovered_selected_row_background(tree_panel.tree, _tree_item(tree_panel, "dataset"))

    assert_tinted(background, context.get_manager(ThemeManager).get_surface_palette()["accent"])


def test_rebuilding_a_large_tree_renders_each_icon_state_once(qtbot, monkeypatch):
    app_context = build_app_context()
    project = Project(name="Large")
    for index in range(34):
        project.add_item(Dataset(id=f"dataset-{index}", name=f"Data {index}"))
        project.add_item(Chart(id=f"chart-{index}", name=f"Chart {index}"))
        project.add_item(Note(id=f"note-{index}", name=f"Note {index}"))
    panel = ProjectViewPanel(app_context=app_context)
    qtbot.addWidget(panel)
    app_context.get_app_state().load_project(project)
    icon_library.clear_icon_cache()
    renders = []

    def counting_renderer(data):
        renders.append(data)
        return QSvgRenderer(data)

    monkeypatch.setattr(icon_library, "QSvgRenderer", counting_renderer)

    panel.project_tree_manager.update_project_tree(project)
    panel.project_tree_manager.update_project_tree(project)

    # The dataset, chart and note kinds, each as normal, disabled and selected (three colours). The project root row is kept
    # by a same-project rebuild, so its icon is not drawn again; the Project Details button's info icon is drawn once as
    # normal and disabled (two colours, no selected colour) and then comes from the cache.
    assert len(renders) == 3 * 3 + 2
    icon_library.clear_icon_cache()
