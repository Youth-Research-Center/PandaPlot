"""The project's root row in the Project Explorer has a button that opens Project Details.

Project Details is otherwise only in File and the tree's context menu. The button sits on the project row
itself (in a narrow actions column), so each project root gets its own once several can be open.
"""

import pytest
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QAbstractItemView, QApplication, QLineEdit, QToolButton

from pandaplot.app import build_app_context
from pandaplot.commands.project.folder import CreateFolderCommand
from pandaplot.gui.components.sidebar.project.project_view_panel import ProjectViewPanel
from pandaplot.gui.dialogs.project import project_details_dialog
from pandaplot.models.project import Project
from pandaplot.models.project.items import Dataset, Folder
from pandaplot.models.state.config import Theme
from pandaplot.services.theme import ThemeManager
from pandaplot.services.theme.theme_manager import ThemeContext
from tests.gui.icon_testing import ICON_TOKENS, assert_tinted, strongest_pixel


@pytest.fixture
def panel(qtbot, monkeypatch):
    opened: list = []
    monkeypatch.setattr(project_details_dialog, "edit_project_details", lambda app_context, parent: opened.append((app_context, parent)))
    app_context = build_app_context()
    panel = ProjectViewPanel(app_context=app_context)
    qtbot.addWidget(panel)
    panel.resize(300, 500)
    panel.show()
    qtbot.waitExposed(panel)
    return panel, app_context, opened


def _root_button(panel: ProjectViewPanel) -> QToolButton | None:
    root = panel.tree.topLevelItem(0)
    widget = panel.tree.itemWidget(root, 1) if root is not None else None
    return widget if isinstance(widget, QToolButton) else None


def _project_with_a_folder(name: str = "Demo") -> Project:
    project = Project(name=name)
    project.add_item(Folder(id="folder", name="Data"))
    project.add_item(Dataset(id="dataset", name="Sales"))
    return project


def _icon_pixel(button: QToolButton) -> QColor:
    return strongest_pixel(button.icon())


def test_only_the_project_row_has_the_button(panel):
    panel, app_context, _ = panel
    assert _root_button(panel) is None  # the "No project loaded" placeholder
    assert panel.tree.itemWidget(panel.tree.topLevelItem(0), 1) is None

    app_context.get_app_state().load_project(_project_with_a_folder())

    root = panel.tree.topLevelItem(0)
    assert root.data(0, Qt.ItemDataRole.UserRole)["type"] == "project"
    assert _root_button(panel) is not None
    assert panel.tree.itemWidget(root.child(0), 1) is None
    assert panel.tree.itemWidget(root.child(1), 1) is None


def test_clicking_the_button_opens_project_details(panel, qtbot):
    panel, app_context, opened = panel
    app_context.get_app_state().load_project(_project_with_a_folder())

    qtbot.mouseClick(_root_button(panel), Qt.MouseButton.LeftButton)

    assert opened == [(app_context, panel)]


def test_button_is_an_accessible_keyboard_reachable_icon_button(panel, qtbot):
    panel, app_context, opened = panel
    app_context.get_app_state().load_project(_project_with_a_folder())
    button = _root_button(panel)

    assert not button.icon().isNull()
    assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly
    assert button.accessibleName() == "Project Details: Demo"
    assert button.accessibleDescription()
    assert "Project Details" in button.toolTip()
    assert button.focusPolicy() & Qt.FocusPolicy.TabFocus
    assert panel.tree.headerItem().data(1, Qt.ItemDataRole.AccessibleTextRole) == "Actions"

    button.setFocus()
    qtbot.keyClick(button, Qt.Key.Key_Space)
    assert len(opened) == 1


def test_tab_from_the_tree_reaches_the_button_and_shift_tab_returns(panel, qtbot):
    panel, app_context, _ = panel
    app_context.get_app_state().load_project(_project_with_a_folder())
    button = _root_button(panel)

    panel.tree.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() is panel.tree)
    qtbot.keyClick(panel.tree, Qt.Key.Key_Tab)
    qtbot.waitUntil(lambda: QApplication.focusWidget() is button)
    qtbot.keyClick(button, Qt.Key.Key_Tab, Qt.KeyboardModifier.ShiftModifier)
    qtbot.waitUntil(lambda: QApplication.focusWidget() is panel.tree)


