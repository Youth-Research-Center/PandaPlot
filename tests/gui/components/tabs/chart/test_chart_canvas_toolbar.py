"""Regression tests for issue #511: the (x, y) mouse readout on the chart
toolbar must take a stable amount of space.

Matplotlib's stock readout is a `QLabel` whose size hint follows its text, so
every enter, move and leave across a length boundary re-laid-out the toolbar
and resized the canvas below it. The readout now reports a size that does not
depend on its text, elides what does not fit, and keeps to a single line.
"""
import pytest
import shiboken6
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from pandaplot.gui.components.tabs.chart.chart_canvas import ChartCanvas

EMPTY = ""
ONE_Y = "(x, y) = (1.234, 6.789)"
TWO_Y = "(x, y) = (1.234, 6.789) | (1.234, 6.789)"
WIDEST_TWO_Y = "(x, y) = (-1234.567, -1234.567) | (-1234.567, -1234.567)"
WITH_CURSOR_DATA = "(x, y) = (1.234, 6.789)\n[0.1 0.2 0.3]"
OVERFLOWING = "(x, y) = " + " | ".join(["(-123456789.123456, -123456789.123456)"] * 6)

MESSAGES = [EMPTY, ONE_Y, TWO_Y, WIDEST_TWO_Y, WITH_CURSOR_DATA, OVERFLOWING]


@pytest.fixture
def canvas(qtbot):
    canvas = ChartCanvas()
    qtbot.addWidget(canvas)
    return canvas


@pytest.fixture
def toolbar_row(qtbot, canvas):
    """The navigation toolbar laid out the way the chart editor does it: Fixed
    policy in a row, so its width is whatever its size hint says."""
    toolbar = canvas.navigation_toolbar
    host = QWidget()
    row = QHBoxLayout(host)
    row.setContentsMargins(0, 0, 0, 0)
    toolbar.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    row.addWidget(toolbar)
    toolbar.show()  # ChartCanvas keeps the toolbar hidden until a layout adopts it
    row.addStretch()
    qtbot.addWidget(host)
    host.resize(1200, 100)
    host.show()
    qtbot.waitExposed(host)
    return host, toolbar


def test_readout_size_hint_does_not_depend_on_text(canvas):
    toolbar = canvas.navigation_toolbar
    label = toolbar.readout_label
    toolbar.set_message(EMPTY)
    expected_hint = label.sizeHint()
    expected_minimum_hint = label.minimumSizeHint()

    for message in MESSAGES:
        toolbar.set_message(message)
        assert label.sizeHint() == expected_hint, repr(message)
        assert label.minimumSizeHint() == expected_minimum_hint, repr(message)


@pytest.mark.parametrize("themed", [False, True])
def test_toolbar_geometry_is_stable_while_the_readout_changes(qtbot, canvas, toolbar_row, themed):
    """The layout-level symptom of #511: the toolbar must neither resize nor
    move the label while the mouse enters, crosses and leaves the axes."""
    _, toolbar = toolbar_row
    if themed:
        canvas.apply_navigation_theme()
    label = toolbar.readout_label
    toolbar.set_message(EMPTY)
    qtbot.wait(10)
    expected = (toolbar.geometry(), label.geometry())

    for message in [*MESSAGES, EMPTY]:
        toolbar.set_message(message)
        qtbot.wait(10)
        assert (toolbar.geometry(), label.geometry()) == expected, repr(message)


def test_readout_shows_text_that_fits_unchanged(canvas):
    toolbar = canvas.navigation_toolbar
    for message in (ONE_Y, TWO_Y):
        toolbar.set_message(message)
        assert toolbar.readout_label.text() == message
        assert toolbar.readout_label.toolTip() == ""


def test_readout_elides_overflow_and_keeps_full_text_in_tooltip(qtbot, toolbar_row):
    _, toolbar = toolbar_row
    label = toolbar.readout_label
    toolbar.set_message(OVERFLOWING)
    qtbot.wait(10)

    shown = label.text()
    assert shown != OVERFLOWING
    assert shown.endswith("…")
    assert label.fontMetrics().horizontalAdvance(shown) <= label.contentsRect().width()
    assert label.toolTip() == OVERFLOWING


@pytest.mark.parametrize("message", [ONE_Y, TWO_Y, WIDEST_TWO_Y])
def test_readout_fits_the_two_y_axes_form_with_the_app_theme_applied(qtbot, canvas, toolbar_row, message):
    """The themed stylesheet pads the label; the reserved width must still be
    enough for the widest expected readout, so it is not elided needlessly."""
    _, toolbar = toolbar_row
    canvas.apply_navigation_theme()
    qtbot.wait(10)
    label = toolbar.readout_label

    toolbar.set_message(message)
    qtbot.wait(10)

    assert label.text() == message
    assert label.fontMetrics().horizontalAdvance(message) <= label.contentsRect().width()


def test_readout_flattens_cursor_data_onto_a_single_line(canvas):
    toolbar = canvas.navigation_toolbar
    toolbar.set_message(WITH_CURSOR_DATA)
    assert "\n" not in toolbar.readout_label.text()
    assert toolbar.readout_label.text() == "(x, y) = (1.234, 6.789) [0.1 0.2 0.3]"


def test_readout_clears_and_drops_tooltip_when_the_mouse_leaves(canvas):
    toolbar = canvas.navigation_toolbar
    toolbar.set_message(OVERFLOWING)
    toolbar.set_message(EMPTY)
    assert toolbar.readout_label.text() == ""
    assert toolbar.readout_label.toolTip() == ""


def test_readout_is_exposed_to_assistive_technology(canvas):
    assert canvas.navigation_toolbar.readout_label.accessibleName() == "Cursor position"


def test_toolbar_keeps_its_pan_zoom_and_save_actions(canvas):
    labels = {action.text() for action in canvas.navigation_toolbar.actions() if not action.isSeparator()}
    assert {"Pan", "Zoom", "Save"} <= labels
    assert not labels & {"Home", "Back", "Forward"}


def test_unplaced_toolbar_belongs_to_its_canvas_and_stays_hidden(qtbot):
    """Wizard previews never lay the toolbar out; it must neither paint over the preview nor outlive its canvas (#648)."""
    canvas = ChartCanvas()
    toolbar = canvas.navigation_toolbar
    menus = toolbar.findChildren(QWidget)

    assert toolbar.parent() is canvas
    canvas.show()
    qtbot.waitExposed(canvas)
    assert not toolbar.isVisible()
    canvas.hide()

    shiboken6.delete(canvas)

    assert not shiboken6.isValid(toolbar)
    assert not any(shiboken6.isValid(child) for child in menus)


def test_toolbar_shows_once_a_layout_adopts_it(toolbar_row):
    host, toolbar = toolbar_row

    assert toolbar.isVisible()
    assert toolbar.parent() is host
