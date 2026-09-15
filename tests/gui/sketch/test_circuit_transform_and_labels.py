from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas
from pandaplot.gui.components.tabs.sketch.sketch_property_inspector import SketchPropertyInspector
from pandaplot.models.project.items.sketch import CircuitComponentElement, Sketch


def test_select_tool_hotkeys_rotate_and_flip(qtbot):
    sketch = Sketch(name="Hotkey Test")
    layer = sketch.get_active_layer()
    comp = CircuitComponentElement(x=100, y=100, component_type="resistor")
    layer.elements.append(comp)

    canvas = SketchCanvas(sketch)
    qtbot.addWidget(canvas)

    item = canvas.item_map.get(comp.id)
    assert item is not None
    item.setSelected(True)

    event_r = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_R, Qt.NoModifier)
    canvas.tool_manager.key_press(event_r)
    assert comp.rotation == 90.0

    event_shift_r = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_R, Qt.ShiftModifier)
    canvas.tool_manager.key_press(event_shift_r)
    assert comp.rotation == 0.0

    event_h = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_H, Qt.NoModifier)
    canvas.tool_manager.key_press(event_h)
    assert comp.flip_horizontal is True

    event_v = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_V, Qt.NoModifier)
    canvas.tool_manager.key_press(event_v)
    assert comp.flip_vertical is True


def test_property_inspector_circuit_label_fields(qtbot):
    sketch = Sketch(name="Inspector Test")
    layer = sketch.get_active_layer()
    c1 = CircuitComponentElement(component_type="resistor", designator="R1", value="10k")
    c2 = CircuitComponentElement(component_type="capacitor", designator="C1", value="100n")
    layer.elements.extend([c1, c2])

    canvas = SketchCanvas(sketch)
    qtbot.addWidget(canvas)
    inspector = SketchPropertyInspector(canvas)
    qtbot.addWidget(inspector)

    item1 = canvas.item_map.get(c1.id)
    item2 = canvas.item_map.get(c2.id)

    item1.setSelected(True)
    inspector.update_from_selection()

    assert inspector.desig_edit.isHidden() is False
    assert inspector.desig_edit.text() == "R1"
    assert inspector.val_edit.text() == "10k"

    item1.setSelected(False)
    item2.setSelected(True)
    inspector.update_from_selection()

    assert inspector.desig_edit.isHidden() is False
