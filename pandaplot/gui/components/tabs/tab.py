from typing import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from pandaplot.gui.components.tabs.tab_bar import TAB_DRAG_MIME_TYPE, CustomTabBar
from pandaplot.gui.core.widget_extension import PTabWidget
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager

EDGE_DROP_ZONE_RATIO = 0.75


class CustomTabWidget(PTabWidget):
    """Custom tab widget with enhanced features. Acts as one pane of the (possibly
    split) tab area; TabContainer owns one or two of these side by side."""

    tab_close_requested = Signal(int)
    split_requested = Signal(int)
    move_to_other_pane_requested = Signal(int)
    close_split_requested = Signal()
    tab_popout_requested = Signal(int)
    bar_drop_requested = Signal(object, int, int)  # source_pane_id, source_index, drop_index
    edge_drop_requested = Signal(object, int)  # source_pane_id, source_index

    def __init__(self, app_context: AppContext, parent: QWidget):
        super().__init__(app_context=app_context, parent=parent)
        self._split_capable = True
        self._accent_color = "#4A90E2"
        self._initialize()

    @override
    def _init_ui(self):
        """Set up the user interface components."""
        # Set custom tab bar
        self.custom_tab_bar = CustomTabBar(self)
        self.setTabBar(self.custom_tab_bar)

        self.setAcceptDrops(True)

        self._drop_overlay = QWidget(self)
        self._drop_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._drop_overlay.hide()

    def setup_event_subscriptions(self):
        """Set up event subscriptions for the main window."""
        self.custom_tab_bar.tab_close_requested.connect(self.tab_close_requested.emit)
        self.custom_tab_bar.split_requested.connect(self.split_requested.emit)
        self.custom_tab_bar.move_to_other_pane_requested.connect(self.move_to_other_pane_requested.emit)
        self.custom_tab_bar.close_split_requested.connect(self.close_split_requested.emit)
        self.custom_tab_bar.tab_popout_requested.connect(self.tab_popout_requested.emit)
        self.custom_tab_bar.bar_drop_requested.connect(self.bar_drop_requested.emit)

    def set_split_capable(self, *, can_split: bool):
        """Whether this pane may still be split further (only when it is the sole pane)."""
        self._split_capable = can_split
        self.custom_tab_bar.can_split = can_split

    def set_merge_capable(self, *, can_merge: bool):
        """Whether this pane can offer 'Move to Other Pane' / 'Close Split'."""
        self.custom_tab_bar.can_merge = can_merge

    def set_active(self, *, is_active: bool):
        """Toggle the visual indicator for which pane currently drives the sidebar."""
        self.setProperty("active_pane", is_active)
        self.style().unpolish(self)
        self.style().polish(self)

    # ----- edge drop zone (dropping near the right edge creates a split) -----
    def _edge_zone_rect(self):
        bar_height = self.tabBar().height() if self.tabBar() else 0
        zone_x = int(self.width() * EDGE_DROP_ZONE_RATIO)
        return zone_x, bar_height, self.width() - zone_x, self.height() - bar_height

    def _is_in_edge_zone(self, pos) -> bool:
        return self._split_capable and pos.x() >= int(self.width() * EDGE_DROP_ZONE_RATIO)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(TAB_DRAG_MIME_TYPE):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if not event.mimeData().hasFormat(TAB_DRAG_MIME_TYPE):
            super().dragMoveEvent(event)
            return

        pos = event.position().toPoint()
        if self._is_in_edge_zone(pos):
            x, y, w, h = self._edge_zone_rect()
            self._drop_overlay.setGeometry(x, y, w, h)
            self._drop_overlay.show()
            self._drop_overlay.raise_()
            event.acceptProposedAction()
        else:
            self._drop_overlay.hide()
            event.ignore()

    def dragLeaveEvent(self, event):
        self._drop_overlay.hide()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        mime = event.mimeData()
        self._drop_overlay.hide()
        if not mime.hasFormat(TAB_DRAG_MIME_TYPE):
            super().dropEvent(event)
            return

        pos = event.position().toPoint()
        if not self._is_in_edge_zone(pos):
            event.ignore()
            return

        payload = bytes(mime.data(TAB_DRAG_MIME_TYPE)).decode()
        pane_id_str, index_str = payload.split(":")
        self.edge_drop_requested.emit(int(pane_id_str), int(index_str))
        event.acceptProposedAction()

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

        self._accent_color = accent
        overlay_color = QColor(accent)
        overlay_r, overlay_g, overlay_b = (
            (overlay_color.red(), overlay_color.green(), overlay_color.blue())
            if overlay_color.isValid()
            else (74, 144, 226)
        )
        self._drop_overlay.setStyleSheet(
            f"background-color: rgba({overlay_r}, {overlay_g}, {overlay_b}, 90);"
        )

        self.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {card_border};
                background-color: {card_bg};
            }}
            QTabWidget[active_pane="true"]::pane {{
                border: 2px solid {accent};
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
