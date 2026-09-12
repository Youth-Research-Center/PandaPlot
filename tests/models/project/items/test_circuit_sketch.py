from PySide6.QtWidgets import QWidget

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.sketch.sketch_tab import SketchTab
from pandaplot.gui.components.tabs.tab_factory import TabFactory
from pandaplot.models.project.items.circuit_sketch import CircuitSketch


def test_circuit_sketch_instantiation():
    cs = CircuitSketch(name="My Circuit")
    assert cs.name == "My Circuit"
    data = cs.to_dict()
    loaded = CircuitSketch.from_dict(data)
    assert loaded.name == cs.name


def test_tab_factory_creates_circuit_sketch_tab(qtbot):
    app_ctx = build_app_context()
    tab_factory = app_ctx.get_manager(TabFactory)

    parent_widget = QWidget()
    qtbot.addWidget(parent_widget)
    cs = CircuitSketch(name="Factory Circuit Test")
    tab = tab_factory.create_tab(app_context=app_ctx, item=cs, parent=parent_widget)

    assert isinstance(tab, SketchTab)
    assert tab.sketch is cs
