"""SidebarPanel: the shared look and layout every sidebar panel inherits.

The panel background, group boxes, title bar and result text areas used to be
styled by a near-identical stylesheet copied into each panel's _apply_theme()
(and had drifted: padding, missing background rule, hard-coded colours). They
are now styled once by ThemeManager, keyed on the ``sidebarPanel`` property
that SidebarPanel sets, and laid out with shared helpers.
"""
import ast
from pathlib import Path
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QComboBox, QGroupBox, QLabel, QPlainTextEdit, QTextEdit, QVBoxLayout, QWidget

from pandaplot.gui.components.common.label_role import set_error_state, set_label_role
from pandaplot.gui.components.sidebar.panels.panel_form_layout import (
    COMBO_MINIMUM_CONTENTS_LENGTH,
    FORM_HORIZONTAL_SPACING,
    FORM_VERTICAL_SPACING,
    PanelFormLayout,
    compact_combo,
)
from pandaplot.gui.components.sidebar.panels.sidebar_panel import (
    CONTENT_MARGIN,
    SECTION_SPACING,
    TITLE_OBJECT_NAME,
    SidebarPanel,
)
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.config import Theme
from pandaplot.services.theme.theme_manager import ThemeContext, ThemeManager

SIDEBAR_ROOT = Path(__file__).resolve().parents[5] / "pandaplot" / "gui" / "components" / "sidebar"


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def themed():
    """Style one widget with the real ThemeManager stylesheet for a theme.

    The stylesheet is set on the widget, not on the QApplication: an
    application-wide change re-polishes every widget other tests have left
    alive, which makes these tests take seconds each.
    """

    def apply(widget: QWidget, theme: Theme) -> dict:
        manager = ThemeManager.__new__(ThemeManager)
        manager._current = ThemeContext(theme=theme, accent="#4A56C6", interface_font_size=10)
        widget.setStyleSheet(manager.build_stylesheet(manager._current))
        return manager.get_design_tokens()

    return apply


class _Panel(SidebarPanel):
    """Smallest real panel: a title and a scrollable content area with one group."""

    def __init__(self, app_context):
        super().__init__(app_context)
        self._initialize()

    def _init_ui(self):
        self._init_panel_layout()
        self._set_title("Title")
        content = QWidget()
        layout = self._new_content_layout(content)
        self.group = QGroupBox("Group")
        group_layout = PanelFormLayout(self.group)
        self.combo = QComboBox()
        self.combo.addItem("A very long dataset name that would widen the whole panel")
        group_layout.addRow("Dataset:", self.combo)
        self.results = QTextEdit()
        group_layout.addRow(self.results)
        layout.addWidget(self.group)
        self._set_content(content, scrollable=False)
        self.content_layout = layout

    def _apply_theme(self):
        pass


@pytest.fixture
def panel():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    widget = _Panel(ctx)
    yield widget
    widget.close()


# -- the SidebarPanel contract ----------------------------------------------------


def test_panel_marks_itself_for_the_shared_stylesheet(panel):
    assert panel.property("sidebarPanel") is True
    assert panel.testAttribute(Qt.WidgetAttribute.WA_StyledBackground)


def test_title_label_is_findable_by_the_shared_stylesheet(panel):
    assert panel.title_label is not None
    assert panel.title_label.objectName() == TITLE_OBJECT_NAME


def test_content_layout_has_the_same_margin_and_spacing_in_every_panel(panel):
    layout = panel.content_layout

    assert isinstance(layout, QVBoxLayout)
    assert layout.contentsMargins().left() == layout.contentsMargins().top() == CONTENT_MARGIN
    assert layout.contentsMargins().right() == layout.contentsMargins().bottom() == CONTENT_MARGIN
    assert layout.spacing() == SECTION_SPACING


def test_panels_no_longer_carry_their_own_title_or_group_styles(panel):
    assert panel.styleSheet() == ""
    assert panel.title_label.styleSheet() == ""


# -- shared form layout ----------------------------------------------------------


def test_form_layout_aligns_labels_left_and_lets_fields_fill_the_row(panel):
    form = panel.group.layout()

    assert isinstance(form, PanelFormLayout)
    assert form.labelAlignment() & Qt.AlignmentFlag.AlignLeft
    assert form.fieldGrowthPolicy() == PanelFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
    assert form.rowWrapPolicy() == PanelFormLayout.RowWrapPolicy.DontWrapRows
    assert form.horizontalSpacing() == FORM_HORIZONTAL_SPACING
    assert form.verticalSpacing() == FORM_VERTICAL_SPACING


def test_combo_added_to_a_form_row_can_shrink_below_its_longest_item(panel):
    combo = panel.combo

    assert combo.sizeAdjustPolicy() == QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    assert combo.minimumContentsLength() == COMBO_MINIMUM_CONTENTS_LENGTH
    assert combo.minimumSizeHint().width() < combo.fontMetrics().horizontalAdvance(combo.itemText(0))


