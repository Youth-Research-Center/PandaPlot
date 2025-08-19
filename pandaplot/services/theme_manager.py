"""Theme Manager (Phase 3).

Applies application-wide theming based on configuration and reacts to
configuration changes via the event bus. Emits a lightweight
``theme.changed`` event whenever an application-level theme (light/dark/system)
change or accent/font change is applied.

Responsibilities:
    * Build a global Qt stylesheet (QSS) from current configuration
    * Apply palette / font size adjustments (minimal for now)
    * Subscribe to ``config.loaded`` & ``config.updated`` events
    * Emit ``theme.changed`` after applying style

Non-goals (future phases): advanced component‑specific palettes, high‑contrast
accessibility themes, dynamic chart color palettes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor

from pandaplot.models.state.config import ApplicationConfig, Theme
from pandaplot.models.events.event_bus import EventBus


@dataclass(slots=True)
class ThemeContext:
    """Snapshot of theme-relevant config values."""

    theme: Theme
    accent: str
    interface_font_size: int


class ThemeManager:
    def __init__(self, event_bus: EventBus, config_provider, qt_app: Optional[QApplication] = None):
        """Create manager.

        Args:
            event_bus: shared event bus
            config_provider: object exposing ``config`` attribute (ConfigManager)
            qt_app: QApplication (can be injected later via ``set_qt_app``)
        """
        self._bus = event_bus
        self._provider = config_provider
        self._app: Optional[QApplication] = qt_app
        self._current: Optional[ThemeContext] = None
        # Subscribe to configuration lifecycle
        self._bus.subscribe("config.loaded", self._on_config_event)
        self._bus.subscribe("config.updated", self._on_config_event)

    def set_qt_app(self, app: QApplication) -> None:
        self._app = app

    def apply_current(self) -> None:
        cfg: ApplicationConfig = self._provider.config  # type: ignore[attr-defined]
        self.apply_from_config(cfg)

    def apply_from_config(self, cfg: ApplicationConfig) -> None:
        ctx = ThemeContext(
            theme=cfg.appearance.theme,
            accent=cfg.appearance.accent_color,
            interface_font_size=cfg.appearance.interface_font_size,
        )
        if self._current and self._current == ctx:
            return  # no change
        self._current = ctx
        if self._app is not None:
            self._apply_to_qapp(ctx)
        self._bus.emit("theme.changed", {
            "theme": ctx.theme.value,
            "accent": ctx.accent,
            "font_size": ctx.interface_font_size,
        })

    def build_stylesheet(self, ctx: ThemeContext) -> str:
        accent = ctx.accent
        text_color = "#FFFFFF"  # fallback
        hover = accent
        pressed = accent
        try:
            c = QColor(accent)
            if c.isValid():
                # Derive hover / pressed variants
                hover = c.lighter(110).name()
                pressed = c.darker(115).name()
                # Compute relative luminance to decide contrasting text color
                r, g, b = c.red(), c.green(), c.blue()
                lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0
                # If accent is light, use dark text; if dark, use light text
                if lum > 0.6:
                    text_color = "#000000"
                else:
                    text_color = "#FFFFFF"
            # Adjust for overall theme preference so light theme favors dark text unless accent is extremely dark
            if ctx.theme != Theme.DARK and text_color == "#FFFFFF":
                # Force dark text if accent still offers 4.5:1 contrast against white background (approx luminance threshold)
                # If accent is very dark (lum < 0.25) keep white text.
                if 'lum' in locals() and lum >= 0.25:
                    text_color = "#000000"
        except Exception:  # noqa: BLE001
            pass

        return f"""
            QPushButton[primary="true"] {{
                background-color: {accent};
                border: 1px solid {accent};
                border-radius: 4px;
                padding: 4px 8px;
                color: {text_color};
            }}
            QPushButton[primary="true"]:hover {{
                background-color: {hover};
                border-color: {hover};
            }}
            QPushButton[primary="true"]:pressed {{
                background-color: {pressed};
                border-color: {pressed};
            }}
            QTabBar::tab:selected {{ color: {accent}; }}
        """

    def _apply_to_qapp(self, ctx: ThemeContext) -> None:
        """Apply palette & global QSS to the QApplication."""
        if not self._app:
            return
        palette = self._app.palette() if self._app else QPalette()
        if ctx.theme == Theme.DARK:
            bg = QColor(30, 30, 30)
            fg = QColor(224, 224, 224)
        else:
            bg = QColor(255, 255, 255)
            fg = QColor(0, 0, 0)
        palette.setColor(QPalette.ColorRole.Window, bg)
        palette.setColor(QPalette.ColorRole.WindowText, fg)
        palette.setColor(QPalette.ColorRole.Base, bg)
        palette.setColor(QPalette.ColorRole.Text, fg)
        self._app.setPalette(palette)
        self._app.setStyleSheet(self.build_stylesheet(ctx))
        f = self._app.font()
        f.setPointSize(ctx.interface_font_size)
        self._app.setFont(f)

    def get_surface_palette(self) -> dict:
        if not self._current:
            return {
                "card_bg": "#f8f9fa",
                "card_hover": "#e9ecef",
                "card_pressed": "#dee2e6",
                "card_border": "#dee2e6",
                "base_fg": "#000000",
                "secondary_fg": "#555555",
                "accent": "#4A90E2",
            }
        ctx = self._current
        if ctx.theme == Theme.DARK:
            return {
                "card_bg": "#2a2c2e",
                "card_hover": "#323437",
                "card_pressed": "#3a3d40",
                "card_border": "#404347",
                "base_fg": "#e2e2e2",
                "secondary_fg": "#a8adb2",
                "accent": ctx.accent,
            }
        return {
            "card_bg": "#f8f9fa",
            "card_hover": "#e9ecef",
            "card_pressed": "#dee2e6",
            "card_border": "#dee2e6",
            "base_fg": "#000000",
            "secondary_fg": "#555555",
            "accent": ctx.accent,
        }

    def _on_config_event(self, data):  # signature per EventBus
        cfg = data.get("config")
        if cfg is None:
            return
        self.apply_from_config(cfg)


__all__ = ["ThemeManager", "ThemeContext"]
