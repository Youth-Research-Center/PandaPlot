"""Regression tests for AxesTab (axes_tab.py).

Note: the ordering-bug regression tests for the Colors card's Match-X
toggle (spine/major/minor tick colors) moved to
tests/gui/test_style_tab_axes_colors.py as of Task 6, since that Colors
card itself moved from AxesTab into StyleTab's "Axes" section.
"""
import types

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.axes_tab import AxesTab
from pandaplot.models.chart.chart_configuration import ScaleType
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_app_context(project=None):
    """Minimal stand-in exposing the one attribute AxesTab reads:
    `app_context.app_state.current_project` (consulted by
    `_refresh_range_display`). None here means `compute_axis_data_range`
    can't resolve any series and falls back to (0.0, 1.0), which is fine
    since these tests don't assert on the Range card's min/max values."""
    return types.SimpleNamespace(app_state=types.SimpleNamespace(current_project=project))


class _FakeProject:
    """Minimal stand-in for a project, exposing only the `find_item` lookup
    `compute_axis_data_range` -> `resolve_series_data` needs."""

    def __init__(self, datasets):
        self._datasets = {d.id: d for d in datasets}

    def find_item(self, item_id):
        return self._datasets.get(item_id)


def _make_dataset(id_, x, y):
    import pandas as pd
    ds = Dataset(id=id_, name=id_)
    ds.data = pd.DataFrame({"x": x, "y": y})
    return ds


def test_selecting_custom_log_base_reveals_spin_and_round_trips_into_config():
    """Selecting "Custom..." on the log-base combo reveals the custom spin
    box, and the spin box's value round-trips into
    chart.config[f"{prefix}_log_base"] via the real _on_field_changed ->
    _write_axis_config -> _resolve_log_base path."""
    chart = Chart(name="Test Chart")
    chart.update_config({"y_scale": "log"})

    tab = AxesTab(_make_app_context())
    tab.load(chart)

    y_form = tab.axes_forms["y"]
    custom_index = y_form["log_base_combo"].findData("custom")
    y_form["log_base_combo"].setCurrentIndex(custom_index)

    assert y_form["log_base_custom_spin"].isHidden() is False

    y_form["log_base_custom_spin"].setValue(4.2)

    assert chart.config["y_log_base"] == 4.2


def test_log_base_of_one_falls_back_to_ten():
    """A log base of exactly 1.0 is invalid for matplotlib's LogScale;
    _resolve_log_base (invoked via the custom spin box's valueChanged ->
    _on_field_changed -> _write_axis_config path) must fall back to 10.0."""
    chart = Chart(name="Test Chart")
    chart.update_config({"y_scale": "log"})

    tab = AxesTab(_make_app_context())
    tab.load(chart)

    y_form = tab.axes_forms["y"]
    custom_index = y_form["log_base_combo"].findData("custom")
    y_form["log_base_combo"].setCurrentIndex(custom_index)
    y_form["log_base_custom_spin"].setValue(1.0)

    assert chart.config["y_log_base"] == 10.0


def test_copy_axis_settings_copies_log_base_from_source_y_to_target_y2():
    """_on_copy_axis_settings("y") must copy Y's log-base combo selection
    into Y2, and the copy must be observable in chart.config (not just the
    widget state), since _on_field_changed writes all three axes' config
    at the end of the copy."""
    chart = Chart(name="Test Chart")
    chart.update_config({"y_scale": "log", "y_log_base": 2.0})
    chart.add_data_series(dataset_id="ds1", x_column="x", y_column="y", y_axis="secondary")

    tab = AxesTab(_make_app_context())
    tab.load(chart)

    y2_form = tab.axes_forms["y2"]
    # Sanity check: Y2 starts out at the default base (10.0), distinct from Y's 2.0.
    assert y2_form["log_base_combo"].currentData() == 10.0

    tab._on_copy_axis_settings("y")

    assert y2_form["log_base_combo"].currentData() == 2.0
    assert chart.config["y2_log_base"] == 2.0


def test_load_selects_custom_for_non_preset_log_base_and_populates_spin():
    """Loading a chart whose config has a non-preset log base (3.5) must
    select "Custom..." in the combo and populate the custom spin box with
    3.5 -- the round-trip of _read_axis_config for a saved custom base."""
    chart = Chart(name="Test Chart")
    chart.update_config({"y_scale": "log", "y_log_base": 3.5})

    tab = AxesTab(_make_app_context())
    tab.load(chart)

    y_form = tab.axes_forms["y"]
    assert y_form["log_base_combo"].currentData() == "custom"
    assert y_form["log_base_custom_spin"].value() == 3.5
    assert y_form["log_base_custom_spin"].isHidden() is False
    assert y_form["log_base_row"].isHidden() is False


def test_load_manual_axis_shows_saved_range_not_recomputed_data_range():
    """A Manual-mode axis's displayed min/max on load must be exactly what
    was saved in chart.config, even when the chart's series data would
    compute to a completely different range. Loading/reopening a chart is
    NOT an Auto->Manual toggle, so it must never recompute-and-overwrite a
    Manual axis's value (the bug this test guards against: `load()` used to
    call `_refresh_range_display` unconditionally for every axis, silently
    clobbering the saved manual range with the live data range)."""
    ds = _make_dataset("ds1", x=[1, 2, 3], y=[100, 200, 300])
    project = _FakeProject([ds])
    chart = Chart(name="Test Chart")
    chart.update_config({
        "y_auto_limits": False,
        "y_min": 5.0,
        "y_max": 50.0,
    })
    chart.add_data_series(dataset_id="ds1", x_column="x", y_column="y")

    tab = AxesTab(_make_app_context(project))
    tab.load(chart)

    y_form = tab.axes_forms["y"]
    assert y_form["auto_toggle"].isChecked() is False
    assert y_form["min_spin"].value() == 5.0
    assert y_form["max_spin"].value() == 50.0
    assert y_form["min_spin"].isEnabled() is True
    assert y_form["max_spin"].isEnabled() is True


