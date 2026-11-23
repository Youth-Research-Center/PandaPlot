"""Theme Manager (Phase 3).

Applies application-wide theming based on configuration and reacts to
configuration changes via the event bus. Emits a lightweight
``theme.changed`` event whenever an application-level theme (light/dark/system)
change or accent/font change is applied.

Responsibilities:
    * Build a global Qt stylesheet (QSS) from current configuration
    * Apply palette / font size adjustments (minimal for now)
    * Subscribe to ``config.updated`` events
    * Emit ``theme.changed`` after applying style

Non-goals (future phases): advanced component‑specific palettes, high‑contrast
accessibility themes, dynamic chart color palettes.
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.events.event_types import ConfigEvents, ThemeEvents
from pandaplot.models.state.config import AppearanceConfig, ApplicationConfig, Theme
from pandaplot.services.theme.caret_icon import caret_icon_path
from pandaplot.services.theme.contrast import contrast_ratio, contrasting_text_color
from pandaplot.services.theme.design_tokens import build_design_tokens, freeze_tokens
from pandaplot.utils.garbage_collection import paused_garbage_collection

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ThemeContext:
    """Snapshot of theme-relevant config values."""

    theme: Theme
    accent: str
    interface_font_size: int


class ThemeManager:
    # Class attribute so a manager built with `ThemeManager.__new__` (tests) still has the cache slot.
    _frozen_tokens: tuple[tuple[Theme, str] | None, Mapping[str, Any]] | None = None

    def __init__(self, event_bus: EventBus, config_provider, qt_app: QApplication | None = None):
        """Create manager.

        Args:
            event_bus: shared event bus
            config_provider: object exposing ``config`` attribute (ConfigManager)
            qt_app: QApplication (can be injected later via ``set_qt_app``)
        """
        self._bus = event_bus
        self._provider = config_provider
        self._app: QApplication | None = qt_app
        self._current: ThemeContext | None = None
        # Subscribe to configuration lifecycle events
        self._bus.subscribe(ConfigEvents.CONFIG_UPDATED, self._on_config_event)

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
        self._bus.emit(ThemeEvents.THEME_CHANGED, {
            "theme": ctx.theme.value,
            "accent": ctx.accent,
            "font_size": ctx.interface_font_size,
        })

    @classmethod
    def _contrast_ratio(cls, first: QColor, second: QColor) -> float:
        """WCAG 2.x contrast ratio; see `contrast.contrast_ratio`."""
        return contrast_ratio(first, second)

    @classmethod
    def _contrasting_text_color(cls, accent: QColor) -> QColor:
        """Black or white, whichever is more legible on `accent`; see `contrast.contrasting_text_color`."""
        return contrasting_text_color(accent)

    @staticmethod
    def _combo_box_rules(tokens: dict[str, Any], *, accent: str, selected_text: str) -> str:
        """QSS for the app-wide dropdown (QComboBox) style.

        Every combo box -- sidebar panels, dialogs and wizards -- gets this one
        look, so a dialog must not restyle ``QComboBox`` itself. Where the list
        opens is not a stylesheet matter (macOS opens a native menu over the
        field whatever the QSS says); ``DropDownComboBox`` takes care of that.
        Styling ``::drop-down`` removes Qt's own arrow, so a caret in the
        theme's muted text colour is supplied (a `text_disabled` one while
        disabled).

        Args:
            tokens: Design tokens from ``get_design_tokens()``.
            accent: Accent colour used for the hover/focus border and selection.
            selected_text: Legible text colour on top of ``accent``.

        Returns:
            The QSS block for ``QComboBox`` and its popup list.
        """
        caret = caret_icon_path(tokens["text_muted"])
        caret_disabled = caret_icon_path(tokens["text_disabled"])
        return f"""
            QComboBox {{
                background-color: {tokens['surface_white']};
                color: {tokens['text_primary']};
                border: 1px solid {tokens['border_control']};
                border-radius: {tokens['radius_control']}px;
                padding: 4px 8px;
                min-height: 18px;
            }}
            QComboBox:hover, QComboBox:focus, QComboBox:on {{
                border-color: {accent};
            }}
            QComboBox:disabled {{
                background-color: {tokens['surface_inset']};
                color: {tokens['text_disabled']};
                border-color: {tokens['border_subtle']};
            }}
            QComboBox::drop-down {{
                subcontrol-origin: padding;
                subcontrol-position: center right;
                width: 22px;
                border: none;
            }}
            QComboBox::down-arrow {{
                image: url("{caret}");
                width: 12px;
                height: 12px;
            }}
            QComboBox::down-arrow:disabled {{
                image: url("{caret_disabled}");
            }}
            QComboBox QAbstractItemView {{
                background-color: {tokens['surface_white']};
                color: {tokens['text_primary']};
                border: 1px solid {tokens['border_control']};
                outline: none;
                padding: 2px;
                selection-background-color: {accent};
                selection-color: {selected_text};
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 22px;
                padding: 2px 8px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {accent};
                color: {selected_text};
            }}
        """

    @staticmethod
    def _number_input_rules(tokens: dict[str, Any], *, accent: str) -> str:
        """QSS for ``DecimalInput`` / ``IntegerInput`` (``QFrame[numberInput]``).

        The frame draws the field border so the ``-`` / ``+`` buttons, the
        number and the unit read as one control; the inner line edit is
        flat (``NumberInput`` sets that on the edit itself). The frame carries ``focused`` and ``invalid`` dynamic
        properties because a stylesheet cannot style a parent by its child's
        focus.

        Args:
            tokens: Design tokens from ``get_design_tokens()``.
            accent: Accent colour for the hover and focus border.

        Returns:
            The QSS block for the number inputs and their parts.
        """
        return f"""
            QFrame[numberInput="true"] {{
                background-color: {tokens['surface_white']};
                border: 1px solid {tokens['border_control']};
                border-radius: {tokens['radius_control']}px;
            }}
            QFrame[numberInput="true"]:hover, QFrame[numberInput="true"][focused="true"] {{
                border-color: {accent};
            }}
            QFrame[numberInput="true"][invalid="true"] {{
                border-color: {tokens['status_danger']};
            }}
            QFrame[numberInput="true"]:disabled {{
                background-color: {tokens['surface_inset']};
                border-color: {tokens['border_subtle']};
            }}
            QFrame[numberInput="true"] QLineEdit {{
                color: {tokens['text_primary']};
            }}
            QFrame[numberInput="true"] QLineEdit:disabled {{
                color: {tokens['text_disabled']};
            }}
            QFrame[numberInput="true"] QLabel#numberInputSuffix {{
                background-color: transparent;
                border: none;
                color: {tokens['text_muted']};
                padding-right: 6px;
            }}
            QFrame[numberInput="true"] QToolButton {{
                background-color: transparent;
                border: none;
                color: {tokens['text_secondary']};
                font-size: 15px;
                font-weight: 600;
            }}
            QFrame[numberInput="true"] QToolButton:hover {{
                background-color: {tokens['surface_inset']};
                color: {tokens['text_primary']};
            }}
            QFrame[numberInput="true"] QToolButton:pressed {{
                background-color: {tokens['surface_chrome']};
            }}
            QFrame[numberInput="true"] QToolButton:disabled {{
                color: {tokens['text_disabled']};
            }}
            QFrame[numberInput="true"] QToolButton#numberInputDecrease {{
                border-right: 1px solid {tokens['border_subtle']};
                border-top-left-radius: {tokens['radius_control'] - 1}px;
                border-bottom-left-radius: {tokens['radius_control'] - 1}px;
            }}
            QFrame[numberInput="true"] QToolButton#numberInputIncrease {{
                border-left: 1px solid {tokens['border_subtle']};
                border-top-right-radius: {tokens['radius_control'] - 1}px;
                border-bottom-right-radius: {tokens['radius_control'] - 1}px;
            }}
        """

    def build_stylesheet(self, ctx: ThemeContext) -> str:
        tokens = self._tokens_for(ctx)
        accent = tokens["accent"]
        hover = tokens["accent_hover"]
        pressed = tokens["accent_pressed"]
        text_color = tokens["on_accent"]
        danger = tokens["status_danger"]
        danger_pressed = QColor(danger).darker(115).name()
        disabled_text_color = self._contrasting_text_color(QColor(tokens["accent_disabled"])).name()

        shared_widget_rules = f"""
            QFrame[card="true"] {{
                background-color: {tokens['surface_white']};
                border: 1px solid {tokens['border_subtle']};
                border-radius: {tokens['radius_card']}px;
            }}
            QFrame[card="true"][selected="true"] {{
                border: 2px solid {accent};
            }}
            QPushButton[segment="true"] {{
                border-top: none;
                border-right: none;
                border-bottom: none;
                border-left: 3px solid transparent;
                background-color: transparent;
                color: {tokens['text_muted']};
                padding: 4px 8px;
            }}
            QPushButton[segment="true"]:hover {{
                background-color: {tokens['surface_inset']};
            }}
            QPushButton[segment="true"][selected="true"] {{
                background-color: {tokens['accent_selected_bg']};
                color: {tokens['accent_active_text']};
                font-weight: 600;
            }}
            QPushButton[segment="true"][selected="true"][navActive="true"] {{
                border-left: 3px solid {accent};
            }}
            QPushButton[chip="true"] {{
                border: 1px solid {tokens['border_control']};
                border-radius: {tokens['radius_chip']}px;
                padding: 4px 10px;
                color: {tokens['text_secondary']};
                background-color: transparent;
            }}
            QPushButton[chip="true"]:hover {{
                background-color: {tokens['surface_inset']};
            }}
            QPushButton[chip="true"][selected="true"] {{
                background-color: {accent};
                color: {text_color};
                border-color: {accent};
            }}
            QPushButton[stepState="current"] {{
                border: none;
                font-weight: 700;
                color: {accent};
            }}
            QPushButton[stepState="completed"] {{
                border: none;
                font-weight: 600;
                color: {tokens['text_primary']};
            }}
            QPushButton[stepState="upcoming"] {{
                border: none;
                color: {tokens['text_muted']};
            }}
            {self._combo_box_rules(tokens, accent=accent, selected_text=text_color)}
            {self._number_input_rules(tokens, accent=accent)}
            QMessageBox QPushButton, QDialogButtonBox QPushButton {{
                color: {tokens['text_primary']};
                background-color: {tokens['surface_white']};
                border: 1px solid {tokens['border_control']};
                border-radius: {tokens['radius_control']}px;
                padding: 4px 14px;
                min-width: 70px;
            }}
            QMessageBox QPushButton:hover, QDialogButtonBox QPushButton:hover {{
                background-color: {tokens['surface_inset']};
            }}
            QPushButton[secondary="true"] {{
                background-color: transparent;
                border: 1px solid {tokens['border_control']};
                border-radius: {tokens['radius_control']}px;
                padding: 6px 14px;
                color: {tokens['text_secondary']};
            }}
            QPushButton[secondary="true"]:hover {{
                background-color: {tokens['surface_inset']};
            }}
            QPushButton[secondary="true"]:pressed {{
                background-color: {tokens['surface_chrome']};
            }}
            QPushButton[secondary="true"]:disabled {{
                border-color: {tokens['border_subtle']};
                color: {tokens['text_disabled']};
            }}
            QPushButton[destructive="true"] {{
                background-color: transparent;
                border: 1px solid {danger};
                border-radius: {tokens['radius_control']}px;
                padding: 6px 14px;
                color: {danger};
            }}
            QPushButton[destructive="true"]:hover {{
                background-color: {danger};
                color: {tokens['text_on_danger']};
            }}
            QPushButton[destructive="true"]:pressed {{
                background-color: {danger_pressed};
                color: {tokens['text_on_danger']};
            }}
            QPushButton[destructive="true"]:disabled {{
                border-color: {tokens['border_subtle']};
                color: {tokens['text_disabled']};
            }}
            QPushButton[iconButton="true"] {{
                border: none;
                background-color: transparent;
                padding: 4px;
                color: {tokens['text_muted']};
            }}
            QPushButton[iconButton="true"]:hover {{
                background-color: {tokens['surface_inset']};
            }}
            QPushButton[iconButton="true"][destructive="true"]:hover {{
                background-color: {danger};
                color: {tokens['text_on_danger']};
            }}
        """

        return f"""
            QPushButton[primary="true"] {{
                background-color: {accent};
                border: 1px solid {accent};
                border-radius: {tokens['radius_control']}px;
                padding: 6px 14px;
                font-weight: 600;
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
            QPushButton[primary="true"]:disabled {{
                background-color: {tokens['accent_disabled']};
                border-color: {tokens['accent_disabled']};
                color: {disabled_text_color};
            }}
            QTabBar::tab:selected {{ color: {accent}; }}
        """ + shared_widget_rules

    def _apply_to_qapp(self, ctx: ThemeContext) -> None:
        """Apply palette & global QSS to the QApplication.

        The automatic cyclic GC is paused meanwhile: these calls re-polish every live widget and run Python
        ``changeEvent`` overrides, and a GC pass that frees a stale parentless widget in the middle leaves Qt with a
        dangling pointer (rare segmentation fault in ``QApplication.setStyleSheet``, issue #648).
        """
        if not self._app:
            return
        with paused_garbage_collection():
            self._apply_theme_to_paused_qapp(ctx)

    def _apply_theme_to_paused_qapp(self, ctx: ThemeContext) -> None:
        palette = self._app.palette() if self._app else QPalette()
        if ctx.theme == Theme.DARK:
            bg = QColor(30, 30, 30)
            fg = QColor(224, 224, 224)
        else:
            bg = QColor(255, 255, 255)
            fg = QColor(0, 0, 0)
        # Controls the platform style draws itself (e.g. QWizard buttons on the Windows 11 style) follow Qt's colour scheme, which
        # defaults to the operating system's. Without this, a light app theme on a dark OS drew white text on white buttons.
        self._app.styleHints().setColorScheme(Qt.ColorScheme.Dark if ctx.theme == Theme.DARK else Qt.ColorScheme.Light)
        accent = QColor(ctx.accent)
        if not accent.isValid():
            accent = QColor(74, 86, 198)
        highlighted_text = QColor(self._tokens_for(ctx)["on_accent"])
        # Muted variant of fg, halfway to bg, so placeholder text is visibly
        # distinct from real text but still legible against the background.
        placeholder = QColor(
            (fg.red() + bg.red()) // 2,
            (fg.green() + bg.green()) // 2,
            (fg.blue() + bg.blue()) // 2,
        )

        palette.setColor(QPalette.ColorRole.Window, bg)
        palette.setColor(QPalette.ColorRole.WindowText, fg)
        palette.setColor(QPalette.ColorRole.Base, bg)
        palette.setColor(QPalette.ColorRole.Text, fg)
        palette.setColor(QPalette.ColorRole.Button, bg)
        palette.setColor(QPalette.ColorRole.ButtonText, fg)
        palette.setColor(QPalette.ColorRole.ToolTipBase, bg)
        palette.setColor(QPalette.ColorRole.ToolTipText, fg)
        palette.setColor(QPalette.ColorRole.BrightText, fg)
        palette.setColor(QPalette.ColorRole.PlaceholderText, placeholder)
        palette.setColor(QPalette.ColorRole.Highlight, accent)
        palette.setColor(QPalette.ColorRole.HighlightedText, highlighted_text)
        self._app.setPalette(palette)
        self._app.setStyleSheet(self.build_stylesheet(ctx))
        f = self._app.font()
        f.setPointSize(ctx.interface_font_size)
        self._app.setFont(f)

    def get_surface_palette(self) -> dict[str, str]:
        """Derived view over get_design_tokens() for callers that only need
        the original small 7-key shape -- kept as a single source of truth
        so the two can never drift out of sync (see get_design_tokens()).
        card_hover/card_pressed are derived from surface_white via
        QColor.darker() rather than reusing surface_inset/surface_chrome
        directly, since those tokens serve a different purpose (chrome/inset
        surfaces) and aren't guaranteed to sit in a monotonically-darkening
        order relative to each other. card_border is the quiet panel border
        (border_panel): it is also the background of the icon bar and the sidebar
        panel titles, where the 3:1 border_control would drop muted icons below
        their contrast."""
        tokens = self.get_design_tokens()
        bg = QColor(tokens["surface_white"])
        card_hover = bg.darker(110).name() if bg.isValid() else tokens["surface_inset"]
        card_pressed = bg.darker(115).name() if bg.isValid() else tokens["surface_chrome"]
        return {
            "card_bg": tokens["surface_white"],
            "card_hover": card_hover,
            "card_pressed": card_pressed,
            "card_border": tokens["border_panel"],
            "base_fg": tokens["text_primary"],
            "secondary_fg": tokens["text_secondary"],
            "accent": tokens["accent"],
        }

    def get_design_tokens(self) -> dict[str, Any]:
        """Return a fresh, mutable copy of the design tokens for the applied theme and accent (spec §5).

        Before any theme is applied this is the light theme with the default accent.
        """
        if self._current is None:
            return build_design_tokens(Theme.LIGHT, AppearanceConfig().accent_color)
        return build_design_tokens(self._current.theme, self._current.accent)

    def current_tokens(self) -> Mapping[str, Any]:
        """Return the cached, read-only design tokens for the applied theme.

        For painted widgets and the focus ring, which must not rebuild tokens on every paint. The cache is rebuilt
        whenever the applied `ThemeContext` changes.
        """
        key = None if self._current is None else (self._current.theme, self._current.accent)
        if self._frozen_tokens is None or self._frozen_tokens[0] != key:
            self._frozen_tokens = (key, freeze_tokens(self.get_design_tokens()))
        return self._frozen_tokens[1]

    def _tokens_for(self, ctx: ThemeContext) -> dict[str, Any]:
        """Tokens for `ctx`: `get_design_tokens()` when `ctx` is the applied context (so tests can patch it), else built."""
        if ctx is self._current:
            return self.get_design_tokens()
        return build_design_tokens(ctx.theme, ctx.accent)

    def build_context_menu_stylesheet(self) -> str:
        """Shared QSS for right-click context menus (dataset cell/column/row
        headers, project tree) -- kept separate from build_stylesheet()'s
        app-wide QPushButton rules since QMenu instances are styled
        per-instance rather than through the global QApplication stylesheet.
        """
        tokens = self.get_design_tokens()
        selected_text_color = tokens["on_accent"]
        return f"""
            QMenu {{
                background-color: {tokens['surface_white']};
                color: {tokens['text_primary']};
                border: 1px solid {tokens['border_control']};
            }}
            QMenu::item:selected {{
                background-color: {tokens['accent']};
                color: {selected_text_color};
            }}
        """

    def _on_config_event(self, data):  # signature per EventBus
        cfg = data.get("config")
        if cfg is None:
            return
        self.apply_from_config(cfg)


__all__ = ["ThemeContext", "ThemeManager"]
