from typing import Optional, override

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pandaplot.commands.project.current_project import get_current_project
from pandaplot.gui.components.tabs.sketch.circuit_palette_panel import CircuitPalettePanel
from pandaplot.gui.components.tabs.sketch.layer_manager_panel import LayerManagerPanel
from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas
from pandaplot.gui.components.tabs.sketch.sketch_property_inspector import SketchPropertyInspector
from pandaplot.gui.components.tabs.sketch.tools.base_tool import ToolMode
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.sketch import Sketch
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.circuit_simulation import CircuitSimulator


class SketchTab(PWidget):
    """Editor tab for Sketch items combining canvas, drawing toolbar, inspector, and layer panel."""

    def __init__(self, app_context: AppContext, sketch: Sketch, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)
        self.sketch: Sketch = sketch
        self._initialize()

    @override
    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Drawing ToolBar
        self.drawing_toolbar = QToolBar("Drawing Tools")
        self.select_btn = QPushButton("Select")
        self.freehand_btn = QPushButton("Freehand")
        self.line_btn = QPushButton("Line")
        self.rect_btn = QPushButton("Rectangle")
        self.ellipse_btn = QPushButton("Ellipse")
        self.text_btn = QPushButton("Text")

        self.select_btn.clicked.connect(lambda: self.set_tool(ToolMode.SELECT))
        self.freehand_btn.clicked.connect(lambda: self.set_tool(ToolMode.FREEHAND))
        self.line_btn.clicked.connect(lambda: self.set_tool(ToolMode.LINE))
        self.rect_btn.clicked.connect(lambda: self.set_tool(ToolMode.RECTANGLE))
        self.ellipse_btn.clicked.connect(lambda: self.set_tool(ToolMode.ELLIPSE))
        self.text_btn.clicked.connect(lambda: self.set_tool(ToolMode.TEXT))

        self.drawing_toolbar.addWidget(self.select_btn)
        self.drawing_toolbar.addWidget(self.freehand_btn)
        self.drawing_toolbar.addWidget(self.line_btn)
        self.drawing_toolbar.addWidget(self.rect_btn)
        self.drawing_toolbar.addWidget(self.ellipse_btn)
        self.drawing_toolbar.addWidget(self.text_btn)

        self.drawing_toolbar.addSeparator()

        self.sim_btn = QPushButton("⚡ Run Simulation")
        self.sim_btn.clicked.connect(self._run_simulation)
        self.drawing_toolbar.addWidget(self.sim_btn)

        main_layout.addWidget(self.drawing_toolbar)

        # Canvas & Property Inspector
        cmd_executor = self.app_context.get_command_executor() if self.app_context else None
        self.canvas = SketchCanvas(self.sketch, command_executor=cmd_executor, parent=self)
        self.property_inspector = SketchPropertyInspector(self.canvas, self)

        self.property_inspector.property_changed.connect(
            self.canvas.apply_style_change_to_selection
        )

        main_layout.addWidget(self.property_inspector)

        # Splitter with Circuit Palette, Canvas, and Layer Panel
        splitter = QSplitter(Qt.Horizontal)

        self.circuit_palette = CircuitPalettePanel(self.canvas, parent=self)
        splitter.addWidget(self.circuit_palette)

        splitter.addWidget(self.canvas)

        self.layer_panel = LayerManagerPanel(self.sketch, self.canvas, self)
        splitter.addWidget(self.layer_panel)
        splitter.setSizes([150, 650, 200])

        main_layout.addWidget(splitter)

    def _run_simulation(self):
        try:
            sim = CircuitSimulator(self.sketch)
            res = sim.solve_dc()
        except Exception as e:
            QMessageBox.warning(self, "Circuit Simulation", f"Simulation failed:\n{e}")
            return

        df = pd.DataFrame(res.dataset_columns)
        dataset = Dataset(name=f"{self.sketch.name} Simulation", data=df)

        if self.app_context and self.app_context.get_app_state().has_project:
            project = get_current_project(self.app_context)
            if project:
                project.add_item(dataset)

        summary = "\n".join([f"{k}: {v}" for k, v in res.component_readouts.items()])
        if not summary:
            summary = "\n".join([f"Node {k}: {v:.3f} V" for k, v in res.node_voltages.items()])

        QMessageBox.information(
            self,
            "Circuit Simulation Results",
            f"DC Nodal Analysis Completed Successfully!\n\nReadouts:\n{summary}\n\nCreated Dataset '{dataset.name}'."
        )

    @override
    def _apply_theme(self):
        pass

    def set_tool(self, mode: ToolMode) -> None:
        self.canvas.tool_manager.set_mode(mode)

    def get_tab_title(self) -> str:
        return f"🎨 {self.sketch.name}"

    def get_tab_data(self) -> dict:
        return {"type": "sketch", "id": self.sketch.id}