def test_load_auto_axis_shows_recomputed_data_range_disabled():
    """Regression check: an Auto-mode axis must still show the freshly
    recomputed data range on load, disabled -- the Auto path is unaffected
    by the Manual-mode fix above."""
    ds = _make_dataset("ds1", x=[1, 2, 3], y=[100, 200, 300])
    project = _FakeProject([ds])
    chart = Chart(name="Test Chart")
    chart.update_config({"y_auto_limits": True})
    chart.add_data_series(dataset_id="ds1", x_column="x", y_column="y")

    tab = AxesTab(_make_app_context(project))
    tab.load(chart)

    y_form = tab.axes_forms["y"]
    assert y_form["auto_toggle"].isChecked() is True
    assert y_form["min_spin"].value() == 100.0
    assert y_form["max_spin"].value() == 300.0
    assert y_form["min_spin"].isEnabled() is False
    assert y_form["max_spin"].isEnabled() is False


def test_log_scale_axis_range_display_excludes_non_positive_values():
    """A Log-scaled axis must show Min/Max computed from only the positive
    subset of the data -- matplotlib's log-scale autoscale ignores
    non-positive points entirely, and a raw min <= 0 would later be
    silently rejected by set_ylim() on a log axis."""
    ds = _make_dataset("ds1", x=[1, 2, 3], y=[-5, 10, 20])
    project = _FakeProject([ds])
    chart = Chart(name="Test Chart")
    chart.update_config({"y_auto_limits": True, "y_scale": "log"})
    chart.add_data_series(dataset_id="ds1", x_column="x", y_column="y")

    tab = AxesTab(_make_app_context(project))
    tab.load(chart)

    y_form = tab.axes_forms["y"]
    assert y_form["min_spin"].value() == 10.0
    assert y_form["max_spin"].value() == 20.0


def test_toggling_auto_to_manual_recomputes_fresh_from_data():
    """Regression check: an explicit Auto->Manual toggle is the one case
    that SHOULD still recompute-and-overwrite -- it must ignore whatever
    stale value happened to be sitting in the spin boxes and show the
    current data range instead."""
    ds = _make_dataset("ds1", x=[1, 2, 3], y=[100, 200, 300])
    project = _FakeProject([ds])
    chart = Chart(name="Test Chart")
    chart.update_config({"y_auto_limits": True})
    chart.add_data_series(dataset_id="ds1", x_column="x", y_column="y")

    tab = AxesTab(_make_app_context(project))
    tab.load(chart)

    y_form = tab.axes_forms["y"]
    assert y_form["min_spin"].value() == 100.0
    assert y_form["max_spin"].value() == 300.0

    y_form["auto_toggle"].setChecked(checked=False)

    assert y_form["min_spin"].value() == 100.0
    assert y_form["max_spin"].value() == 300.0
    assert y_form["min_spin"].isEnabled() is True
    assert y_form["max_spin"].isEnabled() is True


def test_range_spin_boxes_do_not_round_away_small_magnitude_data():
    """The Range card's min/max spin boxes must not silently round a
    small-magnitude computed data range to 0.00/0.01 (Qt's default of 2
    decimal places) -- Task 4 made these boxes display machine-computed
    ranges, and a rounded-to-zero min on a subsequent Auto->Manual toggle
    would write a degenerate (or, on a log axis, invalid) limit into
    config."""
    ds = _make_dataset("ds1", x=[1, 2, 3], y=[0.001, 0.005, 0.009])
    project = _FakeProject([ds])
    chart = Chart(name="Test Chart")
    chart.update_config({"y_auto_limits": True})
    chart.add_data_series(dataset_id="ds1", x_column="x", y_column="y")

    tab = AxesTab(_make_app_context(project))
    tab.load(chart)

    y_form = tab.axes_forms["y"]
    assert y_form["min_spin"].value() == pytest.approx(0.001)
    assert y_form["max_spin"].value() == pytest.approx(0.009)
    assert y_form["min_spin"].decimals() >= 6
    assert y_form["max_spin"].decimals() >= 6


def test_switching_linear_to_log_refreshes_auto_range_to_positive_only():
    """Switching an Auto axis's Scale from Linear to Log must immediately
    refresh the displayed range to the positive-only-filtered range (Task
    4's `positive_only` filtering only takes effect through
    `_refresh_range_display`) -- not leave the pre-switch linear range
    (which may include a non-positive min invalid for a log axis) on
    display."""
    ds = _make_dataset("ds1", x=[1, 2, 3], y=[-5, 10, 20])
    project = _FakeProject([ds])
    chart = Chart(name="Test Chart")
    chart.update_config({"y_auto_limits": True, "y_scale": "linear"})
    chart.add_data_series(dataset_id="ds1", x_column="x", y_column="y")

    tab = AxesTab(_make_app_context(project))
    tab.load(chart)

    y_form = tab.axes_forms["y"]
    assert y_form["min_spin"].value() == -5.0
    assert y_form["max_spin"].value() == 20.0

    # SegmentedControl.setCurrentValue() is a silent programmatic setter (no
    # currentValueChanged emitted) -- only a real button click fires the
    # signal that drives _on_scale_changed, so click the "Log" segment
    # rather than calling setCurrentValue() directly.
    log_index = y_form["scale_control"]._values.index(ScaleType.LOG)
    y_form["scale_control"]._buttons[log_index].click()

    assert y_form["scale_control"].currentValue() == ScaleType.LOG
    assert y_form["min_spin"].value() == 10.0
    assert y_form["max_spin"].value() == 20.0
