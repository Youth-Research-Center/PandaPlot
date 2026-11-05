"""Tests for LayerManagerPanel, driven through its controls inside a real SketchTab."""
import pytest
from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtWidgets import QWidget

from pandaplot.app import build_app_context, create_tab_factory
from pandaplot.gui.components.tabs.sketch.layer_manager_panel import LAYER_ID_ROLE, LayerManagerPanel
from pandaplot.gui.components.tabs.sketch.sketch_tab import SketchTab
from pandaplot.models.project import Project
from pandaplot.models.project.items.sketch import RectangleElement, Sketch, SketchLayer


@pytest.fixture
def app_context(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    return build_app_context()


@pytest.fixture
def sketch(app_context) -> Sketch:
    sketch = Sketch(id="sketch-1", name="Diagram", active_layer_id="middle", layers=[
        SketchLayer(id="bottom", name="Background"),
        SketchLayer(id="middle", name="Shapes", elements=[RectangleElement(id="box", x=10.0, y=10.0, width=100.0, height=50.0, fill_color="#FF0000")]),
        SketchLayer(id="top", name="Labels"),
    ])
    project = Project(name="Layers")
    project.add_item(sketch)
    app_context.get_app_state().load_project(project)
    return sketch


@pytest.fixture
def container(qtbot):
    container = QWidget()
    qtbot.addWidget(container)
    return container


@pytest.fixture
def tab(app_context, sketch, container) -> SketchTab:
    tab = create_tab_factory().create_tab(app_context, sketch, parent=container)
    assert isinstance(tab, SketchTab)
    container.resize(1000, 600)
    tab.resize(1000, 600)
    container.show()
    return tab


@pytest.fixture
def panel(tab) -> LayerManagerPanel:
    return tab.layer_panel


@pytest.fixture
def executor(app_context):
    return app_context.get_command_executor()


def _row_ids(panel: LayerManagerPanel) -> list[str]:
    return [panel.layer_list.item(row).data(LAYER_ID_ROLE) for row in range(panel.layer_list.count())]


def _current_id(panel: LayerManagerPanel) -> str | None:
    item = panel.layer_list.currentItem()
    return None if item is None else item.data(LAYER_ID_ROLE)


def _layer(sketch: Sketch, layer_id: str) -> SketchLayer:
    layer = sketch.get_layer(layer_id)
    assert layer is not None
    return layer


def _click(qtbot, widget: QWidget) -> None:
    qtbot.mouseClick(widget, Qt.MouseButton.LeftButton)


def test_lists_layers_top_first_with_the_active_one_selected(panel):
    assert _row_ids(panel) == ["top", "middle", "bottom"]
    assert [panel.rows[layer_id].name_label.text() for layer_id in _row_ids(panel)] == ["Labels", "Shapes", "Background"]
    assert _current_id(panel) == "middle"


def test_clicking_a_row_activates_its_layer_without_an_undo_step(qtbot, panel, sketch, executor):
    rect = panel.layer_list.visualItemRect(panel.layer_list.item(0))
    # Click the name, clear of the row's toggles.
    qtbot.mouseClick(panel.layer_list.viewport(), Qt.MouseButton.LeftButton, pos=rect.center() + QPoint(rect.width() // 4, 0))

    assert sketch.active_layer_id == "top"
    assert _current_id(panel) == "top"
    assert executor.undo_stack == []


def test_arrow_keys_change_the_active_layer(qtbot, panel, sketch):
    panel.layer_list.setFocus()
    qtbot.keyClick(panel.layer_list, Qt.Key.Key_Down)

    assert sketch.active_layer_id == "bottom"


def test_add_puts_a_new_layer_above_the_active_one_and_undo_removes_it(qtbot, panel, sketch, executor):
    _click(qtbot, panel.add_button)

    new_id = sketch.layers[2].id
    assert [layer.id for layer in sketch.layers] == ["bottom", "middle", new_id, "top"]
    assert _row_ids(panel) == ["top", new_id, "middle", "bottom"]
    assert _current_id(panel) == new_id
    assert panel.rows[new_id].name_label.text() == "Layer 4"

    executor.undo()

    assert _row_ids(panel) == ["top", "middle", "bottom"]
    assert _current_id(panel) == "middle"


def test_delete_removes_the_active_layer_and_its_drawing(qtbot, tab, panel, sketch, executor):
    _click(qtbot, panel.delete_button)

    assert _row_ids(panel) == ["top", "bottom"]
    assert tab.canvas.element_item("box") is None

    executor.undo()

    assert _row_ids(panel) == ["top", "middle", "bottom"]
    assert tab.canvas.element_item("box") is not None
    assert _current_id(panel) == "middle"


def test_delete_is_disabled_for_the_last_layer(app_context, container):
    sketch = Sketch(layers=[SketchLayer(id="only")])
    panel = LayerManagerPanel(app_context, sketch, container)

    assert not panel.delete_button.isEnabled()


def test_move_buttons_reorder_and_restack_the_canvas(qtbot, tab, panel, sketch, executor):
    _click(qtbot, panel.up_button)

    assert [layer.id for layer in sketch.layers] == ["bottom", "top", "middle"]
    assert _row_ids(panel) == ["middle", "top", "bottom"]
    middle_item, top_item = tab.canvas.layer_item("middle"), tab.canvas.layer_item("top")
    assert middle_item is not None and top_item is not None
    assert middle_item.zValue() > top_item.zValue()
    # The active layer is now on top, so it can't go further up.
    assert not panel.up_button.isEnabled()

    _click(qtbot, panel.down_button)
    _click(qtbot, panel.down_button)

    assert [layer.id for layer in sketch.layers] == ["middle", "bottom", "top"]
    assert not panel.down_button.isEnabled()
    assert len(executor.undo_stack) == 3


def test_visibility_toggle_hides_the_layer_and_undo_shows_it(qtbot, tab, panel, sketch, executor):
    row = panel.rows["middle"]

    _click(qtbot, row.visible_button)

    assert _layer(sketch, "middle").visible is False
    layer_item = tab.canvas.layer_item("middle")
    assert layer_item is not None and not layer_item.isVisible()
    # Toggling a layer updates its row in place rather than rebuilding it.
    assert panel.rows["middle"] is row
    assert not row.visible_button.isChecked()

    executor.undo()

    assert _layer(sketch, "middle").visible is True
    assert row.visible_button.isChecked()


def test_lock_toggle_protects_the_layer(qtbot, tab, panel, sketch):
    assert tab.canvas.element_at(QPointF(50.0, 30.0)) == "box"

    _click(qtbot, panel.rows["middle"].lock_button)

    assert _layer(sketch, "middle").locked is True
    assert tab.canvas.element_at(QPointF(50.0, 30.0)) is None
    assert not panel.delete_button.isEnabled()
    assert panel.delete_button.toolTip() == "Unlock the layer to delete it"
    assert tab.canvas.tool_manager.drawing_blocked_reason() is not None


def test_hiding_a_layer_drops_its_selected_elements(qtbot, tab, panel):
    tab.canvas.set_selection(["box"])

    _click(qtbot, panel.rows["middle"].visible_button)

    assert tab.canvas.selected_ids == ()


def test_double_click_renames_the_active_layer(qtbot, monkeypatch, app_context, panel, sketch, executor):
    prompts = []

    def answer(title: str, message: str, default_text: str = "") -> str:
        prompts.append(default_text)
        return "Rectangles"

    monkeypatch.setattr(app_context.get_ui_controller(), "get_text_input", answer)
    rect = panel.layer_list.visualItemRect(panel.layer_list.item(1))

    # A real double-click starts with a plain click; mouseDClick sends only the second press.
    qtbot.mouseClick(panel.layer_list.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    qtbot.mouseDClick(panel.layer_list.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())

    assert prompts == ["Shapes"]
    assert _layer(sketch, "middle").name == "Rectangles"
    assert panel.rows["middle"].name_label.text() == "Rectangles"
    executor.undo()
    assert panel.rows["middle"].name_label.text() == "Shapes"


@pytest.mark.parametrize("key", [Qt.Key.Key_F2, Qt.Key.Key_Return])
def test_keyboard_renames_the_active_layer(qtbot, monkeypatch, app_context, panel, sketch, key):
    monkeypatch.setattr(app_context.get_ui_controller(), "get_text_input", lambda *_args: "Rectangles")
    panel.layer_list.setFocus()

    qtbot.keyClick(panel.layer_list, key)

    assert _layer(sketch, "middle").name == "Rectangles"


def test_cancelling_the_rename_changes_nothing(monkeypatch, app_context, panel, sketch, executor):
    monkeypatch.setattr(app_context.get_ui_controller(), "get_text_input", lambda *_args: None)

    panel.rename_active_layer()

    assert _layer(sketch, "middle").name == "Shapes"
    assert executor.undo_stack == []


def test_dragging_the_opacity_slider_previews_then_applies_one_step(tab, panel, sketch, executor):
    slider = panel.opacity_slider
    layer_item = tab.canvas.layer_item("middle")
    assert layer_item is not None

    slider.setSliderDown(True)
    slider.setValue(70)
    slider.setValue(40)

    assert _layer(sketch, "middle").opacity == 1.0
    assert layer_item.opacity() == pytest.approx(0.4)
    assert panel.opacity_value.text() == "40%"

    slider.setSliderDown(False)

    assert _layer(sketch, "middle").opacity == pytest.approx(0.4)
    assert len(executor.undo_stack) == 1

    executor.undo()

    assert slider.value() == 100
    restored_item = tab.canvas.layer_item("middle")
    assert restored_item is not None and restored_item.opacity() == 1.0


def test_keyboard_opacity_steps_apply_at_once(qtbot, panel, sketch):
    panel.opacity_slider.setFocus()

    qtbot.keyClick(panel.opacity_slider, Qt.Key.Key_PageDown)

    assert _layer(sketch, "middle").opacity == pytest.approx(0.9)


def test_opacity_slider_follows_the_active_layer(qtbot, panel, sketch):
    _layer(sketch, "top").opacity = 0.3

    panel.layer_list.setCurrentRow(0)

    assert sketch.active_layer_id == "top"
    assert panel.opacity_slider.value() == 30


def test_rows_describe_hidden_locked_and_translucent_layers(app_context, container):
    sketch = Sketch(layers=[SketchLayer(id="faded", name="Notes", visible=False, locked=True, opacity=0.5)])
    panel = LayerManagerPanel(app_context, sketch, container)

    assert panel.layer_list.item(0).data(Qt.ItemDataRole.AccessibleTextRole) == "Notes, hidden, locked, opacity 50%"
    assert panel.rows["faded"].visible_button.accessibleName() == "Visible: Notes"
    assert not panel.rows["faded"].visible_button.isChecked()
    assert panel.rows["faded"].lock_button.isChecked()


def test_layers_button_hides_and_shows_the_panel(tab):
    assert tab.layer_panel.isVisible()

    tab.layers_action.trigger()
    assert not tab.layer_panel.isVisible()

    tab.layers_action.trigger()
    assert tab.layer_panel.isVisible()
