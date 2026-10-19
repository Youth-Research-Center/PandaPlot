"""Tab that shows a Sketch on its canvas."""
from typing import override

from PySide6.QtGui import QColor, QShowEvent
from PySide6.QtWidgets import QVBoxLayout, QWidget

from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.events import ProjectEvents, SketchEvents
from pandaplot.models.project.items.sketch import Sketch
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager
from pandaplot.utils.item_labels import item_label


class SketchTab(PWidget):
    """Shows one Sketch and redraws it whenever the sketch changes.

    Edits reach the model through sketch commands, which emit
    `SketchEvents.SKETCH_CHANGED`; the tab rebuilds its canvas from the
    model on that event, so undo and redo redraw the same way.
    """

    def __init__(self, app_context: AppContext, sketch: Sketch, parent: QWidget | None = None):
        super().__init__(app_context=app_context, parent=parent)
        self.sketch = sketch
        self._fitted_once = False
        self._initialize()

    @override
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = SketchCanvas(self.sketch, self)
        layout.addWidget(self.canvas)

    @override
    def _apply_theme(self):
        tokens = self.app_context.get_manager(ThemeManager).get_design_tokens()
        # A neutral grey around the paper and a hairline edge, so a white
        # sketch stays distinguishable from a white window in the light theme.
        self.canvas.set_frame_colors(surround=QColor(tokens["border_panel"]), paper_border=QColor(tokens["border_control"]))

    @override
    def setup_event_subscriptions(self):
        self.subscribe_to_event(SketchEvents.SKETCH_CHANGED, self._on_sketch_changed)
        self.subscribe_to_event(ProjectEvents.PROJECT_ITEM_RENAMED, self._on_item_renamed)

    def _on_sketch_changed(self, event_data: dict):
        if event_data.get("sketch_id") == self.sketch.id:
            self.canvas.rebuild()

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
