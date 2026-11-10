from pathlib import Path

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.state.config import Theme
from pandaplot.services.config import ConfigManager
from pandaplot.services.theme.theme_manager import ThemeContext, ThemeManager


def _luminance(hex_color: str) -> float:
    c = QColor(hex_color)
    return (0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue()) / 255.0


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _manager_with_context(theme: Theme) -> ThemeManager:
    manager = ThemeManager.__new__(ThemeManager)
    manager._current = ThemeContext(theme=theme, accent="#4A56C6", interface_font_size=10)
    return manager


def test_get_design_tokens_light_has_status_danger():
    manager = _manager_with_context(Theme.LIGHT)
    tokens = manager.get_design_tokens()
    assert "status_danger" in tokens
    assert tokens["status_danger"] == "#DC3545"


def test_get_design_tokens_dark_has_status_danger():
    manager = _manager_with_context(Theme.DARK)
    tokens = manager.get_design_tokens()
    assert "status_danger" in tokens
    assert tokens["status_danger"] == "#C24141"


def test_build_stylesheet_includes_secondary_destructive_icon_selectors():
    manager = _manager_with_context(Theme.LIGHT)
    ctx = manager._current
    qss = manager.build_stylesheet(ctx)
    assert 'QPushButton[secondary="true"]' in qss
    assert 'QPushButton[destructive="true"]' in qss
    assert 'QPushButton[iconButton="true"]' in qss
    assert 'QPushButton[iconButton="true"][destructive="true"]:hover' in qss


def test_destructive_hover_and_pressed_text_use_the_text_on_danger_token():
    manager = _manager_with_context(Theme.LIGHT)
    tokens = {**manager.get_design_tokens(), "text_on_danger": "#123456"}
    manager.get_design_tokens = lambda: tokens

    qss = manager.build_stylesheet(manager._current)

    for selector in (
        'QPushButton[destructive="true"]:hover',
        'QPushButton[destructive="true"]:pressed',
        'QPushButton[iconButton="true"][destructive="true"]:hover',
    ):
        block = qss.split(selector + " {", 1)[1].split("}", 1)[0]
        assert "color: #123456;" in block, selector
        assert "#FFFFFF" not in block, selector


def test_build_stylesheet_includes_navactive_and_hover_selectors():
    manager = _manager_with_context(Theme.LIGHT)
    ctx = manager._current
    qss = manager.build_stylesheet(ctx)
    assert 'QPushButton[segment="true"][selected="true"][navActive="true"]' in qss
    assert 'QPushButton[segment="true"]:hover' in qss
    assert 'QPushButton[chip="true"]:hover' in qss


def test_build_stylesheet_primary_uses_shared_shape():
    manager = _manager_with_context(Theme.LIGHT)
    ctx = manager._current
    qss = manager.build_stylesheet(ctx)
    primary_rule = qss.split('QPushButton[primary="true"] {')[1].split("}")[0]
    assert "border-radius: 5px" in primary_rule
    assert "padding: 6px 14px" in primary_rule
    assert "font-weight: 600" in primary_rule


def test_build_stylesheet_primary_button_text_is_white_for_default_accent_in_light_theme():
    """User-reported: the default accent (#4A56C6) primary button showed
    black text in light theme. _contrasting_text_color()'s "light theme
    prefers black text down to luminance 0.25" heuristic picks black here
    (3.44:1 contrast) even though white gives 6.11:1 -- the same WCAG
    contrast bug already fixed for build_context_menu_stylesheet()'s
    selected-item text, present here too since both share
    _contrasting_text_color()."""
    manager = _manager_with_context(Theme.LIGHT)
    ctx = manager._current
    qss = manager.build_stylesheet(ctx)
    primary_rule = qss.split('QPushButton[primary="true"] {')[1].split("}")[0]
    assert "color: #ffffff;" in primary_rule.lower()


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_build_stylesheet_disabled_primary_button_text_is_legible(theme):
    """User-reported: a disabled primary button (e.g. an "Apply" button
    before there's anything to apply) rendered near-invisible text -- the
    disabled rule used tokens['text_hint'] (#9AA0AB) against
    tokens['accent_disabled'] (#7683FF for the default accent, same value
    in both themes) for only ~1.24:1 contrast, versus ~6.46:1 for black and
    ~3.25:1 for white. Must pick whichever of black/white actually
    contrasts against the disabled background, same as the enabled
    button's text color."""
    manager = _manager_with_context(theme)
    ctx = manager._current
    qss = manager.build_stylesheet(ctx)
    disabled_rule = qss.split('QPushButton[primary="true"]:disabled {')[1].split("}")[0]
    assert "color: #000000;" in disabled_rule.lower()


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_get_surface_palette_matches_design_tokens(theme):
    """get_surface_palette() must be a derived view over get_design_tokens(),
    not a separately-maintained dict -- this is what would have caught the
    card_border ('#404347') vs border_control ('#4A4D52') dark-theme mismatch
    that existed before this fix."""
    manager = _manager_with_context(theme)
    palette = manager.get_surface_palette()
    tokens = manager.get_design_tokens()

    assert palette["card_bg"] == tokens["surface_white"]
    assert palette["card_border"] == tokens["border_control"]
    assert palette["base_fg"] == tokens["text_primary"]
    assert palette["secondary_fg"] == tokens["text_secondary"]
    assert palette["accent"] == tokens["accent"]

    # card_bg -> card_hover -> card_pressed must be monotonically darkening
    # (press-feedback hierarchy relied on by ~30 call sites), in both themes.
    # This directly guards the regression where light-theme card_pressed
    # (derived from surface_chrome) ended up lighter than card_hover
    # (derived from surface_inset).
    bg_lum = _luminance(palette["card_bg"])
    hover_lum = _luminance(palette["card_hover"])
    pressed_lum = _luminance(palette["card_pressed"])
    assert bg_lum > hover_lum > pressed_lum


