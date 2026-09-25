"""Tests for DataTab's per-series Series Type selector (Phase 4c)."""
import sys
from unittest.mock import patch

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.data_tab import DataTab
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.series_style import LineSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart, YAxis
from pandaplot.models.project.project import Project


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _app_context_with_project():
    from pandaplot.app import build_app_context
    app_context = build_app_context()
    project = Project(name="Test Project")
    df = pd.DataFrame({"x": [0, 1], "y": [0, 1], "u": [1.0, -1.0], "v": [0.5, 0.5]})
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    app_context.app_state.load_project(project)
    return app_context, project, dataset


def test_series_type_combo_offers_only_the_chart_types_allowed_series_types():
    """A Bar chart allows {BAR, SCATTER} (not LINE/HIST/VECTOR).

    LINE/SCATTER/VECTOR now all mutually allow each other (CHART_TYPE_
    SPECS), so a Line chart's combo would no longer demonstrate any
    restriction -- Bar (and Histogram) are the chart types still narrowed
    to a proper subset, so this test uses Bar to keep checking real
    allow-list enforcement rather than becoming vacuous."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Bar Chart", chart_type="bar")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    offered = {tab.series_type_combo.itemData(i) for i in range(tab.series_type_combo.count())}
    # SeriesType.FIT itself is never offered -- only the
    # "__convert_to_fit__" action item represents "Fit" here.
    assert offered == {SeriesType.BAR, SeriesType.SCATTER, "__convert_to_fit__"}


def test_series_type_combo_has_exactly_one_fit_entry_using_the_convert_sentinel():
    """Regression test for final-review finding #2: the combo must never
    list SeriesType.FIT itself (which would retype the series in place,
    losing its curve snapshot) -- only the "__convert_to_fit__" action
    item may be labeled "Fit"."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    fit_labeled_rows = [
        i for i in range(tab.series_type_combo.count())
        if tab.series_type_combo.itemText(i) == "Fit"
    ]
    assert len(fit_labeled_rows) == 1
    assert tab.series_type_combo.itemData(fit_labeled_rows[0]) == "__convert_to_fit__"
    # SeriesType.FIT itself must not be selectable from this combo at all.
    assert tab.series_type_combo.findData(SeriesType.FIT) == -1


def _fit_entry_row(tab):
    return tab.series_type_combo.findData("__convert_to_fit__")


def test_series_type_combo_disables_the_fit_conversion_action_on_3d_charts():
    """A FIT series has only 2-D (x, y) curve data and its renderer plots
    on a plain Axes, not mplot3d -- offering "Fit" as a conversion action
    on a 3-D chart would leave a 2-D-only renderer attached to 3-D axes,
    with no chart-type switch involved to have warned about it (#304
    final-review finding). The entry stays in the combo (so an existing
    fit is still labeled "Fit"), just disabled."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="3D Scatter Chart", chart_type="scatter3d")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
                           series_type=SeriesType.SCATTER3D)
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    row = _fit_entry_row(tab)
    assert row >= 0
    assert tab.series_type_combo.model().item(row).isEnabled() is False


def test_series_type_combo_disables_the_fit_conversion_action_on_colormap_charts():
    """A Colormap chart has allows_fit=False (same as a 3-D chart type,
    just for a different reason: FIT isn't a member of its
    allowed_series_types at all) -- offering "Fit" there would let
    ConvertSeriesToFitCommand (which has no chart-type check of its own)
    produce a FIT series the chart type can't actually render. The entry
    stays in the combo (so an existing fit is still labeled "Fit"), just
    disabled."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Colormap Chart", chart_type="colormap")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
                           series_type=SeriesType.SCATTER)
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    row = _fit_entry_row(tab)
    assert row >= 0
    assert tab.series_type_combo.model().item(row).isEnabled() is False


def test_series_type_combo_selects_the_current_series_own_type():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Vector Chart", chart_type="vector")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
                           series_type=SeriesType.LINE)
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    assert tab.series_type_combo.currentData() == SeriesType.LINE


def test_changing_the_combo_retypes_the_selected_series():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    scatter_index = tab.series_type_combo.findData(SeriesType.SCATTER)
    tab.series_type_combo.setCurrentIndex(scatter_index)

    assert chart.data_series[0].series_type == SeriesType.SCATTER


