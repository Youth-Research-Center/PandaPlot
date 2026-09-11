from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGroupBox, QPushButton, QVBoxLayout, QWidget

from pandaplot.gui.components.tabs.sketch.tools.base_tool import ToolMode

if TYPE_CHECKING:
    from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas


class CircuitPalettePanel(QGroupBox):
    """Panel with buttons for selecting electronics circuit components and wire tool."""

    component_selected = Signal(object)

    def __init__(self, canvas: "SketchCanvas", parent: Optional[QWidget] = None):
        super().__init__("Circuit Components", parent)
        self.canvas: "SketchCanvas" = canvas
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.wire_btn = QPushButton("🔌 Wire")
        self.wire_btn.clicked.connect(self._select_wire)
        layout.addWidget(self.wire_btn)

        components = [
            ("Resistor", "resistor"),
            ("Capacitor", "capacitor"),
            ("Inductor", "inductor"),
            ("Diode", "diode"),
            ("Voltage Source", "voltage_source"),
            ("Ground", "ground"),
            ("Voltmeter", "voltmeter"),
            ("Ammeter", "ammeter"),
        ]

        for label, comp_type in components:
            btn = QPushButton(f"⚡ {label}")
            btn.clicked.connect(lambda _, t=comp_type: self._select_component(t))
            layout.addWidget(btn)

        layout.addStretch()

    def _select_wire(self):
        self.canvas.tool_manager.set_mode(ToolMode.WIRE)

    def _select_component(self, comp_type: str):
        tool = self.canvas.tool_manager.tools.get(ToolMode.CIRCUIT_COMPONENT)
        if tool and hasattr(tool, "set_component_type"):
            tool.set_component_type(comp_type)
        self.canvas.tool_manager.set_mode(ToolMode.CIRCUIT_COMPONENT)
        self.component_selected.emit(comp_type)
