from typing import override

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget

from pandaplot.gui.components.tabs.tab_bar import CustomTabBar
from pandaplot.gui.core.widget_extension import PTabWidget
from pandaplot.models.state.app_context import AppContext


class CustomTabWidget(PTabWidget):
    """Custom tab widget with enhanced features."""
    
    tab_close_requested = Signal(int)

    def __init__(self, app_context: AppContext, parent: QWidget):
        super().__init__(app_context=app_context, parent=parent)
        self._init_ui()
        self._apply_theme()
        self.setup_event_subscriptions()
        self.logger.info("PandaMainWindow initialized.")

    @override
    def _init_ui(self):
        """Set up the user interface components."""
        # Set custom tab bar
        self.custom_tab_bar = CustomTabBar(self)
        self.setTabBar(self.custom_tab_bar)

    def setup_event_subscriptions(self):    
        """Set up event subscriptions for the main window."""
        super().setup_event_subscriptions()
        self.custom_tab_bar.tab_close_requested.connect(self.tab_close_requested.emit)

    @override
    def _apply_theme(self):
        self.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #C0C0C0;
                background-color: white;
            }
            QTabWidget::tab-bar {
                left: 5px;
            }
            QTabBar::tab {
                background-color: #E1E1E1;
                border: 1px solid #C0C0C0;
                border-bottom: none;
                padding: 8px 12px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 80px;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 1px solid white;
            }
            QTabBar::tab:hover {
                background-color: #F0F0F0;
            }
            QTabBar::close-button {
                subcontrol-origin: margin;
                subcontrol-position: center right;
                background-color: #CCCCCC;
                border: 1px solid #999999;
                border-radius: 6px;
                width: 12px;
                height: 12px;
                margin: 2px;
            }
            QTabBar::close-button:hover {
                background-color: #FF6B6B;
                border-color: #FF5252;
            }
            QTabBar::close-button:pressed {
                background-color: #FF5252;
                border-color: #E53935;
            }
            QMenu {
                background-color: white;
                border: 1px solid #C0C0C0;
                color: black;
                margin: 2px;
                border-radius: 4px;
            }
            QMenu::item {
                background-color: transparent;
                padding: 6px 20px;
                margin: 1px;
                border-radius: 2px;
            }
            QMenu::item:selected {
                background-color: #4A90E2;
                color: white;
            }
            QMenu::item:pressed {
                background-color: #357ABD;
                color: white;
            }
            QMenu::separator {
                height: 1px;
                background-color: #C0C0C0;
                margin: 2px 10px;
            }
        """)