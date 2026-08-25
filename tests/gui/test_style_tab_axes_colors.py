"""Regression tests for two ordering bugs in StyleTab's Axes-section Colors card.

Both `load_chart_style` and `_on_copy_axis_style` must set match-toggle
checked state BEFORE loading/copying swatch colors. `ToggleSwitch.setChecked`
emits `toggled` unconditionally, and the toggled handler
(`_on_axis_style_match_x_colors_toggled`) pre-fills swatches from X's
*current* color whenever the new state is "not matching" -- doing colors
first would silently clobber a saved/just-copied custom color with X's.
"""
import types

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.style_tab import StyleTab
from pandaplot.models.project.items.chart import Chart


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_app_context():
    return types.SimpleNamespace(app_state=types.SimpleNamespace(current_project=None))


def test_load_preserves_custom_y_colors_when_not_matching_x():
    """Loading a chart where Y opted out of matching X's colors, with its
    own custom spine/tick colors saved, must NOT have those colors
    replaced by X's colors just because the chart loaded."""
    chart = Chart(name="Test Chart")
    chart.update_config({
        "x_spine_color": "#111111",
        "x_major_tick_color": "#111111",
        "x_minor_tick_color": "#111111",
        "x_tick_label_color": "#111111",
        "y_match_x_colors": False,
        "y_spine_color": "#abcdef",
        "y_major_tick_color": "#abcdef",
        "y_minor_tick_color": "#abcdef",
        "y_tick_label_color": "#abcdef",
    })

    tab = StyleTab(_make_app_context())
    tab.load_chart_style(chart)

    y_form = tab.axes_style_forms["y"]
    assert y_form["match_x_colors_toggle"].isChecked() is False
    assert y_form["spine_color_row"].currentColor() == "#abcdef"
    assert y_form["major_tick_color_row"].currentColor() == "#abcdef"
    assert y_form["minor_tick_color_row"].currentColor() == "#abcdef"
    assert y_form["tick_color_row"].currentColor() == "#abcdef"


def test_copy_axis_style_copies_source_colors_not_x_colors():
    """Copying Y2 (unmatched, with custom colors) into Y must leave Y with
    Y2's colors -- not X's -- even though copying flips Y's match toggle."""
    chart = Chart(name="Test Chart")
    chart.update_config({
        "x_spine_color": "#111111",
        "x_major_tick_color": "#111111",
        "x_minor_tick_color": "#111111",
        "x_tick_label_color": "#111111",
        "y2_match_x_colors": False,
        "y2_spine_color": "#00ff00",
        "y2_major_tick_color": "#00ff00",
        "y2_minor_tick_color": "#00ff00",
        "y2_tick_label_color": "#00ff00",
        # Y starts out matching X (default), which is the state being
        # flipped away from during the copy.
    })
    chart.add_data_series(dataset_id="ds1", x_column="x", y_column="y", y_axis="secondary")

    tab = StyleTab(_make_app_context())
    tab.load_chart_style(chart)

    # Sanity check: Y starts out matching X, as loaded.
    y_form = tab.axes_style_forms["y"]
    assert y_form["match_x_colors_toggle"].isChecked() is True

    tab._on_copy_axis_style("y2")

    assert y_form["match_x_colors_toggle"].isChecked() is False
    assert y_form["spine_color_row"].currentColor() == "#00ff00"
    assert y_form["major_tick_color_row"].currentColor() == "#00ff00"
    assert y_form["minor_tick_color_row"].currentColor() == "#00ff00"
    assert y_form["tick_color_row"].currentColor() == "#00ff00"