def test_design_tokens_has_font_size_group_title():
    manager = _manager_with_context(Theme.LIGHT)
    tokens = manager.get_design_tokens()
    assert tokens["font_size_group_title"] == 9


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_build_context_menu_stylesheet_uses_theme_tokens(theme):
    """Regression guard for the dark-theme bug where dataset/project context
    menus hardcoded a light-mode-only stylesheet (#ffffff/#0078d4/#e5f3ff)
    that never reacted to the app theme."""
    manager = _manager_with_context(theme)
    tokens = manager.get_design_tokens()
    qss = manager.build_context_menu_stylesheet()

    assert tokens["surface_white"] in qss
    assert tokens["border_control"] in qss
    assert tokens["accent"] in qss


def test_build_context_menu_stylesheet_selected_text_contrasts_with_accent():
    """Regression guard: the selected QMenu item's text color must be
    derived from the accent color via a real WCAG contrast-ratio
    comparison, not hardcoded to white (illegible for a light accent) and
    not _contrasting_text_color()'s theme-specific heuristic (which picks
    black for the default accent #4A56C6 in light theme -- 3.44:1 contrast,
    below the 4.5:1 minimum for normal text -- even though white gives
    6.11:1 there)."""
    manager = _manager_with_context(Theme.LIGHT)
    manager._current.accent = "#FFEB3B"  # light yellow accent
    qss = manager.build_context_menu_stylesheet()
    selected_rule = qss.split("QMenu::item:selected {")[1].split("}")[0]
    assert "color: #000000;" in selected_rule.lower()
    assert "#ffffff" not in selected_rule.lower()

    # The default accent (#4A56C6) has ~6.11:1 contrast against white and
    # only ~3.44:1 against black -- white must win, in BOTH themes, since
    # WCAG contrast doesn't depend on the app's light/dark theme setting.
    for theme in (Theme.LIGHT, Theme.DARK):
        manager = _manager_with_context(theme)
        manager._current.accent = "#4A56C6"
        qss = manager.build_context_menu_stylesheet()
        selected_rule = qss.split("QMenu::item:selected {")[1].split("}")[0]
        assert "color: #ffffff;" in selected_rule.lower(), (
            f"expected white text for default accent in {theme}, got: {selected_rule}"
        )


def _rule(qss: str, selector: str) -> str:
    return qss.split(f"{selector} {{")[1].split("}")[0]


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_build_stylesheet_styles_combo_boxes_from_design_tokens(theme):
    manager = _manager_with_context(theme)
    tokens = manager.get_design_tokens()
    qss = manager.build_stylesheet(manager._current)

    combo_rule = _rule(qss, "QComboBox")
    assert f"background-color: {tokens['surface_white']}" in combo_rule
    assert f"color: {tokens['text_primary']}" in combo_rule
    assert f"border: 1px solid {tokens['border_control']}" in combo_rule
    assert f"border-radius: {tokens['radius_control']}px" in combo_rule

    interactive_rule = _rule(qss, "QComboBox:hover, QComboBox:focus, QComboBox:on")
    assert f"border-color: {tokens['accent']}" in interactive_rule

    disabled_rule = _rule(qss, "QComboBox:disabled")
    assert f"background-color: {tokens['surface_inset']}" in disabled_rule
    assert f"color: {tokens['text_hint']}" in disabled_rule


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_build_stylesheet_supplies_a_caret_for_the_combo_box_arrow(theme):
    """Styling ::drop-down removes Qt's native arrow, so without an explicit
    image the field would show no sign that it opens a list."""
    manager = _manager_with_context(theme)
    qss = manager.build_stylesheet(manager._current)

    arrow_rule = _rule(qss, "QComboBox::down-arrow")
    assert 'image: url("' in arrow_rule
    assert "pandaplot_caret_" in arrow_rule
    assert "pandaplot_caret_" in _rule(qss, "QComboBox::down-arrow:disabled")
    assert _rule(qss, "QComboBox::down-arrow") != _rule(qss, "QComboBox::down-arrow:disabled")


