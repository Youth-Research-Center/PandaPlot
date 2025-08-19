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

    def _apply_to_qapp(self, ctx: ThemeContext) -> None:
        palette = self._app.palette() if self._app else QPalette()
        if ctx.theme == Theme.DARK:
            base_bg = QColor(30, 30, 30)
            base_fg = QColor(224, 224, 224)
        elif ctx.theme == Theme.LIGHT:
            base_bg = QColor(255, 255, 255)
            base_fg = QColor(0, 0, 0)
        else:
            base_bg = QColor(255, 255, 255)
            base_fg = QColor(0, 0, 0)
        palette.setColor(QPalette.ColorRole.Window, base_bg)
        palette.setColor(QPalette.ColorRole.WindowText, base_fg)
        palette.setColor(QPalette.ColorRole.Base, base_bg)
        palette.setColor(QPalette.ColorRole.Text, base_fg)
        palette.setColor(QPalette.ColorRole.Button, QColor(ctx.accent))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("white"))
        if self._app:
            self._app.setPalette(palette)
            stylesheet = self.build_stylesheet(ctx)
            self._app.setStyleSheet(stylesheet)
            default_font = self._app.font()
            default_font.setPointSize(ctx.interface_font_size)
            self._app.setFont(default_font)

    def build_stylesheet(self, ctx: ThemeContext) -> str:
        accent = ctx.accent
        return f"""
            QPushButton {{
                background-color: {accent};
                border: 1px solid {accent};
                border-radius: 4px;
                padding: 4px 8px;
            }}
            QPushButton:hover {{
                filter: brightness(1.1);
            }}
            QTabBar::tab:selected {{
                color: {accent};
            }}
        """

    def _on_config_event(self, data):  # signature per EventBus
        cfg = data.get("config")
        if cfg is None:
            return
        self.apply_from_config(cfg)


__all__ = ["ThemeManager", "ThemeContext"]