def test_name_column_takes_the_width_and_the_action_column_stays_narrow(panel):
    panel, app_context, _ = panel
    app_context.get_app_state().load_project(_project_with_a_folder())
    button = _root_button(panel)

    assert panel.tree.columnCount() == 2
    assert panel.tree.headerItem().text(0) == "Project Structure"
    assert panel.tree.columnWidth(1) <= 2 * button.iconSize().width()
    assert panel.tree.columnWidth(0) > panel.tree.columnWidth(1)
    assert not panel.tree.horizontalScrollBar().isVisible()


def test_the_root_row_is_as_tall_as_any_other_row(panel):
    panel, app_context, _ = panel
    app_context.get_app_state().load_project(_project_with_a_folder())
    root = panel.tree.topLevelItem(0)

    assert abs(panel.tree.visualItemRect(root).height() - panel.tree.visualItemRect(root.child(0)).height()) <= 2


def test_the_button_is_re_sized_from_the_row_height_when_the_font_grows(panel):
    panel, app_context, _ = panel
    app_context.get_app_state().load_project(_project_with_a_folder())
    button = _root_button(panel)
    small = button.height()

    font = panel.tree.font()
    font.setPointSize(36)
    panel.tree.setFont(font)
    panel.project_tree_manager.retint_icons()

    assert button.height() > small
    assert panel.tree.columnWidth(1) == button.width() + 4


def test_the_same_button_survives_tree_rebuilds_and_keeps_focus(panel, qtbot):
    panel, app_context, opened = panel
    project = _project_with_a_folder()
    app_context.get_app_state().load_project(project)
    button = _root_button(panel)
    button.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() is button)

    panel.project_tree_manager.update_project_tree(project)
    app_context.get_command_executor().execute_command(CreateFolderCommand(app_context, "New", None))  # PROJECT_CHANGED

    assert panel.tree.topLevelItem(0).childCount() == 3
    assert _root_button(panel) is button
    assert QApplication.focusWidget() is button
    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert len(opened) == 1


def test_a_same_project_rebuild_leaves_nothing_selected_like_before(panel):
    panel, app_context, _ = panel
    app_context.get_app_state().load_project(_project_with_a_folder())
    button = _root_button(panel)
    root = panel.tree.topLevelItem(0)
    panel.tree.setCurrentItem(root.child(1))
    assert panel.tree.selectedItems()

    app_context.get_command_executor().execute_command(CreateFolderCommand(app_context, "New", None))

    assert panel.tree.currentItem() is None
    assert panel.tree.selectedItems() == []
    assert _root_button(panel) is button
    assert_tinted(_icon_pixel(button), ICON_TOKENS["text_primary"])


def test_the_expanded_state_survives_a_same_project_rebuild(panel):
    panel, app_context, _ = panel
    app_context.get_app_state().load_project(_project_with_a_folder())
    root = panel.tree.topLevelItem(0)
    root.child(0).setExpanded(True)

    app_context.get_command_executor().execute_command(CreateFolderCommand(app_context, "New", None))

    assert panel.tree.topLevelItem(0).child(0).isExpanded()


def test_a_different_project_gets_its_own_button_and_closing_removes_it(panel):
    panel, app_context, _ = panel
    state = app_context.get_app_state()
    state.load_project(_project_with_a_folder("First"))
    first = _root_button(panel)

    state.load_project(_project_with_a_folder("Second"))
    second = _root_button(panel)

    assert second is not None
    assert second is not first
    assert second.accessibleName() == "Project Details: Second"
    assert panel.tree.topLevelItemCount() == 1

    state.close_project()
    assert _root_button(panel) is None
    assert panel.tree.topLevelItemCount() == 1  # the placeholder


def test_the_accessible_name_follows_a_project_rename(panel):
    panel, app_context, _ = panel
    project = _project_with_a_folder()
    app_context.get_app_state().load_project(project)
    button = _root_button(panel)

    project.name = "Renamed"
    panel.project_tree_manager.update_project_tree(project)

    assert _root_button(panel) is button
    assert panel.tree.topLevelItem(0).text(0) == "Renamed"
    assert button.accessibleName() == "Project Details: Renamed"


