"""Tab that shows a Sketch on its canvas, with the drawing toolbar."""
from typing import override

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence, QShowEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QToolBar, QVBoxLayout, QWidget

from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas
from pandaplot.gui.components.tabs.sketch.tools.tool_manager import ToolMode
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.events import ProjectEvents
from pandaplot.models.project.items.sketch import Sketch
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager
from pandaplot.utils.item_labels import item_label

# Tool -> (button label, shortcut, tooltip).
TOOL_BUTTONS: dict[ToolMode, tuple[str, str, str]] = {
    ToolMode.SELECT: ("Select", "V", "Select, move and resize elements (V)"),
    ToolMode.FREEHAND: ("Pen", "P", "Draw a smooth freehand stroke (P)"),
    ToolMode.LINE: ("Line", "L", "Draw a straight line (L)"),
    ToolMode.RECTANGLE: ("Rectangle", "R", "Draw a rectangle (R)"),
    ToolMode.ELLIPSE: ("Ellipse", "E", "Draw an ellipse (E)"),
    ToolMode.TEXT: ("Text", "T", "Place a text label (T)"),
}


class SketchTab(PWidget):
    """Shows one Sketch on a SketchCanvas, with a toolbar to pick the tool,
    fit the canvas and see the zoom level.

    The canvas redraws itself whenever the sketch changes, so drawing,
    undo and redo all redraw the same way.
    """

    def __init__(self, app_context: AppContext, sketch: Sketch, parent: QWidget | None = None):
        super().__init__(app_context=app_context, parent=parent)
        self.sketch = sketch
        self._fitted_once = False
        self.tool_actions: dict[ToolMode, QAction] = {}
        self._initialize()

    @override
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.canvas = SketchCanvas(self.sketch, self, app_context=self.app_context)
        self.toolbar = self._build_toolbar()
        layout.addWidget(self.toolbar)
        layout.addWidget(self.canvas)
        self.canvas.tool_manager.tool_changed.connect(self._on_tool_changed)
        self.canvas.zoom_changed.connect(self._show_zoom)
        self.canvas.status_message.connect(self.status_label.setText)
        self._show_zoom(self.canvas.zoom)

    def _build_toolbar(self) -> QToolBar:
        toolbar = QToolBar("Sketch tools", self)
        toolbar.setAccessibleName("Sketch tools")
        group = QActionGroup(toolbar)
        group.setExclusive(True)
        for mode, (label, shortcut, tooltip) in TOOL_BUTTONS.items():
            action = QAction(label, toolbar)
            action.setCheckable(True)
            action.setChecked(mode is self.canvas.tool_manager.mode)
            action.setToolTip(tooltip)
            action.setShortcut(QKeySequence(shortcut))
            # Single-key shortcuts only while this tab has focus.
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            action.triggered.connect(lambda _checked=False, mode=mode: self.canvas.tool_manager.set_tool(mode))
            group.addAction(action)
            toolbar.addAction(action)
            self.addAction(action)
            self.tool_actions[mode] = action
        toolbar.addSeparator()
        fit_action = QAction("Fit", toolbar)
        fit_action.setToolTip("Show the whole canvas")
        fit_action.triggered.connect(self.canvas.fit_to_canvas)
        toolbar.addAction(fit_action)
        self.zoom_label = QLabel(toolbar)
        self.zoom_label.setAccessibleName("Zoom level")
        toolbar.addWidget(self.zoom_label)
        spacer = QWidget(toolbar)
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)
        self.status_label = QLabel(toolbar)
        self.status_label.setAccessibleName("Sketch status")
        toolbar.addWidget(self.status_label)
        return toolbar

    def _on_tool_changed(self, mode: ToolMode) -> None:
        self.tool_actions[mode].setChecked(True)
        self.status_label.clear()

    def _show_zoom(self, zoom: float) -> None:
        self.zoom_label.setText(f"{round(zoom * 100)}%")

    @override
    def _apply_theme(self):
        tokens = self.app_context.get_manager(ThemeManager).get_design_tokens()
        self.toolbar.setStyleSheet(f"""
            QToolBar {{
                background-color: {tokens["surface_white"]};
                border-bottom: 1px solid {tokens["border_panel"]};
                padding: 4px;
                spacing: 2px;
            }}
            QToolBar QToolButton {{
                color: {tokens["text_primary"]};
                background-color: transparent;
                border: 1px solid transparent;
                padding: 4px 10px;
                border-radius: {tokens["radius_control"]}px;
            }}
            QToolBar QToolButton:hover {{
                background-color: {tokens["surface_inset"]};
            }}
            QToolBar QToolButton:checked {{
                background-color: {tokens["accent_selected_bg"]};
                border-color: {tokens["accent"]};
                color: {tokens["accent_active_text"]};
            }}
            QToolBar QToolButton:focus {{
                border-color: {tokens["accent"]};
            }}
            QToolBar QLabel {{
                color: {tokens["text_secondary"]};
                padding: 0 6px;
            }}
        """)

    @override
    def setup_event_subscriptions(self):
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_RENAMED, self._on_item_renamed)

    def _on_item_renamed(self, event_data: dict):
        if event_data.get("item_id") == self.sketch.id:
            self.refresh_tab_title()

    @override
    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        # Fit once the tab has its real size; later shows keep the user's view.
        if not self._fitted_once:
            self._fitted_once = True
            self.canvas.fit_to_canvas()

    def get_tab_title(self) -> str:
        return item_label("sketch", self.sketch.name)

    def get_tab_data(self) -> dict:
        """Identify this tab to TabContainer for session/event bookkeeping."""
        return {"type": "sketch", "id": self.sketch.id}

    def refresh_tab_title(self):
        """Push the current tab title up to the tab container."""
        parent_container = self.parent()
        while parent_container is not None and not hasattr(parent_container, "update_tab_title"):
            parent_container = parent_container.parent()
        if parent_container:
            update_fn = getattr(parent_container, "update_tab_title", None)
            if callable(update_fn):
                try:
                    update_fn(self, self.get_tab_title())
                except Exception:
                    self.logger.debug("Failed to update tab title on parent container", exc_info=True)