def test_a_long_item_does_not_widen_the_panel(panel):
    panel.resize(300, 300)
    panel.show()
    QApplication.processEvents()

    assert panel.minimumSizeHint().width() <= 300


def test_compact_combo_helper_works_on_a_standalone_combo():
    plain = QComboBox()
    plain.addItem("x" * 80)
    compact = QComboBox()
    compact.addItem("x" * 80)

    compact_combo(compact)

    assert compact.minimumSizeHint().width() < plain.minimumSizeHint().width()


def test_form_rows_without_a_combo_are_added_unchanged(panel):
    form = panel.group.layout()
    label = QLabel("Plain")
    form.addRow("Text:", label)

    assert form.rowCount() == 3
    assert form.itemAt(2, PanelFormLayout.ItemRole.FieldRole).widget() is label


# -- label roles -----------------------------------------------------------------


def test_set_label_role_sets_and_clears_the_property():
    label = QLabel("hint")

    set_label_role(label, "hint")
    assert label.property("role") == "hint"
    set_label_role(label, None)

    assert label.property("role") == ""


@pytest.mark.parametrize("area_type", [QTextEdit, QPlainTextEdit])
def test_set_error_state_toggles_the_error_property(area_type):
    area = area_type()

    set_error_state(area, error=True)
    assert area.property("error") is True
    set_error_state(area, error=False)

    assert area.property("error") is False


# -- rendering -------------------------------------------------------------------


def _pixel(widget: QWidget, x: int, y: int) -> str:
    return QColor(widget.grab().toImage().pixel(x, y)).name()


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_group_box_and_text_area_borders_come_from_the_theme(themed, panel, theme):
    tokens = themed(panel, theme)
    panel.resize(320, 360)
    panel.show()
    QApplication.processEvents()
    area = panel.results
    host = panel
    origin = area.mapTo(host, area.rect().topLeft())
    middle = origin.y() + area.height() // 2

    assert _pixel(host, origin.x(), middle) == QColor(tokens["border_control"]).name()


@pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK])
def test_title_bar_uses_the_theme_border_color_as_its_background(themed, panel, theme):
    tokens = themed(panel, theme)
    panel.resize(320, 360)
    panel.show()
    QApplication.processEvents()
    title = panel.title_label
    point = title.mapTo(panel, title.rect().topRight())

    assert _pixel(panel, point.x() - 6, point.y() + title.height() // 2) == QColor(tokens["border_control"]).name()


def test_error_text_area_is_drawn_in_the_danger_colour(themed, panel):
    tokens = themed(panel, Theme.LIGHT)
    panel.resize(320, 360)
    panel.show()
    set_error_state(panel.results, error=True)
    panel.results.setPlainText("Fit did not converge")
    QApplication.processEvents()

    # The text colour is what the widget actually resolves to, not just what a
    # rule says: a pixel in the glyphs would depend on the font, so read the
    # style sheet's effect through the palette Qt computed for the widget.
    assert panel.results.property("error") is True
    resolved = panel.results.palette().color(panel.results.foregroundRole()).name()
    assert resolved == QColor(tokens["status_danger"]).name()


# -- no drift ---------------------------------------------------------------------


def _panel_sources():
    return sorted(path for path in SIDEBAR_ROOT.rglob("*_panel.py") if "__pycache__" not in path.parts)


def test_panel_modules_do_not_restyle_group_boxes_or_titles():
    """The shared look lives in ThemeManager; a per-panel copy drifts."""
    offenders = []
    for path in _panel_sources():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            is_qss = isinstance(node, ast.Constant) and isinstance(node.value, str) and "{" in node.value
            if is_qss and ("QGroupBox" in node.value or "sidebarPanelTitle" in node.value):
                offenders.append(f"{path.relative_to(SIDEBAR_ROOT.parent.parent.parent.parent)}:{node.lineno}")

    assert offenders == [], f"group box / title QSS belongs in ThemeManager._sidebar_panel_rules: {offenders}"


def test_panel_modules_do_not_hardcode_status_colors():
    """Hard-coded ``color: red`` ignored the theme (and dark mode)."""
    offenders = []
    for path in _panel_sources():
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if "color: red" in line or '"red"' in line:
                offenders.append(f"{path.name}:{number}: {line.strip()}")

    assert offenders == [], f"use set_label_role(..., 'error') / set_error_state(): {offenders}"


def test_panel_modules_use_the_shared_form_layout():
    offenders = []
    for path in _panel_sources():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "QFormLayout":
                offenders.append(f"{path.name}:{node.lineno}")

    assert offenders == [], f"use PanelFormLayout so rows line up across panels: {offenders}"
