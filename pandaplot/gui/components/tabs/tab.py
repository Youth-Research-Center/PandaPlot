from typing import override

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from pandaplot.gui.components.tabs.tab_bar import CustomTabBar
from pandaplot.gui.core.widget_extension import PTabWidget
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class CustomTabWidget(PTabWidget):
    """Custom tab widget with enhanced features."""
    
    tab_close_requested = Signal(int)

    def __init__(self, app_context: AppContext, parent: QWidget):
        super().__init__(app_context=app_context, parent=parent)
        self._initialize()

    @override
    def _init_ui(self):
        """Set up the user interface components."""
        # Set custom tab bar
        self.custom_tab_bar = CustomTabBar(self)
        self.setTabBar(self.custom_tab_bar)

    def setup_event_subscriptions(self):    
        """Set up event subscriptions for the main window."""
        self.custom_tab_bar.tab_close_requested.connect(self.tab_close_requested.emit)

    @override
    def _apply_theme(self):
        """Apply theme-specific styling to the tab widget based on current theme."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        
        # Get theme-appropriate colors
        card_bg = palette.get("card_bg", "#f8f9fa")
        card_hover = palette.get("card_hover", "#e9ecef")
        card_pressed = palette.get("card_pressed", "#dee2e6")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#000000")
        secondary_fg = palette.get("secondary_fg", "#555555")
        accent = palette.get("accent", "#4A90E2")
        
        # Derive accent color variant for pressed state
        accent_color = QColor(accent)
        if accent_color.isValid():
            accent_pressed = accent_color.darker(115).name()
        else:
            accent_pressed = accent
        
        self.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {card_border};
                background-color: {card_bg};
            }}
            QTabWidget::tab-bar {{
                left: 5px;
            }}
            QTabBar::tab {{
                background-color: {card_hover};
                border: 1px solid {card_border};
                border-bottom: none;
                padding: 8px 12px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 80px;
                color: {secondary_fg};
            }}
            QTabBar::tab:selected {{
                background-color: {card_bg};
                border-bottom: 1px solid {card_bg};
                color: {base_fg};
            }}
            QTabBar::tab:hover {{
                background-color: {card_pressed};
            }}
            QTabBar::close-button {{
                subcontrol-origin: margin;
                subcontrol-position: center right;
                background-color: {card_hover};
                border: 1px solid {card_border};
                border-radius: 6px;
                width: 12px;
                height: 12px;
                margin: 2px;
            }}
            QTabBar::close-button:hover {{
                background-color: #FF6B6B;
                border-color: #FF5252;
            }}
            QTabBar::close-button:pressed {{
                background-color: #FF5252;
                border-color: #E53935;
            }}
            QMenu {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                color: {base_fg};
                margin: 2px;
                border-radius: 4px;
            }}
            QMenu::item {{
                background-color: transparent;
                padding: 6px 20px;
                margin: 1px;
                border-radius: 2px;
            }}
            QMenu::item:selected {{
                background-color: {accent};
                color: {card_bg};
            }}
            QMenu::item:pressed {{
                background-color: {accent_pressed};
                color: {card_bg};
            }}
            QMenu::separator {{
                height: 1px;
                background-color: {card_border};
                margin: 2px 10px;
            }}
        """)