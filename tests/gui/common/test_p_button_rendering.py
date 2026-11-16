import pytest
from PySide6.QtCore import QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QHBoxLayout, QWidget

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.models.state.config import Theme
from tests.gui.theme_testing import design_tokens, theme_manager_for


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _render_and_pick_color(app: QApplication, theme: Theme, role: str, *, icon: bool = False) -> str:
    manager = theme_manager_for(theme)
    assert manager._current is not None
    app.setStyleSheet(manager.build_stylesheet(manager._current))

    window = QWidget()
    layout = QHBoxLayout(window)
    button = PButton("X", role=role, icon=icon)
    layout.addWidget(button)
    window.resize(60, 40)
    window.show()
    app.processEvents()

    pixmap = window.grab()
    # Sample left of center so the label glyph (white text on Linux fonts) is never hit.
    point = button.mapTo(window, button.rect().center() - QPoint(button.width() // 2 - 8, 0))
    image = pixmap.toImage()
    return QColor(image.pixel(point.x(), point.y())).name()


def _token_color(theme: Theme, key: str) -> str:
    return QColor(design_tokens(theme)[key]).name()


def test_primary_renders_accent_color_light(qapp):
    assert _render_and_pick_color(qapp, Theme.LIGHT, "primary") == _token_color(Theme.LIGHT, "accent")


def test_primary_renders_accent_color_dark(qapp):
    assert _render_and_pick_color(qapp, Theme.DARK, "primary") == _token_color(Theme.DARK, "accent")


def test_secondary_does_not_render_accent_or_danger_color(qapp):
    color = _render_and_pick_color(qapp, Theme.LIGHT, "secondary")
    assert color not in (_token_color(Theme.LIGHT, "accent"), _token_color(Theme.LIGHT, "status_danger"))


def test_destructive_renders_danger_border_not_solid_fill_at_rest(qapp):
    # At rest (not hovered) destructive buttons are outlined, not filled —
    # the center pixel should NOT be the solid danger color.
    color = _render_and_pick_color(qapp, Theme.LIGHT, "destructive")
    assert color != _token_color(Theme.LIGHT, "status_danger")
