"""Reusable color picker button widget."""
from PySide6.QtWidgets import QPushButton, QColorDialog
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QPainter

from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class ColorButton(QPushButton):
    """A button that displays and allows selection of colors."""

    colorChanged = Signal(str)

    def __init__(self, app_context: AppContext, parent=None, color: str = "#1f77b4"):
        super().__init__(parent)
        self.app_context = app_context
        self._color = color
        self.setFixedSize(30, 25)
        self.clicked.connect(self._select_color)
        self._update_appearance()

    def set_color(self, color: str):
        """Set the button color."""
        self._color = color
        self._update_appearance()
        if not self.signalsBlocked():
            self.colorChanged.emit(color)

    def get_color(self) -> str:
        """Get the current color."""
        return self._color

    def _select_color(self):
        """Open color dialog to select a new color."""
        color = QColorDialog.getColor(QColor(self._color), self, "Select Color")
        if color.isValid():
            self.set_color(color.name())

    def _update_appearance(self):
        """Trigger a repaint with theme-aware button styling."""
        # Get theme colors if parent has app_context
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        bg_color = palette.get('card_hover', '#f5f5f5')
        border_color = palette.get('card_border', '#888')
        hover_color = palette.get('card_bg', '#eaeaea')
        pressed_color = palette.get('card_border', '#e0e0e0')

        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg_color};
                border: 1px solid {border_color};
                border-radius: 4px;
            }}
            QPushButton:hover {{
                background: {hover_color};
            }}
            QPushButton:pressed {{
                background: {pressed_color};
            }}
        """)
        self.update()

    def paintEvent(self, event):  # noqa: D401 (Qt override)
        super().paintEvent(event)
        # Draw inner color swatch
        painter = QPainter(self)
        swatch_rect = self.rect().adjusted(6, 6, -6, -6)
        painter.setPen(QColor('#555555'))
        painter.setBrush(QColor(self._color))
        painter.drawRect(swatch_rect)
