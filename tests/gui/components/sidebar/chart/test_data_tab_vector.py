"""Tests for DataTab's Vector chart-type support (U/V/magnitude columns)."""
import sys

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.data_tab import DataTab
from pandaplot.models.chart.series_style.vector import VectorSeriesStyle
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


def test_vector_fields_hidden_for_a_line_chart():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    assert tab.u_column_combo.isVisible() is False
    assert tab.v_column_combo.isVisible() is False
    assert tab.magnitude_column_combo.isVisible() is False


def test_vector_fields_shown_and_populated_for_a_vector_chart():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Vector Chart", chart_type="vector")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        style=VectorSeriesStyle(u_column_id=dataset.column_id("u"), v_column_id=dataset.column_id("v")),
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.show()
    tab.set_project(project)
    tab.load(chart)
    # The persistent series-config form is reparented into whichever card is
    # selected (see _rebuild_series_cards) -- Qt only flips the resulting
    # widgets' shown-state once the event loop processes that reparenting.
    QApplication.processEvents()

    assert tab.u_column_combo.isVisible() is True
    assert tab.v_column_combo.isVisible() is True
    assert tab.u_column_combo.currentData() == dataset.column_id("u")
    assert tab.v_column_combo.currentData() == dataset.column_id("v")


def test_editing_u_column_updates_the_series():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Vector Chart", chart_type="vector")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        style=VectorSeriesStyle(u_column_id=dataset.column_id("u"), v_column_id=dataset.column_id("v")),
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    v_index = tab.v_column_combo.findData(dataset.column_id("u"))
    tab.v_column_combo.setCurrentIndex(v_index)

    assert chart.data_series[0].style.v_column_id == dataset.column_id("u")


def test_refresh_vector_fields_shows_combos_after_a_live_type_switch():
    """Uses a starting chart type of "bar" rather than "line" or "scatter":
    LINE/SCATTER/VECTOR now all mutually allow each other (CHART_TYPE_
    SPECS), so a LINE or SCATTER series would pass through set_chart_type
    untouched when switching to "vector" and the fields would correctly
    stay hidden (that's the scenario the two "non_vector_series" tests
    below cover). A BAR series isn't in Vector's allowed set, so it IS
    retyped to VECTOR, which is what this test needs to exercise the
    fields actually appearing after a live switch."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Chart", chart_type="bar")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.show()
    tab.set_project(project)
    tab.load(chart)
    QApplication.processEvents()
    assert tab.u_column_combo.isVisible() is False

    chart.set_chart_type("vector")  # matches how chart_tab.py drives live type switches
    tab.refresh_vector_fields()
    QApplication.processEvents()

    assert tab.u_column_combo.isVisible() is True


def test_refresh_vector_fields_preserves_the_selected_series_u_v_magnitude():
    """Regression test: repopulating the U/V/magnitude combos (which clears
    them back to their first entry) must not desync from the still-selected
    series' actual column ids -- otherwise the next unrelated edit
    (_on_series_config_changed writes every combo's current value back to
    the series) silently overwrites a correctly-configured vector series."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Vector Chart", chart_type="vector")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
        style=VectorSeriesStyle(
            u_column_id=dataset.column_id("u"), v_column_id=dataset.column_id("v"),
            magnitude_column_id=dataset.column_id("x"),
        ),
        label="v1",
    )
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    tab.refresh_vector_fields()

    assert tab.u_column_combo.currentData() == dataset.column_id("u")
    assert tab.v_column_combo.currentData() == dataset.column_id("v")
    assert tab.magnitude_column_combo.currentData() == dataset.column_id("x")

    # An unrelated edit (e.g. toggling the Y axis) re-reads every combo's
    # current value via _on_series_config_changed -- it must not clobber
    # u/v/magnitude via now-desynced combos.
    tab._on_series_config_changed()

    series = chart.data_series[0]
    assert series.style.u_column_id == dataset.column_id("u")
    assert series.style.v_column_id == dataset.column_id("v")
    assert series.style.magnitude_column_id == dataset.column_id("x")


def test_apply_to_does_not_create_a_vector_series_on_an_empty_chart():
    """Applying an empty vector chart never invents a series, even with U/V picked."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Vector Chart", chart_type="vector")
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)
    # An empty chart has no series yet, so load() alone leaves the x/y/u/v
    # combos empty; _on_dataset_changed (fired by a user picking a dataset)
    # is what populates them.
    tab._on_dataset_changed()
    tab.u_column_combo.setCurrentIndex(tab.u_column_combo.findData(dataset.column_id("u")))
    tab.v_column_combo.setCurrentIndex(tab.v_column_combo.findData(dataset.column_id("v")))

    tab.apply_to(chart)

    assert chart.data_series == []


def test_vector_fields_hidden_for_a_non_vector_series_on_a_vector_typed_chart():
    """Regression test for the Phase 4b set_chart_type redesign: a LINE
    series left on a chart that switched to "vector" (Vector's spec
    allows {VECTOR, LINE}, so set_chart_type leaves it untouched) must
    NOT show U/V/magnitude fields when selected -- those fields are
    driven by the series' own type, not the chart's."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Mixed Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    chart.set_chart_type("vector")
    assert chart.data_series[0].series_type == SeriesType.LINE  # sanity: still LINE, per Phase 4b

    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.show()
    tab.set_project(project)
    tab.load(chart)
    QApplication.processEvents()

    assert tab.u_column_combo.isVisible() is False
    assert tab.v_column_combo.isVisible() is False
    assert tab.magnitude_column_combo.isVisible() is False


def test_editing_u_column_does_not_write_to_a_non_vector_series_on_a_vector_typed_chart():
    """Companion to the visibility test above: even if the (hidden) U/V
    combos hold stale data from a previously-selected vector series,
    _on_series_config_changed must not write it onto a LINE series just
    because the chart itself is vector-typed."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Mixed Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    chart.set_chart_type("vector")
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    tab._on_series_config_changed()

    series = chart.data_series[0]
    assert getattr(series.style, "u_column_id", "") == ""
    assert getattr(series.style, "v_column_id", "") == ""
    assert getattr(series.style, "magnitude_column_id", "") == ""


def test_retyping_an_existing_series_to_vector_does_not_default_uv_to_the_same_real_column():
    """Regression test: the U/V combos must show a blank/unset entry when
    the model's u_column_id/v_column_id are genuinely empty (e.g. right
    after retyping an existing series to VECTOR) -- not silently land on
    the dataset's first real column, which the next unrelated edit would
    then commit as a meaningless u==v vector field."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    chart.set_chart_type("vector")
    project.add_item(chart)

    tab = DataTab(app_context=app_context)
    tab.set_project(project)
    tab.load(chart)

    vector_index = tab.series_type_combo.findData(SeriesType.VECTOR)
    tab.series_type_combo.setCurrentIndex(vector_index)

    assert tab.u_column_combo.currentData() == ""
    assert tab.v_column_combo.currentData() == ""
