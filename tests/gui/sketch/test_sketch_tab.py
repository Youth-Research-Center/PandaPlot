from PySide6.QtWidgets import QWidget

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.sketch.sketch_tab import SketchTab
from pandaplot.gui.components.tabs.tab_factory import TabFactory
from pandaplot.models.project.items.sketch import Sketch


def test_tab_factory_creates_sketch_tab(qtbot):
    app_ctx = build_app_context()
    tab_factory = app_ctx.get_manager(TabFactory)

    parent_widget = QWidget()
    qtbot.addWidget(parent_widget)
    sketch = Sketch(name="Factory Test Sketch")
    tab = tab_factory.create_tab(app_context=app_ctx, item=sketch, parent=parent_widget)

    assert isinstance(tab, SketchTab)
    assert tab.sketch is sketch


def test_layer_manager_panel_interactions(qtbot):
    app_ctx = build_app_context()
    parent_widget = QWidget()
    qtbot.addWidget(parent_widget)
    sketch = Sketch(name="Layer Panel Test")
    tab = SketchTab(app_context=app_ctx, sketch=sketch, parent=parent_widget)

    panel = tab.layer_panel
    assert len(sketch.layers) == 1

    # Add Layer
    panel._add_layer()
    assert len(sketch.layers) == 2
    assert sketch.layers[-1].name == "Layer 2"

    # Move Down
    panel._move_down()
    assert sketch.layers[0].name == "Layer 2"

    # Delete Layer
    panel._delete_layer()
    assert len(sketch.layers) == 1
