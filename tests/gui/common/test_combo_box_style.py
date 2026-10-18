"""Every dropdown in the app shares one look and one popup behaviour.

The look comes from ThemeManager's app-wide QComboBox rules and the popup
placement from DropDownComboBox, so a dropdown built from a bare QComboBox, or
a dialog that restyles QComboBox for itself, breaks the consistency.
"""
import ast
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QComboBox, QVBoxLayout, QWidget

from pandaplot.gui.components.common.drop_down_combo_box import DropDownComboBox
from pandaplot.gui.components.common.value_combo_box import ValueComboBox
from pandaplot.models.state.config import Theme
from pandaplot.services.theme.theme_manager import ThemeContext, ThemeManager

PACKAGE_ROOT = Path(__file__).resolve().parents[3] / "pandaplot"
THEME_MANAGER = PACKAGE_ROOT / "services" / "theme" / "theme_manager.py"


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def themed_app(qapp):
    """Apply the real app-wide stylesheet for a theme, restoring it afterwards."""
    original_sheet = qapp.styleSheet()
    original_palette = qapp.palette()

    def apply(theme: Theme) -> dict:
        manager = ThemeManager.__new__(ThemeManager)
        manager._current = ThemeContext(theme=theme, accent="#4A56C6", interface_font_size=10)
        qapp.setStyleSheet(manager.build_stylesheet(manager._current))
        return manager.get_design_tokens()

    try:
        yield apply
    finally:
        qapp.setStyleSheet(original_sheet)
        qapp.setPalette(original_palette)


def _production_sources() -> list[Path]:
    return sorted(path for path in PACKAGE_ROOT.rglob("*.py") if "__pycache__" not in path.parts)


def test_production_code_never_instantiates_a_bare_qcombobox():
    """A bare QComboBox opens as a native menu over the field on macOS."""
    offenders = []
    for path in _production_sources():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "QComboBox":
                offenders.append(f"{path.relative_to(PACKAGE_ROOT.parent)}:{node.lineno}")

    assert offenders == [], f"use DropDownComboBox instead of QComboBox(): {offenders}"


def test_only_the_theme_manager_styles_combo_boxes():
    """A dialog-level QComboBox rule overrides the shared one, so every
    dialog drifted to its own radius, padding and background."""
    offenders = []
    for path in _production_sources():
        if path == THEME_MANAGER:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            # Stylesheet text: a string that names QComboBox next to a rule body.
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and "QComboBox" in node.value and "{" in node.value:
                offenders.append(f"{path.relative_to(PACKAGE_ROOT.parent)}:{node.lineno}")

    assert offenders == [], f"QComboBox QSS belongs in ThemeManager: {offenders}"


def test_value_combo_box_is_a_drop_down_combo_box():
    assert issubclass(ValueComboBox, DropDownComboBox)


def test_value_combo_box_popup_opens_below_the_field():
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = ValueComboBox([("One", 1), ("Two", 2), ("Three", 3)])
    layout.addWidget(combo)
    host.move(200, 300)
    host.resize(300, 120)
    host.show()
    QApplication.processEvents()
    try:
        combo.showPopup()
        QApplication.processEvents()

        popup_top = combo.view().window().mapToGlobal(combo.view().window().rect().topLeft())
        field_bottom = combo.mapToGlobal(combo.rect().bottomLeft())
        assert popup_top.y() >= field_bottom.y() - 2
    finally:
        combo.hidePopup()
        host.close()


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_combo_box_renders_the_shared_field_style(themed_app, theme):
    tokens = themed_app(theme)
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = DropDownComboBox()
    combo.addItems(["Alpha", "Beta"])
    combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    layout.addWidget(combo)
    host.resize(240, 80)
    host.show()
    QApplication.processEvents()
    try:
        image = host.grab().toImage()
        field = combo.geometry()
        middle = field.top() + field.height() // 2
        # Just inside the left border, clear of the text, and on the border itself.
        inside = QColor(image.pixel(field.left() + 4, middle)).name()
        border = QColor(image.pixel(field.left(), middle)).name()

        assert inside == QColor(tokens["surface_white"]).name()
        assert border == QColor(tokens["border_control"]).name()
    finally:
        host.close()


def test_disabled_combo_box_is_visibly_inset(themed_app):
    tokens = themed_app(Theme.LIGHT)
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = DropDownComboBox()
    combo.addItems(["Alpha"])
    combo.setEnabled(False)
    combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    layout.addWidget(combo)
    host.resize(240, 80)
    host.show()
    QApplication.processEvents()
    try:
        image = host.grab().toImage()
        field = combo.geometry()
        inside = QColor(image.pixel(field.left() + 4, field.top() + field.height() // 2)).name()

        assert inside == QColor(tokens["surface_inset"]).name()
    finally:
        host.close()


def test_plain_qcombobox_is_still_styled_by_the_shared_rules(themed_app):
    """Third-party widgets that embed a QComboBox pick up the same look."""
    tokens = themed_app(Theme.LIGHT)
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = QComboBox()
    combo.addItems(["Alpha"])
    combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    layout.addWidget(combo)
    host.resize(240, 80)
    host.show()
    QApplication.processEvents()
    try:
        image = host.grab().toImage()
        field = combo.geometry()
        border = QColor(image.pixel(field.left(), field.top() + field.height() // 2)).name()

        assert border == QColor(tokens["border_control"]).name()
    finally:
        host.close()


def test_focused_combo_box_is_outlined_in_the_accent_colour(themed_app):
    tokens = themed_app(Theme.LIGHT)
    host = QWidget()
    layout = QVBoxLayout(host)
    combo = DropDownComboBox()
    combo.addItems(["Alpha"])
    layout.addWidget(combo)
    host.resize(240, 80)
    host.show()
    host.activateWindow()
    combo.setFocus(Qt.FocusReason.TabFocusReason)
    QApplication.processEvents()
    try:
        image = host.grab().toImage()
        field = combo.geometry()
        border = QColor(image.pixel(field.left(), field.top() + field.height() // 2)).name()

        assert combo.hasFocus()
        assert border == QColor(tokens["accent"]).name()
    finally:
        host.close()