def test_the_icon_is_tinted_for_the_row_state_and_follows_the_theme(panel, monkeypatch):
    panel, app_context, _ = panel
    app_context.get_app_state().load_project(_project_with_a_folder())
    button = _root_button(panel)
    root = panel.tree.topLevelItem(0)
    assert_tinted(_icon_pixel(button), ICON_TOKENS["text_primary"])

    panel.tree.setCurrentItem(root)
    assert_tinted(_icon_pixel(button), ICON_TOKENS["text_on_accent"])

    panel.tree.setCurrentItem(root.child(0))
    assert_tinted(_icon_pixel(button), ICON_TOKENS["text_primary"])

    manager = app_context.get_manager(ThemeManager)
    real_tokens = manager.get_design_tokens()
    monkeypatch.setattr(manager, "get_design_tokens", lambda: {**real_tokens, "text_primary": "#00AA00"})
    panel.project_tree_manager.retint_icons()
    assert_tinted(_icon_pixel(button), "#00AA00")


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_the_icon_has_3_to_1_contrast_in_every_theme_and_state(panel, monkeypatch, theme):
    panel, app_context, _ = panel
    app_context.get_app_state().load_project(_project_with_a_folder())
    themed = ThemeManager.__new__(ThemeManager)
    themed._current = ThemeContext(theme=theme, accent="#4A56C6", interface_font_size=10)
    manager = app_context.get_manager(ThemeManager)
    monkeypatch.setattr(manager, "get_design_tokens", themed.get_design_tokens)
    monkeypatch.setattr(manager, "get_surface_palette", themed.get_surface_palette)
    palette = themed.get_surface_palette()
    root = panel.tree.topLevelItem(0)

    panel.tree.setCurrentItem(root.child(0))
    panel.project_tree_manager.retint_icons()
    assert ThemeManager._contrast_ratio(_icon_pixel(_root_button(panel)), QColor(palette["card_bg"])) >= 3.0

    panel.tree.setCurrentItem(root)
    assert ThemeManager._contrast_ratio(_icon_pixel(_root_button(panel)), QColor(palette["accent"])) >= 3.0


def test_f2_after_clicking_the_action_cell_renames_the_name_not_the_action_column(panel, qtbot):
    panel, app_context, _ = panel
    app_context.get_app_state().load_project(_project_with_a_folder())
    tree = panel.tree
    row = tree.topLevelItem(0).child(0)
    action_cell = tree.visualRect(tree.indexFromItem(row, 1))
    QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=action_cell.center())
    assert tree.currentIndex().column() == 1

    tree.setFocus()
    qtbot.keyClick(tree, Qt.Key.Key_F2)

    assert tree.state() == QAbstractItemView.State.EditingState
    editor = tree.viewport().findChild(QLineEdit)
    assert editor is not None
    name_cell = tree.visualRect(tree.indexFromItem(row, 0))
    assert name_cell.contains(editor.geometry().center())
    assert not action_cell.contains(editor.geometry().center())


def test_the_action_column_never_opens_an_editor(panel):
    panel, app_context, _ = panel
    app_context.get_app_state().load_project(_project_with_a_folder())
    tree = panel.tree
    row = tree.topLevelItem(0).child(0)
    tree.setCurrentItem(row)

    tree.edit(tree.indexFromItem(row, 1), QAbstractItemView.EditTrigger.EditKeyPressed, QEvent(QEvent.Type.KeyPress))

    editor = tree.viewport().findChild(QLineEdit)
    assert editor is not None
    assert tree.visualRect(tree.indexFromItem(row, 0)).contains(editor.geometry().center())


def test_a_drop_highlight_covers_every_column_of_the_row(panel):
    panel, app_context, _ = panel
    app_context.get_app_state().load_project(_project_with_a_folder())
    tree = panel.tree
    root = tree.topLevelItem(0)
    before = [root.background(column).color().alpha() for column in range(2)]

    tree._highlight_item(root)
    assert all(root.background(column).color().alpha() == 120 for column in range(2))

    tree._clear_highlight()
    assert [root.background(column).color().alpha() for column in range(2)] == before