def test_build_stylesheet_combo_popup_list_follows_the_theme():
    for theme in (Theme.LIGHT, Theme.DARK):
        manager = _manager_with_context(theme)
        tokens = manager.get_design_tokens()
        qss = manager.build_stylesheet(manager._current)

        popup_rule = _rule(qss, "QComboBox QAbstractItemView")
        assert f"background-color: {tokens['surface_white']}" in popup_rule
        assert f"border: 1px solid {tokens['border_control']}" in popup_rule
        assert f"selection-background-color: {tokens['accent']}" in popup_rule
        # Same legibility rule as the primary button: black or white,
        # whichever contrasts with the accent.
        assert "selection-color: #ffffff" in popup_rule.lower()


def test_build_stylesheet_combo_selection_text_contrasts_with_a_light_accent():
    manager = _manager_with_context(Theme.LIGHT)
    manager._current.accent = "#FFEB3B"
    qss = manager.build_stylesheet(manager._current)

    assert "selection-color: #000000" in _rule(qss, "QComboBox QAbstractItemView").lower()
    assert "color: #000000" in _rule(qss, "QComboBox QAbstractItemView::item:hover").lower()


class DummyFont:
    def __init__(self):
        self._pt = 10
    def setPointSize(self, pt):
        self._pt = pt

class DummyStyleHints:
    def __init__(self):
        self.color_scheme = None

    def setColorScheme(self, scheme):
        self.color_scheme = scheme


class DummyApp:
    """Minimal stub of QApplication for stylesheet & palette testing."""
    def __init__(self):
        from PySide6.QtGui import QPalette
        self._stylesheet = ""
        self._palette = QPalette()
        self._font = DummyFont()
        self._style_hints = DummyStyleHints()

    def styleHints(self):
        return self._style_hints

    def palette(self):
        return self._palette

    def font(self):
        return self._font

    def setFont(self, f):
        self._font = f

    def setPalette(self, palette):
        self._palette = palette

    def setStyleSheet(self, qss):
        self._stylesheet = qss

    def styleSheet(self):
        return self._stylesheet


def test_theme_manager_emits_on_config_events(tmp_path: Path):
    bus = EventBus()
    cfg_path = tmp_path / "cfg.json"
    cm = ConfigManager(bus, config_path=cfg_path, auto_save=False)
    tm = ThemeManager(bus, cm)
    app = DummyApp()
    tm.set_qt_app(app)

    emitted = []
    bus.subscribe("theme.changed", lambda d: emitted.append(d))

    # Trigger load event
    cm.load()
    assert emitted, "Theme change should occur on initial config load"
    emitted.clear()

    # Update config theme and ensure theme.changed fires
    cm.update({"appearance": {"theme": "light"}}, save=False)
    assert emitted, "Theme change should emit after config update"
    assert emitted[-1]["theme"] == Theme.LIGHT


def test_stylesheet_contains_accent_and_font(tmp_path: Path):
    bus = EventBus()
    cm = ConfigManager(bus, config_path=tmp_path / "c.json", auto_save=False)
    tm = ThemeManager(bus, cm)
    app = DummyApp()
    tm.set_qt_app(app)

    # Set explicit config values and apply
    cm.update({"appearance": {"accent_color": "#FF0000", "interface_font_size": 15}}, save=False)

    qss = app.styleSheet()
    assert "#FF0000" in qss
    # Font size applied to QApp font, not stylesheet
    assert app.font()._pt == 15


