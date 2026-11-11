from typing import override

import shiboken6
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QContextMenuEvent, QIcon, QMouseEvent
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.gui.resources.icon_library import build_icon
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager

_ICON_SIZE = 20


class IconBar(PWidget):
    """Icon bar component that holds panel toggle buttons."""

    panel_requested = Signal(str)  # Signal emitted when a panel is requested
    settings_requested = Signal()  # Signal emitted when settings button is clicked
    # Emitted when the user requests to dock the sidebar on a side ("left"/"right")
    position_change_requested = Signal(str)

    def __init__(self, app_context: AppContext, parent: QWidget, width: int = 40):
        super().__init__(app_context=app_context, parent=parent)
        self.icon_width = width
        self.panels = {}  # Store panel names and their buttons
        self.current_position = "left"  # Side the sidebar is currently docked on
        self._active_panel: str | None = None  # Panel whose button shows the active state

        # Drag-to-dock state. The empty area of the icon bar acts as a drag
        # handle: dragging it toward an edge re-docks the sidebar on that side.
        self._press_pos: QPoint | None = None
        self._dragging: bool = False
        self._drop_overlay: QWidget | None = None

        self._initialize()

    # ------------------------------------------------------------------
    # Drag-to-dock
    # ------------------------------------------------------------------
    @override
    def mousePressEvent(self, event: QMouseEvent):
        """Begin tracking a potential drag from the icon bar handle."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
            self._dragging = False
        super().mousePressEvent(event)

    @override
    def mouseMoveEvent(self, event: QMouseEvent):
        """Start/continue a drag once the cursor moves past the threshold."""
        if self._press_pos is not None and (event.buttons() & Qt.MouseButton.LeftButton):
            moved = (event.position().toPoint() - self._press_pos).manhattanLength()
            if not self._dragging and moved >= QApplication.startDragDistance():
                self._dragging = True
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
            if self._dragging:
                self._update_drop_overlay(event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Drop the sidebar onto whichever half the cursor was released over."""
        if self._dragging:
            side = self._side_for_global_pos(event.globalPosition().toPoint())
            self._end_drag()
            self.position_change_requested.emit(side)
        self._press_pos = None
        super().mouseReleaseEvent(event)

    def _side_for_global_pos(self, global_pos: QPoint) -> str:
        """Return 'left'/'right' based on which window half the point is in."""
        window = self.window()
        center = window.mapToGlobal(window.rect().center())
        return "left" if global_pos.x() < center.x() else "right"

    def _update_drop_overlay(self, global_pos: QPoint):
        """Highlight the window half the sidebar would dock to on release."""
        window = self.window()
        if self._drop_overlay is None:
            self._drop_overlay = QWidget(window)
            self._drop_overlay.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        side = self._side_for_global_pos(global_pos)
        rect = window.rect()
        half = max(1, rect.width() // 2)
        if side == "left":
            geometry = QRect(0, 0, half, rect.height())
        else:
            geometry = QRect(rect.width() - half, 0, half, rect.height())
        self._drop_overlay.setGeometry(geometry)

        r, g, b = self._accent_rgb()
        self._drop_overlay.setStyleSheet(
            f"background-color: rgba({r}, {g}, {b}, 45);"
            f"border: 2px solid rgba({r}, {g}, {b}, 200);"
        )
        self._drop_overlay.show()
        self._drop_overlay.raise_()

    def _end_drag(self):
        """Clear drag state and remove the drop overlay."""
        self._dragging = False
        self.unsetCursor()
        if self._drop_overlay is not None:
            self._drop_overlay.hide()
            self._drop_overlay.deleteLater()
            self._drop_overlay = None

    def _accent_rgb(self) -> tuple[int, int, int]:
        """Resolve the theme accent color as an (r, g, b) tuple for overlays."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        hex_color = palette.get("accent", "#4A90E2").lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join(c * 2 for c in hex_color)
        try:
            return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
        except ValueError:
            return (74, 144, 226)

    @override
    def contextMenuEvent(self, event: QContextMenuEvent):
        """Show a context menu to move the sidebar to the left or right."""
        menu = QMenu(self)
        left_action = menu.addAction("Dock sidebar left")
        right_action = menu.addAction("Dock sidebar right")
        for action, side in ((left_action, "left"), (right_action, "right")):
            action.setCheckable(True)
            action.setChecked(self.current_position == side)
            action.setEnabled(self.current_position != side)
        left_action.triggered.connect(
            lambda: self.position_change_requested.emit("left"))
        right_action.triggered.connect(
            lambda: self.position_change_requested.emit("right"))
        try:
            menu.exec(event.globalPos())
        finally:
            if shiboken6.isValid(menu):
                menu.deleteLater()

    @override
    def _init_ui(self):
        """Create the settings gear button at the bottom of the icon bar."""
        self.setFixedWidth(self.icon_width)
        self.setMinimumWidth(self.icon_width)
        self.setMaximumWidth(self.icon_width)
        # Remove hardcoded styling - will be applied in _apply_theme

        # Set size policy to prevent any stretching
        self.setSizePolicy(QSizePolicy.Policy.Fixed,
                           QSizePolicy.Policy.Expanding)

        # Layout for icon buttons
        self.button_layout = QVBoxLayout(self)
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.setSpacing(2)

        # Add stretch to push main panel buttons to top and settings to bottom
        self.button_layout.addStretch()
        
        # TODO(#216): use command instead of signal
        # TODO(#216): make settings button addition more generic so that icon bar doesn't know about settings
        self.settings_button = PButton(
            "", role="secondary", icon=True, on_click=self.settings_requested.emit
        )
        self.settings_button.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        self.settings_button.setToolTip("Settings")
        self.settings_button.setAccessibleName("Settings")
        self.settings_button.setIcon(self._tinted_icon("gear", "text_muted"))
        self.button_layout.addWidget(self.settings_button)

    @override
    def _apply_theme(self):
        """Apply theme styling to icon bar components."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        
        # Get theme colors for main background
        card_border = palette.get("card_border", "#dee2e6")
        
        # Apply theme to main icon bar background
        self.setStyleSheet(f"""
            IconBar {{
                background-color: {card_border};
            }}
        """)
        
        # Apply theme to all panel buttons
        self._apply_panel_buttons_theme()
        self.settings_button.setIcon(self._tinted_icon("gear", "text_muted"))

    def _apply_panel_buttons_theme(self):
        """Apply theme styling to all panel buttons, keeping the active panel's button highlighted."""
        for name, btn in self.panels.items():
            self._apply_button_theme(btn, is_active=(name == self._active_panel))

    def _tinted_icon(self, icon_name: str, token: str) -> QIcon:
        """Render a bundled icon in a design-token colour: `text_muted` normally, the contrast-safe `accent_icon_active` when selected."""
        tokens = self.app_context.get_manager(ThemeManager).get_design_tokens()
        return build_icon(icon_name, tokens[token], size=_ICON_SIZE, disabled_color=tokens["text_disabled"])

    def _apply_button_theme(self, button: QPushButton, *, is_active: bool = False) -> None:
        """Toggle the button's active/inactive appearance via the shared
        [segment="true"][selected="true"] QSS rule, plus a left-border accent
        indicator (via [navActive="true"]) unique to this vertical icon bar.

        navActive is kept separate from the shared selected property so this
        icon-bar-specific "clearer active indicator" (a left border) doesn't
        leak onto other [segment="true"] consumers such as SegmentedControl's
        horizontal pill row, where a left border would read as a stray line
        rather than an active-state cue."""
        button.setProperty("selected", is_active)
        button.setProperty("navActive", is_active)
        button.style().unpolish(button)
        button.style().polish(button)
        icon_name = button.property("iconName")
        if icon_name:
            button.setIcon(self._tinted_icon(icon_name, "accent_icon_active" if is_active else "text_muted"))

    def add_panel_button(self, name: str, *, label: str | None = None, icon_name: str) -> QPushButton:
        """Add a new panel button to the icon bar.

        Args:
            name: Unique panel identifier, emitted by panel_requested.
            label: Panel title used for the tooltip and accessible name; derived from `name` when omitted.
            icon_name: Name of the bundled icon (see icon_manifest.toml) shown on the button.

        Returns:
            The new icon-only button.
        """
        btn = QPushButton()
        btn.setProperty("iconName", icon_name)
        btn.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        btn.setProperty("segment", True)  # noqa: FBT003 - Qt method rejects keyword args
        btn.clicked.connect(lambda: self.panel_requested.emit(name))
        button_label = f"{label or name.replace('_', ' ').title()} panel"
        btn.setAccessibleName(button_label)
        btn.setToolTip(button_label)
        # Remove hardcoded styling - will be applied via theme

        # Insert before the stretch (which is before the settings button)
        # The layout has: [panel_buttons...] [stretch] [settings_button]
        # So we insert at position: layout.count() - 2 (before stretch and settings button)
        insert_position = max(0, self.button_layout.count() - 2)
        self.button_layout.insertWidget(insert_position, btn)
        self.panels[name] = btn
        
        # Apply theme styling to the new button
        self._apply_button_theme(btn, is_active=False)
        
        return btn

    def remove_panel_button(self, name: str):
        """Remove a panel button from the icon bar."""
        if name in self.panels:
            btn = self.panels[name]
            self.button_layout.removeWidget(btn)
            btn.deleteLater()
            del self.panels[name]
            if self._active_panel == name:
                self._active_panel = None

    def set_active_button(self, name: str):
        """Set the active button styling."""
        self._active_panel = name
        for panel_name, btn in self.panels.items():
            is_active = (panel_name == name)
            self._apply_button_theme(btn, is_active=is_active)
