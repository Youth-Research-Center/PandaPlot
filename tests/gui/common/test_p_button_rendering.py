import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.models.state.config import Theme
from pandaplot.services.theme.theme_manager import ThemeContext, ThemeManager


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _render_and_pick_color(app: QApplication, theme: Theme, role: str, *, icon: bool = False) -> str:
    manager = ThemeManager.__new__(ThemeManager)
    ctx = ThemeContext(theme=theme, accent="#4A56C6", interface_font_size=10)
    manager._current = ctx
    app.setStyleSheet(manager.build_stylesheet(ctx))

    window = QWidget()
    layout = QHBoxLayout(window)
    button = PButton("X", role=role, icon=icon)
    layout.addWidget(button)
    window.resize(60, 40)
    window.show()
    app.processEvents()

    pixmap = window.grab()
    point = button.mapTo(window, button.rect().center())
    image = pixmap.toImage()
    return QColor(image.pixel(point.x(), point.y())).name()


def test_primary_renders_accent_color_light(qapp):
    assert _render_and_pick_color(qapp, Theme.LIGHT, "primary") == "#4a56c6"


def test_primary_renders_accent_color_dark(qapp):
    assert _render_and_pick_color(qapp, Theme.DARK, "primary") == "#4a56c6"


def test_secondary_does_not_render_accent_or_danger_color(qapp):
    color = _render_and_pick_color(qapp, Theme.LIGHT, "secondary")
    assert color not in ("#4a56c6", "#dc3545")


def test_destructive_renders_danger_border_not_solid_fill_at_rest(qapp):
    # At rest (not hovered) destructive buttons are outlined, not filled —
    # the center pixel should NOT be the solid danger color.
    color = _render_and_pick_color(qapp, Theme.LIGHT, "destructive")
    assert color != "#dc3545"