def test_series_type_combo_defaults_to_the_chart_types_own_default_series_type():
    """Regression test: an untouched combo on a Vector chart must default
    to VECTOR (CHART_TYPE_SPECS["vector"].default_series_type), not
    whatever sorts alphabetically first among allowed_series_types
    ({LINE, VECTOR} -- "line" sorts before "vector"). A user who never
    touches this combo before creating a series on an empty Vector chart
    must still get a Vector series, not a Line one missing its U/V
    columns."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Vector Chart", chart_type="vector")
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    assert tab.series_type_combo.currentData() == SeriesType.VECTOR


def test_changing_the_combo_to_vector_shows_the_uv_fields_for_that_series():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Vector Chart", chart_type="vector")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
                           series_type=SeriesType.LINE)
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.show()
    tab.set_project(project)
    tab.load(chart)
    QApplication.processEvents()
    assert tab.u_column_combo.isVisible() is False

    vector_index = tab.series_type_combo.findData(SeriesType.VECTOR)
    tab.series_type_combo.setCurrentIndex(vector_index)
    QApplication.processEvents()

    assert tab.u_column_combo.isVisible() is True


def test_add_series_defaults_to_the_chart_type_even_if_a_different_typed_series_is_selected():
    """Regression test: reported live as "chart is Line type, but because
    I have selected a Scatter series, adding a new series defaults to
    Scatter instead of Line." The Series Type combo tracks whichever
    EXISTING series is selected (see _load_series_into_controls) -- a
    brand-new series must always get the chart's own default type
    (CHART_TYPE_SPECS[chart_type].default_series_type) regardless of
    what the combo happens to show from the currently-selected series."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
                           series_type=SeriesType.SCATTER)
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    # Sanity: selecting the existing Scatter series correctly shows
    # "Scatter" in the combo -- this is the surprising value that must
    # NOT leak into a newly-added series.
    assert tab.series_type_combo.currentData() == SeriesType.SCATTER

    tab.x_column_combo.setCurrentIndex(0)
    tab.y_column_combo.setCurrentIndex(0)
    tab._add_series()

    assert chart.data_series[-1].series_type == SeriesType.LINE
    assert isinstance(chart.data_series[-1].style, LineSeriesStyle)


def test_add_series_works_on_a_vector_chart_when_a_line_series_is_selected():
    """Regression test: reported live as "+Add series doesn't work when
    chart is vector and series is line." Root cause: a Line series (which
    Vector's spec allows) doesn't need U/V, so its own U/V combos are
    legitimately hidden and blank (_selected_series_is_vector() is False)
    -- but _add_series used to REQUIRE those same combos to be non-empty
    before creating a new (Vector-typed, chart-default) series, so the
    click silently did nothing. It must create the series anyway, even
    with empty U/V -- the resulting series can be completed afterward by
    selecting it and filling in its own now-visible U/V combos, exactly
    like apply_to's already-established empty-chart bootstrap path."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Vector Chart", chart_type="vector")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
                           series_type=SeriesType.LINE)
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    # Sanity: the Line series is selected, so U/V combos read back empty.
    assert tab.u_column_combo.currentData() in (None, "")
    assert tab.v_column_combo.currentData() in (None, "")

    tab._add_series()

    assert len(chart.data_series) == 2
    assert chart.data_series[-1].series_type == SeriesType.VECTOR


def test_uv_fields_appear_right_after_x_and_y_in_the_form():
    """Reported live: "order of information is wrong so u and v columns
    are after error columns instead after x and y columns." The form is a
    QGridLayout with explicit row numbers -- U/V must sit at the rows
    immediately following X/Y, ahead of every error-bar row."""
    app_context, project, dataset = _app_context_with_project()
    tab = DataTab(app_context=app_context)

    layout = tab._series_form_widget.layout()

    def _row_of(widget):
        index = layout.indexOf(widget)
        row, _col, _rowspan, _colspan = layout.getItemPosition(index)
        return row

    x_row = _row_of(tab.x_column_combo)
    y_row = _row_of(tab.y_column_combo)
    u_row = _row_of(tab.u_column_combo)
    v_row = _row_of(tab.v_column_combo)
    x_error_row = _row_of(tab.x_error_column_combo)

    assert x_row < y_row < u_row < v_row < x_error_row


def test_enabling_asymmetric_error_bars_defaults_minus_columns_to_the_plus_columns():
    """Reported live: "when I turn on asymetric error bars, the minus
    column is set to None, it would make more sense if it was set to the
    same column as the plus column as it reflects what is currently shown
    on the chart." Ticking the checkbox must copy each already-selected
    plus-side column into its still-empty minus-side sibling, so the
    rendered error bars don't silently change the instant asymmetric mode
    is turned on."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        style=LineSeriesStyle(error_bars=ErrorBarConfig(y_error_column_id=dataset.column_id("y"))),
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    tab._expand_series(0)

    y_error_index = tab.y_error_column_combo.findData(dataset.column_id("y"))
    tab.y_error_column_combo.setCurrentIndex(y_error_index)
    assert tab.y_error_minus_column_combo.currentData() in (None, "")

    tab.error_asymmetric_check.setChecked(True)

    assert tab.y_error_minus_column_combo.currentData() == dataset.column_id("y")


