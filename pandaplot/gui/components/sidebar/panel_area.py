import logging

from PySide6.QtWidgets import QStackedWidget, QWidget


class PanelArea(QStackedWidget):
    """Panel area component that holds and manages panel content."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.logger = logging.getLogger(__name__)
        # Store panel names and their widgets
        self.panels: dict[str, QWidget] = {}

        # TODO: styling should be managed by theme
        self.setStyleSheet("background-color: #ffffff;")

    def add_panel(self, name: str, content_widget: QWidget):
        """Add a new panel to the area."""
        self.logger.debug("Adding panel: %s", name)
        if content_widget is None:
            self.logger.warning("Content widget is None for panel: %s", name)
            return

        if name is None or name in self.panels:
            self.logger.warning("Invalid panel name: %s", name)
            return

        content_widget.setStyleSheet("background-color: #ffffff;")
        self.addWidget(content_widget)
        self.panels[name] = content_widget

    def remove_panel(self, name: str):
        """Remove a panel from the area."""
        self.logger.debug("Removing panel: %s", name)
        if name in self.panels:
            widget = self.panels[name]
            self.removeWidget(widget)
            widget.deleteLater()
            del self.panels[name]
        else:
            self.logger.warning("Panel not found for removal: %s", name)

    def show_panel(self, name: str) -> bool:
        """Show a specific panel."""
        self.logger.debug("Showing panel: %s", name)

        if name not in self.panels:
            self.logger.warning("Panel not found: %s", name)
            return False

        self.setCurrentWidget(self.panels[name])
        return True