def test_stylesheet_forces_readable_text_on_dialog_buttons(tmp_path: Path):
    """QMessageBox/QDialogButtonBox OK/Cancel buttons render via the native
    Windows visual-styles API on windowsvista/windows11 styles, which colors
    button labels from the OS theme and ignores QPalette entirely. Only an
    explicit QSS rule forces Qt's palette-aware fallback painter."""
    bus = EventBus()
    cm = ConfigManager(bus, config_path=tmp_path / "c.json", auto_save=False)
    tm = ThemeManager(bus, cm)
    app = DummyApp()
    tm.set_qt_app(app)

    cm.update({"appearance": {"theme": "light"}}, save=False)
    qss = app.styleSheet()

    assert "QMessageBox QPushButton" in qss
    assert "QDialogButtonBox QPushButton" in qss
    # Light theme's text_primary token, so the rule actually forces dark text.
    assert "#1C1E26" in qss


def test_palette_sets_all_roles_for_light_theme(tmp_path: Path):
    from PySide6.QtGui import QPalette

    bus = EventBus()
    cm = ConfigManager(bus, config_path=tmp_path / "c.json", auto_save=False)
    tm = ThemeManager(bus, cm)
    app = DummyApp()
    tm.set_qt_app(app)

    cm.update({"appearance": {"theme": "light"}}, save=False)

    palette = app.palette()
    fg = palette.color(QPalette.ColorRole.WindowText)
    bg = palette.color(QPalette.ColorRole.Window)

    # Roles that must follow the app's fg/bg choice rather than the
    # OS-inherited default palette (root cause of white-on-white text).
    assert palette.color(QPalette.ColorRole.Button) == bg
    assert palette.color(QPalette.ColorRole.ButtonText) == fg
    assert palette.color(QPalette.ColorRole.ToolTipBase) == bg
    assert palette.color(QPalette.ColorRole.ToolTipText) == fg
    placeholder = palette.color(QPalette.ColorRole.PlaceholderText)
    assert placeholder != bg
    assert placeholder != fg


def test_idempotent_apply(tmp_path: Path):
    bus = EventBus()
    cm = ConfigManager(bus, config_path=tmp_path / "c.json", auto_save=False)
    tm = ThemeManager(bus, cm)
    app = DummyApp()
    tm.set_qt_app(app)

    cm.update({"appearance": {"theme": "dark"}}, save=False)
    first_qss = app.styleSheet()
    cm.update({"appearance": {"theme": "dark"}}, save=False)
    second_qss = app.styleSheet()
    assert first_qss == second_qss, "Applying same theme twice should produce same stylesheet"


def _real_app_theme_manager(tmp_path: Path, qapp):
    bus = EventBus()
    cm = ConfigManager(bus, config_path=tmp_path / "c.json", auto_save=False)
    tm = ThemeManager(bus, cm)
    tm.set_qt_app(qapp)
    return cm, tm


def test_qt_color_scheme_follows_the_app_theme(tmp_path: Path):
    """Platform-drawn controls (e.g. QWizard buttons on the Windows 11 style) follow Qt's colour scheme, not the app palette.

    With the OS in dark mode and the app theme light, they drew white text on the app's white button background. (A stub app
    is used because the offscreen platform ignores colour scheme requests.)
    """
    from PySide6.QtCore import Qt

    bus = EventBus()
    cm = ConfigManager(bus, config_path=tmp_path / "c.json", auto_save=False)
    tm = ThemeManager(bus, cm)
    app = DummyApp()
    tm.set_qt_app(app)

    cm.update({"appearance": {"theme": "light"}}, save=False)
    assert app.styleHints().color_scheme == Qt.ColorScheme.Light

    cm.update({"appearance": {"theme": "dark"}}, save=False)
    assert app.styleHints().color_scheme == Qt.ColorScheme.Dark

    cm.update({"appearance": {"theme": "light"}}, save=False)
    assert app.styleHints().color_scheme == Qt.ColorScheme.Light


def test_app_palette_survives_the_color_scheme_change(qapp, tmp_path: Path):
    from PySide6.QtGui import QColor, QPalette

    original_palette = qapp.palette()
    original_sheet = qapp.styleSheet()
    cm, _tm = _real_app_theme_manager(tmp_path, qapp)
    try:
        cm.update({"appearance": {"theme": "dark"}}, save=False)
        cm.update({"appearance": {"theme": "light"}}, save=False)

        palette = qapp.palette()
        assert palette.color(QPalette.ColorRole.ButtonText) == QColor(0, 0, 0)
        assert palette.color(QPalette.ColorRole.Button) == QColor(255, 255, 255)
    finally:
        qapp.styleHints().unsetColorScheme()
        qapp.setPalette(original_palette)
        qapp.setStyleSheet(original_sheet)