def test_error_bar_fields_are_grouped_by_axis_not_by_sign():
    """Reported live: "asymetric error bars in ui should be grouped by
    axis and not by plus/minus. I think this is more intuitive for the
    user." Row order must be X(+), X(-), Y(+), Y(-), not X(+), Y(+),
    X(-), Y(-)."""
    app_context, project, dataset = _app_context_with_project()
    tab = DataTab(app_context=app_context)

    layout = tab._series_form_widget.layout()

    def _row_of(widget):
        index = layout.indexOf(widget)
        row, _col, _rowspan, _colspan = layout.getItemPosition(index)
        return row

    x_plus_row = _row_of(tab.x_error_column_combo)
    x_minus_row = _row_of(tab.x_error_minus_column_combo)
    y_plus_row = _row_of(tab.y_error_column_combo)
    y_minus_row = _row_of(tab.y_error_minus_column_combo)

    assert x_plus_row < x_minus_row < y_plus_row < y_minus_row


def test_selecting_fit_converts_the_series_to_fit_data():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        label="My Series",
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    fit_index = tab.series_type_combo.findData("__convert_to_fit__")
    tab.series_type_combo.setCurrentIndex(fit_index)

    # The converted series is now a FIT-type entry IN data_series (the
    # unified list, #304), not removed from it.
    assert len(chart.data_series) == 1
    assert len(chart.fit_data) == 1
    fit = chart.fit_data[0]
    assert fit.style.fit_type == "Custom"
    assert fit.label == "My Series"
    assert fit.dataset_id == dataset.id


