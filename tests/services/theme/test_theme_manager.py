import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.models.state.config import Theme
from pandaplot.services.theme.theme_manager import ThemeContext, ThemeManager


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
    assert palette["card_hover"] == tokens["surface_inset"]
    assert palette["card_pressed"] == tokens["surface_chrome"]
    assert palette["card_border"] == tokens["border_control"]
    assert palette["base_fg"] == tokens["text_primary"]
    assert palette["secondary_fg"] == tokens["text_secondary"]
    assert palette["accent"] == tokens["accent"]


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
