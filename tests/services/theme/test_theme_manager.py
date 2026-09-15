import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from pandaplot.models.state.config import Theme
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
