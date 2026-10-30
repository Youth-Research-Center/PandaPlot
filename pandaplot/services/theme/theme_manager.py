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
from dataclasses import dataclass

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.events.event_types import ConfigEvents, ThemeEvents
from pandaplot.models.state.config import ApplicationConfig, Theme
from pandaplot.services.theme.caret_icon import caret_icon_path

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ThemeContext:
    """Snapshot of theme-relevant config values."""

    theme: Theme
    accent: str
    interface_font_size: int


class ThemeManager:
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

    @staticmethod
    def _relative_luminance(color: QColor) -> float:
        """WCAG 2.x relative luminance (gamma-corrected per channel)."""
        def channel(v: int) -> float:
            c = v / 255.0
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

        r, g, b = channel(color.red()), channel(color.green()), channel(color.blue())
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    @classmethod
    def _contrasting_text_color(cls, accent: QColor) -> QColor:
        """Pick whichever of black/white has the higher WCAG contrast ratio
        against `accent`, so it stays legible regardless of the app's
        light/dark theme setting -- theme doesn't affect how legible text
        is against a given background color.

        Previously branched on theme too ("light theme prefers black text
        down to luminance 0.25"), which picked black for the default accent
        (#4A56C6) in light theme -- 3.44:1 contrast, below the WCAG 4.5:1
        minimum for normal text -- even though white gives 6.11:1 there.
        Reported live on the primary button; the same bug was independently
        found and fixed for the context-menu selected-item text, but that
        fix was scoped to a separate helper to avoid touching this method's
        other call sites without evidence they were also affected. They
        were -- so this replaces the heuristic here instead of duplicating
        the correct logic a third time.
        """
        lum = cls._relative_luminance(accent)
        white_contrast = (1.0 + 0.05) / (lum + 0.05)
        black_contrast = (lum + 0.05) / (0.0 + 0.05)
        return QColor(255, 255, 255) if white_contrast >= black_contrast else QColor(0, 0, 0)

    @staticmethod
    def _combo_box_rules(tokens: dict, *, accent: str, selected_text: str) -> str:
        """QSS for the app-wide dropdown (QComboBox) style.

        Every combo box -- sidebar panels, dialogs and wizards -- gets this one
        look, so a dialog must not restyle ``QComboBox`` itself. Where the list
        opens is not a stylesheet matter (macOS opens a native menu over the
        field whatever the QSS says); ``DropDownComboBox`` takes care of that.
        Styling ``::drop-down`` removes Qt's own arrow, so a caret in the
        theme's muted text colour is supplied (a hint-coloured one while
        disabled).

        Args:
            tokens: Design tokens from ``get_design_tokens()``.
            accent: Accent colour used for the hover/focus border and selection.
            selected_text: Legible text colour on top of ``accent``.

        Returns:
            The QSS block for ``QComboBox`` and its popup list.
        """
        caret = caret_icon_path(tokens["text_muted"])
        caret_disabled = caret_icon_path(tokens["text_hint"])
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
                color: {tokens['text_hint']};
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
    def _number_input_rules(tokens: dict, *, accent: str) -> str:
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
                color: {tokens['text_hint']};
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
                color: {tokens['text_hint']};
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
        accent = ctx.accent
        text_color = "#000000"  # fallback
        hover = accent
        pressed = accent
        try:
            c = QColor(accent)
            if c.isValid():
                # Derive hover / pressed variants
                hover = c.lighter(110).name()
                pressed = c.darker(115).name()
                text_color = self._contrasting_text_color(c).name()
        except Exception:
            logger.debug("Could not derive hover/pressed/text colors from accent %r; using fallback", accent, exc_info=True)

        tokens = self.get_design_tokens()
        danger = tokens["status_danger"]
        danger_pressed = danger
        try:
            dc = QColor(danger)
            if dc.isValid():
                danger_pressed = dc.darker(115).name()
        except Exception:
            logger.debug("Could not derive danger_pressed color from %r; using fallback", danger, exc_info=True)

        # accent_disabled is a lightened, still fairly saturated variant of
        # accent (e.g. #7683FF for the default #4A56C6) -- text_hint (a
        # muted gray meant for text on a plain surface) has only ~1.2:1
        # contrast against it, effectively invisible. Same fix as the
        # enabled button: pick whichever of black/white actually contrasts.
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
                color: #FFFFFF;
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
                color: {tokens['text_hint']};
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
                color: #FFFFFF;
            }}
            QPushButton[destructive="true"]:pressed {{
                background-color: {danger_pressed};
                color: #FFFFFF;
            }}
            QPushButton[destructive="true"]:disabled {{
                border-color: {tokens['border_subtle']};
                color: {tokens['text_hint']};
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
                color: #FFFFFF;
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
        accent = QColor(ctx.accent)
        if not accent.isValid():
            accent = QColor(74, 86, 198)
        highlighted_text = self._contrasting_text_color(accent)
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

    def get_surface_palette(self) -> dict:
        """Derived view over get_design_tokens() for callers that only need
        the original small 7-key shape -- kept as a single source of truth
        so the two can never drift out of sync (see get_design_tokens()).
        card_hover/card_pressed are derived from surface_white via
        QColor.darker() rather than reusing surface_inset/surface_chrome
        directly, since those tokens serve a different purpose (chrome/inset
        surfaces) and aren't guaranteed to sit in a monotonically-darkening
        order relative to each other."""
        tokens = self.get_design_tokens()
        bg = QColor(tokens["surface_white"])
        card_hover = bg.darker(110).name() if bg.isValid() else tokens["surface_inset"]
        card_pressed = bg.darker(115).name() if bg.isValid() else tokens["surface_chrome"]
        return {
            "card_bg": tokens["surface_white"],
            "card_hover": card_hover,
            "card_pressed": card_pressed,
            "card_border": tokens["border_control"],
            "base_fg": tokens["text_primary"],
            "secondary_fg": tokens["text_secondary"],
            "accent": tokens["accent"],
        }

    def get_design_tokens(self) -> dict:
        """Full token set for the chart-properties redesign's shared widgets.

        get_surface_palette() is a derived view over this method's return
        value, not a separate dict -- this is the single source of truth.
        """
        accent = self._current.accent if self._current else "#4A56C6"
        is_dark = self._current is not None and self._current.theme == Theme.DARK

        c = QColor(accent)
        accent_active_text = c.darker(115).name() if c.isValid() else accent
        accent_disabled = c.lighter(140).name() if c.isValid() else "#AAB1E3"

        if is_dark:
            return {
                "text_primary": "#E2E2E2", "text_secondary": "#C7CAD1",
                "text_muted": "#9AA0AB", "text_hint": "#6B7280", "text_disabled": "#5B6270",
                "border_panel": "#3A3D40", "border_control": "#4A4D52",
                "border_subtle": "#33363A",
                "surface_white": "#2A2C2E", "surface_chrome": "#232527",
                "surface_inset": "#26282B",
                "accent": accent, "accent_active_text": accent_active_text,
                "accent_selected_bg": "#2E3350", "accent_disabled": accent_disabled,
                "status_modified_dot": "#E09A1F", "status_modified_text": "#E0A94A",
                "status_success": "#3FA46A", "status_danger": "#C24141",
                "y2_accent": "#B27FD1", "y2_accent_bg": "#3A2E45",
                "series_palette": ["#C24141", "#6B77E8", "#3F9BB0", "#3FA46A", "#E09A1F"],
                "radius_swatch": 4, "radius_control": 5, "radius_card": 6, "radius_chip": 12,
                "font_size_group_title": 9,
            }
        return {
            "text_primary": "#1C1E26", "text_secondary": "#3F4350",
            "text_muted": "#6B7280", "text_hint": "#9AA0AB", "text_disabled": "#AEB2BC",
            "border_panel": "#E5E6EA", "border_control": "#DCDEE4",
            "border_subtle": "#ECEEF2",
            "surface_white": "#FFFFFF", "surface_chrome": "#FBFBFC",
            "surface_inset": "#F4F5F8",
            "accent": accent, "accent_active_text": accent_active_text,
            "accent_selected_bg": "#EEF0FB", "accent_disabled": accent_disabled,
            "status_modified_dot": "#E09A1F", "status_modified_text": "#B06A00",
            "status_success": "#3FA46A", "status_danger": "#DC3545",
            "y2_accent": "#8A4BB8", "y2_accent_bg": "#F5EEFB",
            "series_palette": ["#A01818", "#4A56C6", "#2B7A8C", "#3FA46A", "#E09A1F"],
            "radius_swatch": 4, "radius_control": 5, "radius_card": 6, "radius_chip": 12,
            "font_size_group_title": 9,
        }

    def build_context_menu_stylesheet(self) -> str:
        """Shared QSS for right-click context menus (dataset cell/column/row
        headers, project tree) -- kept separate from build_stylesheet()'s
        app-wide QPushButton rules since QMenu instances are styled
        per-instance rather than through the global QApplication stylesheet.
        """
        tokens = self.get_design_tokens()
        selected_text_color = self._contrasting_text_color(QColor(tokens["accent"])).name()
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
