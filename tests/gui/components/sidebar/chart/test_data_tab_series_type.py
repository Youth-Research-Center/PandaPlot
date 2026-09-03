"""Tests for DataTab's per-series Series Type selector (Phase 4c)."""
import sys
from unittest.mock import patch

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.data_tab import DataTab
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_style import LineSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
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
    # "Fit" is a conversion action offered regardless of allowed_series_types
    # (see test_selecting_fit_converts_the_series_to_fit_data below).
    assert offered == {SeriesType.BAR, SeriesType.SCATTER, "__convert_to_fit__"}


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

    assert len(chart.data_series) == 0
    assert len(chart.fit_data) == 1
    fit = chart.fit_data[0]
    assert fit.fit_type == "Custom"
    assert fit.label == "My Series"
    assert fit.source_dataset_id == dataset.id


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
    np.testing.assert_array_equal(fit.confidence_lower, dataset.data["y_lower"].to_numpy())
    np.testing.assert_array_equal(fit.confidence_upper, dataset.data["y_upper"].to_numpy())


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

    # One series remains (index 0), the new fit lands right after it.
    assert tab.selected_index == 1
    assert len(chart.data_series) == 1
    assert len(chart.fit_data) == 1


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

    assert chart.fit_data[0].is_manual is True
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
    np.testing.assert_array_equal(fit.y_data, dataset.data["y"].to_numpy())

    y2_index = tab.y_column_combo.findData(dataset.column_id("y2"))
    tab.y_column_combo.setCurrentIndex(y2_index)

    fit = chart.fit_data[0]
    assert fit.source_y_column_id == dataset.column_id("y2")
    np.testing.assert_array_equal(fit.y_data, dataset.data["y2"].to_numpy())


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
    original_y_column_id = fit.source_y_column_id
    import numpy as np
    original_y_data = fit.y_data.copy()

    label_index = tab.y_column_combo.findData(dataset.column_id("label"))
    tab.y_column_combo.setCurrentIndex(label_index)

    fit = chart.fit_data[0]
    assert fit.source_y_column_id == original_y_column_id
    np.testing.assert_array_equal(fit.y_data, original_y_data)
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
    assert fit.confidence_lower_column_id == ""
    assert fit.confidence_lower is None

    label_index = tab.confidence_lower_column_combo.findData(dataset.column_id("label"))
    tab.confidence_lower_column_combo.setCurrentIndex(label_index)

    fit = chart.fit_data[0]
    assert fit.confidence_lower_column_id == ""
    assert fit.confidence_lower is None
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
    chart.add_fit_data(
        dataset.id, fit_type="Linear",
        x_data=dataset.data["x"].to_numpy(), y_data=dataset.data["y"].to_numpy(),
        label="A Fit",
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    assert chart.fit_data[0].is_manual is False
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
    chart.add_fit_data(
        dataset.id, fit_type="Custom",
        x_data=dataset.data["x"].to_numpy(), y_data=dataset.data["y"].to_numpy(),
        label="A Custom Fit",
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    assert chart.fit_data[0].fit_type == "Custom"
    assert chart.fit_data[0].is_manual is False
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
    chart.add_fit_data(
        dataset.id, fit_type="Custom",
        x_data=dataset.data["x"].to_numpy(), y_data=dataset.data["y"].to_numpy(),
        label="A Fit",
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

    assert len(chart.data_series) == 0
    assert len(chart.fit_data) == 1

    tab.apply_to(chart)

    assert len(chart.data_series) == 0
    assert len(chart.fit_data) == 1