def test_selecting_fit_keeps_the_series_original_render_position():
    """Regression test: ConvertSeriesToFitCommand used to always append the
    new fit at the END of chart.data_series regardless of which series was
    converted, silently moving a non-last series' fit on top of every
    series after it in render order -- contradicting the design (a FIT
    entry renders in its own data_series position like any other series,
    see the move-controls docstrings). Converting the FIRST of three
    series must leave it first, now as a fit."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
                           label="A")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
                           label="B")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
                           label="C")
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    tab._convert_selected_series_to_fit(0)

    assert [s.label for s in chart.data_series] == ["A", "B", "C"]
    assert chart.data_series[0].series_type == SeriesType.FIT


def test_the_disabled_series_type_combo_shows_fit_not_the_converted_series_own_type():
    """Regression test: reported live as "when I transform a series to fit
    it shows as scatter." _load_fit_into_controls disables the combo but
    used to leave it showing whichever value was last populated there (the
    converted series' own prior type, e.g. Scatter) -- misleading, since
    the disabled combo no longer means "this entry's type is Scatter," it
    means "this entry isn't a real series anymore." It must show "Fit"
    instead."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        series_type=SeriesType.SCATTER,
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    # Sanity: before conversion, the combo correctly shows the series' own type.
    assert tab.series_type_combo.currentData() == SeriesType.SCATTER

    fit_index = tab.series_type_combo.findData("__convert_to_fit__")
    tab.series_type_combo.setCurrentIndex(fit_index)

    assert tab.series_type_combo.currentData() == "__convert_to_fit__"
    assert tab.series_type_combo.isEnabled() is False


def test_selecting_fit_snapshots_the_chosen_confidence_columns():
    app_context, project, dataset = _app_context_with_project()
    # dataset from _app_context_with_project has columns x, y, u, v -- add
    # lower/upper columns for this test.
    dataset.data["y_lower"] = dataset.data["y"] - 0.5
    dataset.data["y_upper"] = dataset.data["y"] + 0.5
    dataset._sync_column_ids()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    lower_index = tab.confidence_lower_column_combo.findData(dataset.column_id("y_lower"))
    tab.confidence_lower_column_combo.setCurrentIndex(lower_index)
    upper_index = tab.confidence_upper_column_combo.findData(dataset.column_id("y_upper"))
    tab.confidence_upper_column_combo.setCurrentIndex(upper_index)

    fit_index = tab.series_type_combo.findData("__convert_to_fit__")
    tab.series_type_combo.setCurrentIndex(fit_index)

    fit = chart.fit_data[0]
    import numpy as np
    np.testing.assert_array_equal(fit.style.confidence_lower, dataset.data["y_lower"].to_numpy())
    np.testing.assert_array_equal(fit.style.confidence_upper, dataset.data["y_upper"].to_numpy())


def test_selecting_fit_selects_the_new_fit_card():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    tab._expand_series(1)

    fit_index = tab.series_type_combo.findData("__convert_to_fit__")
    tab.series_type_combo.setCurrentIndex(fit_index)

    # One series remains (index 0), the new fit lands right after it --
    # the fit is a FIT-type entry IN data_series, not removed from it.
    assert tab.selected_index == 1
    assert len(chart.data_series) == 2
    assert len(chart.fit_data) == 1


def test_converting_a_non_last_series_selects_the_new_fit_not_the_last_card():
    """Regression test (PR #416 review): the fit replaces the converted
    series at its own position, so selection must stay on that position.
    Selecting `len(data_series) - 1` instead expanded the LAST series (a
    plain Line series here) and loaded it into the form and Style tab."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    for label in ("A", "B", "C"):
        chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
                              label=label)
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    tab._expand_series(0)

    fit_index = tab.series_type_combo.findData("__convert_to_fit__")
    tab.series_type_combo.setCurrentIndex(fit_index)

    assert chart.data_series[0].series_type == SeriesType.FIT
    assert tab.selected_index == 0
    # The form shows the fit, not series C.
    assert tab.series_type_combo.currentData() == "__convert_to_fit__"
    assert tab.series_label_edit.text() == "A"


def test_converting_to_fit_is_undoable():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    fit_index = tab.series_type_combo.findData("__convert_to_fit__")
    tab.series_type_combo.setCurrentIndex(fit_index)
    assert len(chart.fit_data) == 1

    app_context.command_executor.undo()

    assert len(chart.data_series) == 1
    assert len(chart.fit_data) == 0


def test_a_manually_converted_fit_keeps_its_columns_editable():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    fit_index = tab.series_type_combo.findData("__convert_to_fit__")
    tab.series_type_combo.setCurrentIndex(fit_index)

    assert chart.fit_data[0].style.is_manual is True
    assert tab.dataset_combo.isEnabled() is True
    assert tab.x_column_combo.isEnabled() is True
    assert tab.y_column_combo.isEnabled() is True
    assert tab.confidence_lower_column_combo.isEnabled() is True
    assert tab.confidence_upper_column_combo.isEnabled() is True
    # X/Y combos show the fit's current source columns.
    assert tab.x_column_combo.currentData() == dataset.column_id("x")
    assert tab.y_column_combo.currentData() == dataset.column_id("y")


def test_editing_a_manual_fits_y_column_resnapshots_its_data():
    app_context, project, dataset = _app_context_with_project()
    dataset.data["y2"] = dataset.data["y"] * 10
    dataset._sync_column_ids()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    fit_index = tab.series_type_combo.findData("__convert_to_fit__")
    tab.series_type_combo.setCurrentIndex(fit_index)

    fit = chart.fit_data[0]
    import numpy as np
    np.testing.assert_array_equal(fit.precomputed_y_data, dataset.data["y"].to_numpy())

    y2_index = tab.y_column_combo.findData(dataset.column_id("y2"))
    tab.y_column_combo.setCurrentIndex(y2_index)

    fit = chart.fit_data[0]
    assert fit.y_column_id == dataset.column_id("y2")
    np.testing.assert_array_equal(fit.precomputed_y_data, dataset.data["y2"].to_numpy())


def test_editing_a_manual_fits_column_to_an_unresolvable_one_rolls_back_atomically():
    """Regression test (PR #309 review): picking a Y column that can't
    resolve (e.g. wholly non-numeric) must not leave the fit in a mixed
    state where the combo shows the new column but x_data/y_data still
    reflect the old one -- the whole edit is rejected and the controls
    revert to the fit's actual, unchanged source/data."""
    app_context, project, dataset = _app_context_with_project()
    dataset.data["label"] = ["a", "b"]
    dataset._sync_column_ids()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    fit_index = tab.series_type_combo.findData("__convert_to_fit__")
    tab.series_type_combo.setCurrentIndex(fit_index)

    fit = chart.fit_data[0]
    original_y_column_id = fit.y_column_id
    import numpy as np
    original_y_data = fit.precomputed_y_data.copy()

    label_index = tab.y_column_combo.findData(dataset.column_id("label"))
    tab.y_column_combo.setCurrentIndex(label_index)

    fit = chart.fit_data[0]
    assert fit.y_column_id == original_y_column_id
    np.testing.assert_array_equal(fit.precomputed_y_data, original_y_data)
    # The controls must also reflect the rollback, not the rejected pick.
    assert tab.y_column_combo.currentData() == original_y_column_id


def test_picking_an_unresolvable_confidence_column_rolls_back_the_whole_edit():
    """Regression test (PR #309 review): a NON-empty confidence-column
    pick that can't resolve (e.g. wholly non-numeric) must reject the
    whole edit -- previously the id was persisted anyway even though
    resolution failed, leaving confidence_lower_column_id pointing at a
    column the fit's confidence_lower array doesn't actually reflect."""
    app_context, project, dataset = _app_context_with_project()
    dataset.data["label"] = ["a", "b"]
    dataset._sync_column_ids()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    fit_index = tab.series_type_combo.findData("__convert_to_fit__")
    tab.series_type_combo.setCurrentIndex(fit_index)

    fit = chart.fit_data[0]
    assert fit.style.confidence_lower_column_id == ""
    assert fit.style.confidence_lower is None

    label_index = tab.confidence_lower_column_combo.findData(dataset.column_id("label"))
    tab.confidence_lower_column_combo.setCurrentIndex(label_index)

    fit = chart.fit_data[0]
    assert fit.style.confidence_lower_column_id == ""
    assert fit.style.confidence_lower is None
    assert tab.confidence_lower_column_combo.currentData() == ""


def test_touching_confidence_combos_while_a_regular_series_is_selected_does_not_mark_dirty():
    """Regression test (PR #309 review): the confidence combos are
    write-only-at-conversion-time for a regular DataSeries (no model
    field they'd persist to) -- touching them there must be a true
    no-op, not mark the panel dirty via the shared
    _on_series_config_changed handler's unconditional dirtyOnly.emit()."""
    app_context, project, dataset = _app_context_with_project()
    dataset.data["label"] = ["a", "b"]
    dataset._sync_column_ids()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    dirty_calls = []
    tab.dirtyOnly.connect(lambda: dirty_calls.append(True))

    label_index = tab.confidence_lower_column_combo.findData(dataset.column_id("label"))
    tab.confidence_lower_column_combo.setCurrentIndex(label_index)

    assert dirty_calls == []


def test_an_auto_applied_fit_stays_non_editable():
    """Regression guard: only a manually-converted fit becomes editable --
    an auto-applied fit (e.g. from the Fit panel, is_manual defaults to
    False) must keep the pre-existing locked behavior."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_fit_series(
        dataset.id,
        x_data=dataset.data["x"].to_numpy(), y_data=dataset.data["y"].to_numpy(),
        label="A Fit", style=FitStyle(fit_type="Linear", is_manual=False),
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    assert chart.fit_data[0].style.is_manual is False
    assert tab.dataset_combo.isEnabled() is False
    assert tab.x_column_combo.isEnabled() is False
    assert tab.y_column_combo.isEnabled() is False


def test_an_auto_applied_custom_fit_stays_non_editable_despite_the_shared_fit_type_string():
    """Regression guard: fit_type=="Custom" alone must NOT make a fit
    editable -- that string is shared by both a manually-converted fit
    (is_manual=True, editable) and a Fit-panel "Custom" equation fit
    (is_manual=False, locked, since #305 let it pick a dataset/X/Y too).
    is_manual is what must actually gate editability."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_fit_series(
        dataset.id,
        x_data=dataset.data["x"].to_numpy(), y_data=dataset.data["y"].to_numpy(),
        label="A Custom Fit", style=FitStyle(fit_type="Custom", is_manual=False),
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    assert chart.fit_data[0].style.fit_type == "Custom"
    assert chart.fit_data[0].style.is_manual is False
    assert tab.dataset_combo.isEnabled() is False
    assert tab.x_column_combo.isEnabled() is False
    assert tab.y_column_combo.isEnabled() is False
    assert tab.confidence_lower_column_combo.isEnabled() is False
    assert tab.confidence_upper_column_combo.isEnabled() is False


def test_selecting_fit_on_a_failed_conversion_reloads_the_real_series_type():
    """Regression test for final-review Fix 2 (#298): if the
    ConvertSeriesToFitCommand fails (e.g. its source dataset no longer
    exists), the series at that index is NOT converted -- but without
    reloading the controls, the Series Type combo would still show "Fit"
    even though the series is still really a Line series, and the user
    couldn't even retry (setCurrentIndex on an already-current index
    doesn't emit currentIndexChanged)."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    # Point the series at a dataset_id that doesn't exist in the project,
    # so ConvertSeriesToFitCommand's dataset lookup fails and it returns
    # CommandResult.FAILURE.
    chart.add_data_series(
        "missing-dataset-id",
        x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        series_type=SeriesType.LINE,
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    fit_index = tab.series_type_combo.findData("__convert_to_fit__")
    # The failed conversion reports the error via a real QMessageBox.critical
    # (UIController.show_error_message), which is a blocking modal dialog
    # -- patch the module-level QMessageBox reference (not an instance
    # method -- Shiboken bypasses those, see test_welcome_tab.py's note) so
    # the test doesn't hang waiting for a click that will never come.
    with patch("pandaplot.gui.controllers.ui_controller.QMessageBox"):
        tab.series_type_combo.setCurrentIndex(fit_index)

    # The series was NOT converted: still a DataSeries, not turned into a fit.
    assert len(chart.data_series) == 1
    assert len(chart.fit_data) == 0
    # The combo must reflect the series' real, unchanged type -- not left
    # stuck on the "__convert_to_fit__" sentinel.
    assert tab.series_type_combo.currentData() == SeriesType.LINE


def test_selecting_fit_on_a_failed_conversion_does_not_crash_when_theres_no_series_to_reload():
    """Regression test: the reload-on-failure step (see test above) used
    to unconditionally index self.current_chart.data_series[index] --
    safe for the "column couldn't be resolved" failure mode (data_series
    is untouched), but ConvertSeriesToFitCommand can also fail before
    ever validating that index (e.g. chart not found, or series_index
    itself out of range), in which case there may be no series at that
    index to reload. Simulated here by forcing the command to fail
    directly and calling the conversion method with an index that's out
    of range for data_series."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    with patch.object(tab.command_executor, "execute_command", return_value=False):
        # No exception must be raised even though `index` is out of range
        # for data_series -- this exercises the same failure branch as a
        # "chart not found" or "series_index out of range" command
        # failure, which the reload step must guard against.
        tab._convert_selected_series_to_fit(5)

    assert len(chart.data_series) == 1


def test_confidence_column_combos_disabled_while_editing_a_fit():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_fit_series(
        dataset.id,
        x_data=dataset.data["x"].to_numpy(), y_data=dataset.data["y"].to_numpy(),
        label="A Fit", style=FitStyle(fit_type="Custom", is_manual=False),
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    assert tab.confidence_lower_column_combo.isEnabled() is False
    assert tab.confidence_upper_column_combo.isEnabled() is False


def test_apply_to_does_not_recreate_a_series_after_converting_the_only_series_to_fit():
    """Regression test (PR #309 review): apply_to()'s "no data_series yet
    -> bootstrap a default series from the form" fallback used to fire
    whenever data_series was empty, even when the chart already has a
    fit (e.g. its only series was just converted). Since the form's
    combos, at that point, show the SELECTED FIT's own source columns
    (not blank defaults), Apply would silently recreate a duplicate
    series alongside the fit."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    fit_index = tab.series_type_combo.findData("__convert_to_fit__")
    tab.series_type_combo.setCurrentIndex(fit_index)

    # The fit is a FIT-type entry IN data_series (the unified list, #304),
    # not removed from it -- data_series is never "empty" here.
    assert len(chart.data_series) == 1
    assert len(chart.fit_data) == 1

    tab.apply_to(chart)

    assert len(chart.data_series) == 1
    assert len(chart.fit_data) == 1


def test_remove_series_at_passes_the_real_data_series_index_for_a_fit():
    """`_remove_series_at` must hand `RemoveSeriesCommand` the same plain
    `chart.data_series` index it was given, for a FIT entry too.
    Regression test: this used to require resolving a `chart.fit_data`-
    relative index by identity (`is`, not `==`/`.index()`, since two FIT
    series with identical dataset/columns/label/style but different
    snapshotted curve data compare `==`-equal); that whole translation
    step is gone now that fits are removed like any other series."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")

    shared_style = FitStyle(fit_type="linear")
    chart.add_fit_series(
        dataset.id,
        x_data=dataset.data["x"].to_numpy(), y_data=dataset.data["y"].to_numpy(),
        source_x_column_id=dataset.column_id("x"), source_y_column_id=dataset.column_id("y"),
        label="Fit", style=shared_style,
    )
    chart.add_fit_series(
        dataset.id,
        # Same dataset/columns/label/style as the first fit -- only the
        # snapshotted curve data differs.
        x_data=dataset.data["x"].to_numpy() * 10, y_data=dataset.data["y"].to_numpy() * 10,
        source_x_column_id=dataset.column_id("x"), source_y_column_id=dataset.column_id("y"),
        label="Fit", style=shared_style,
    )
    # Sanity: the two fits really do compare equal, so a resolution
    # scheme relying on `==`/`.index()` would resolve to the wrong one.
    assert chart.data_series[0] == chart.data_series[1]

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    with patch(
        "pandaplot.gui.components.sidebar.chart.tabs.data_tab.RemoveSeriesCommand"
    ) as mock_command_cls:
        tab._remove_series_at(1)

    mock_command_cls.assert_called_once()
    assert mock_command_cls.call_args.kwargs["series_index"] == 1


def test_expand_series_emits_series_kind_for_fit_entries():
    """#304: a FIT-type series at any index emits ("series", obj), not
    ("fit", obj) -- there is no more separate index space to split on;
    FIT-type entries live inline in chart.data_series like any other
    series."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_fit_series(
        dataset.id, x_data=dataset.data["x"].to_numpy(), y_data=dataset.data["y"].to_numpy(),
        label="Fit", style=FitStyle(),
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    received = []
    tab.seriesSelected.connect(lambda kind, obj: received.append((kind, obj)))
    fit_index = len(chart.data_series) - 1
    tab._expand_series(fit_index)

    # _expand_series re-emits seriesSelected once for its own rebuild (via
    # _build_expanded_series_card) and once explicitly at the end -- a
    # pre-existing double-emit unrelated to this task (identical for a
    # regular, non-FIT series) -- what matters here is that every emission
    # carries ("series", obj), never ("fit", obj), for a FIT-type entry.
    assert received
    assert all(kind == "series" for kind, _obj in received)
    assert received[-1] == ("series", chart.data_series[fit_index])
    assert chart.data_series[fit_index].series_type == SeriesType.FIT


def _chart_with_auto_fit(dataset, *, y_axis=YAxis.PRIMARY):
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_fit_series(
        dataset.id,
        x_data=dataset.data["x"].to_numpy(), y_data=dataset.data["y"].to_numpy(),
        label="A Fit", style=FitStyle(fit_type="Linear", is_manual=False), y_axis=y_axis,
    )
    return chart


def test_a_fits_y_axis_control_is_enabled_and_shows_the_fits_own_axis():
    """PR #416 review: a fit's y_axis is a real field now (#304), so the
    Data tab must let the user change it. It used to be locked, leaving a
    fit stuck on whatever axis it got at creation."""
    app_context, project, dataset = _app_context_with_project()
    chart = _chart_with_auto_fit(dataset, y_axis=YAxis.SECONDARY)
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    assert tab.series_y_axis_control.isEnabled() is True
    assert tab.series_y_axis_control.currentValue() == YAxis.SECONDARY


def test_changing_an_auto_fits_y_axis_writes_it_and_marks_dirty():
    app_context, project, dataset = _app_context_with_project()
    chart = _chart_with_auto_fit(dataset)
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    dirty_calls = []
    tab.dirtyOnly.connect(lambda: dirty_calls.append(True))

    tab.series_y_axis_control.setCurrentValue(YAxis.SECONDARY)
    tab._on_series_y_axis_changed()

    assert chart.data_series[0].y_axis == YAxis.SECONDARY
    assert dirty_calls
    # The auto-applied fit's frozen source columns stay untouched.
    assert tab.dataset_combo.isEnabled() is False


def test_toggling_a_manual_fits_y_axis_does_not_repoint_it_when_its_source_dataset_is_gone():
    """Regression test for final-review Important 1: a manual fit's source
    dataset can be deleted out from under it (fits deliberately survive via
    Chart._strip_references). When the fit is then selected, the shared
    dataset/X/Y combos can't select the missing dataset, so
    _populate_column_combos returns early and they keep showing whatever
    dataset/columns were last loaded (here: the OTHER series' dataset B).

    Toggling only the Y axis must never let that stale combo state leak
    into the fit's dataset_id/x_column_id/y_column_id or resnapshot its
    curve -- _on_series_y_axis_changed must write ONLY y_axis.

    The `set_project` refresh after removing dataset A is what makes the
    combos show dataset B (as the real panel does on a tab switch), which is
    the state the bug needs. The axis toggle is a real click on the Y2
    button rather than a direct handler call, so the test also covers what
    `series_y_axis_control.currentValueChanged` is wired to."""
    app_context, project, dataset_a = _app_context_with_project()
    dataset_b = Dataset(name="ds2", data=pd.DataFrame({"x": [10, 20], "y": [30, 40]}))
    project.add_item(dataset_b)

    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(
        dataset_b.id, x_column_id=dataset_b.column_id("x"), y_column_id=dataset_b.column_id("y"),
        label="Regular",
    )
    chart.add_fit_series(
        dataset_a.id,
        x_data=dataset_a.data["x"].to_numpy(), y_data=dataset_a.data["y"].to_numpy(),
        source_x_column_id=dataset_a.column_id("x"), source_y_column_id=dataset_a.column_id("y"),
        label="Manual Fit", style=FitStyle(fit_type="Custom", is_manual=True),
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    # Select the regular series first so the shared combos show dataset B.
    tab._expand_series(0)
    assert tab.dataset_combo.currentData() == dataset_b.id

    # Now remove the fit's source dataset from the project, and refresh the
    # tab's dataset list the way the real panel does on tab switch
    # (chart_properties_panel.py's _on_tab_changed/_on_project_loaded call
    # set_project again) -- without this, dataset_combo would still contain
    # a stale entry for dataset A, letting the fit re-select it below and
    # masking the actual bug this test guards against.
    project.remove_item(dataset_a)
    tab.set_project(project)

    fit = chart.data_series[1]
    original_dataset_id = fit.dataset_id
    original_x_column_id = fit.x_column_id
    original_y_column_id = fit.y_column_id
    import numpy as np
    original_x_data = fit.precomputed_x_data.copy()
    original_y_data = fit.precomputed_y_data.copy()

    # Select the fit -- combos can't select the now-missing dataset A, so
    # they keep showing dataset B (stale, per _load_fit_into_controls /
    # _populate_column_combos' early-return-on-missing-dataset behavior).
    tab._expand_series(1)
    assert tab.dataset_combo.currentData() == dataset_b.id

    # Click the Y2 button -- a real user interaction, not a direct call to
    # the handler under test.
    tab.series_y_axis_control._buttons[1].click()

    fit = chart.data_series[1]
    assert fit.y_axis == YAxis.SECONDARY
    assert fit.dataset_id == original_dataset_id
    assert fit.x_column_id == original_x_column_id
    assert fit.y_column_id == original_y_column_id
    np.testing.assert_array_equal(fit.precomputed_x_data, original_x_data)
    np.testing.assert_array_equal(fit.precomputed_y_data, original_y_data)


def test_toggling_a_manual_fits_y_axis_does_not_resnapshot_its_data_even_when_source_is_present():
    """Regression test for final-review Important 1: even when the fit's
    source dataset is still present (so the combos correctly show it), a
    Y-axis-only toggle must not re-derive precomputed_x_data/
    precomputed_y_data from the dataset's CURRENT values -- only
    _apply_manual_fit_edits (a real dataset/X/Y edit) should do that.

    Driven by a real click, same reasoning as the test above."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_fit_series(
        dataset.id,
        x_data=dataset.data["x"].to_numpy(), y_data=dataset.data["y"].to_numpy(),
        source_x_column_id=dataset.column_id("x"), source_y_column_id=dataset.column_id("y"),
        label="Manual Fit", style=FitStyle(fit_type="Custom", is_manual=True),
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    fit = chart.data_series[0]
    import numpy as np
    original_y_data = fit.precomputed_y_data.copy()

    # Mutate the source dataset's values in place after the fit was created.
    dataset.data["y"] = dataset.data["y"] * 100

    tab.series_y_axis_control._buttons[1].click()

    fit = chart.data_series[0]
    assert fit.y_axis == YAxis.SECONDARY
    np.testing.assert_array_equal(fit.precomputed_y_data, original_y_data)


def test_clicking_the_y_axis_control_on_a_regular_series_writes_axis_and_refreshes_ui():
    """Regression guard: a real click (not a direct handler call) on the
    segmented control for a plain, non-FIT series must write y_axis,
    fire both axesRefreshRequested and dirtyOnly, and update the expanded
    card's own Y1/Y2 badge in place -- exercising the full, real signal
    path (`currentValueChanged` -> `_on_series_y_axis_changed`) rather
    than just the handler in isolation."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    axes_refresh_calls = []
    tab.axesRefreshRequested.connect(lambda: axes_refresh_calls.append(True))
    dirty_calls = []
    tab.dirtyOnly.connect(lambda: dirty_calls.append(True))

    tab.series_y_axis_control._buttons[1].click()

    assert chart.data_series[0].y_axis == YAxis.SECONDARY
    assert axes_refresh_calls
    assert dirty_calls
    assert tab._expanded_card_y_axis_badge.text() == "Y₂"


def test_apply_to_writes_the_selected_fits_y_axis():
    app_context, project, dataset = _app_context_with_project()
    chart = _chart_with_auto_fit(dataset)
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    tab.series_y_axis_control.setCurrentValue(YAxis.SECONDARY)

    tab.apply_to(chart)

    assert chart.data_series[0].y_axis == YAxis.SECONDARY


def test_fit_rows_show_a_y_axis_badge():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"), label="S")
    chart.add_fit_series(
        dataset.id,
        x_data=dataset.data["x"].to_numpy(), y_data=dataset.data["y"].to_numpy(),
        label="A Fit", style=FitStyle(fit_type="Linear"), y_axis=YAxis.SECONDARY,
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)  # series 0 selected; the fit (index 1) renders as a collapsed row

    from PySide6.QtWidgets import QLabel
    labels = [w.text() for w in tab.findChildren(QLabel)]
    assert "\U0001f527 A Fit" in labels
    assert "Y₂" in labels


def test_a_fit_carried_onto_a_colormap_chart_still_shows_fit_in_the_disabled_combo():
    """PR #416 review: a fit may stay on a Colormap chart (ChartTab allows
    the switch), where fits can't be *created* -- the combo must still
    label the existing fit "Fit" rather than falling back to "Colormap"."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Colormap Chart", chart_type="colormap")
    chart.add_fit_series(
        dataset.id,
        x_data=dataset.data["x"].to_numpy(), y_data=dataset.data["y"].to_numpy(),
        label="A Fit", style=FitStyle(fit_type="Linear"),
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    assert tab.series_type_combo.currentData() == "__convert_to_fit__"
    assert tab.series_type_combo.isEnabled() is False


def test_switching_chart_type_while_a_fit_is_selected_keeps_the_fit_controls():
    """refresh_vector_fields runs after a live chart-type change; it used to
    reload a selected fit through the regular-series path, re-enabling its
    locked source fields and showing a plain series type."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_fit_series(
        dataset.id,
        x_data=dataset.data["x"].to_numpy(), y_data=dataset.data["y"].to_numpy(),
        label="A Fit", style=FitStyle(fit_type="Linear", is_manual=False),
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    chart.set_chart_type("colormap")
    tab.refresh_vector_fields()

    assert tab.series_type_combo.currentData() == "__convert_to_fit__"
    assert tab.series_type_combo.isEnabled() is False
    assert tab.dataset_combo.isEnabled() is False


def test_selecting_the_disabled_fit_entry_does_not_convert_on_a_colormap_chart():
    """Regression test for final-review Minor B: _on_series_type_changed
    relied on Qt to block a click on the disabled "Fit" row -- but the
    handler itself is reachable directly (e.g. programmatically forcing
    the combo's index under blockSignals, then invoking the slot) without
    going through Qt's own disabled-item click guard. On a chart type
    whose CHART_TYPE_SPECS.allows_fit is False (Colormap), the handler
    must refuse the conversion instead of trusting the combo state."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Colormap Chart", chart_type="colormap")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
                           series_type=SeriesType.SCATTER)
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    fit_index = tab.series_type_combo.findData("__convert_to_fit__")
    tab.series_type_combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
    tab.series_type_combo.setCurrentIndex(fit_index)
    tab.series_type_combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only

    tab._on_series_type_changed()

    assert len(chart.data_series) == 1
    assert chart.data_series[0].series_type == SeriesType.SCATTER
    assert len(chart.fit_data) == 0
    # Controls are reloaded back to the series' real, unchanged type.
    assert tab.series_type_combo.currentData() == SeriesType.SCATTER
