"""DataTab's Pie support (#397): the optional Labels column combo, and the
(x, y)-only rows hidden for a series/chart that has no use for them."""
import sys

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.data_tab import DataTab
from pandaplot.models.chart.series_style import PieSeriesStyle
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
    dataset = Dataset(name="ds1", data=pd.DataFrame({"name": ["a", "b"], "count": [1, 2], "other": ["c", "d"]}))
    project.add_item(dataset)
    app_context.app_state.load_project(project)
    return app_context, project, dataset


def _loaded_tab(app_context, project, chart) -> DataTab:
    tab = DataTab(app_context=app_context)
    tab.show()
    tab.set_project(project)
    tab.load(chart)
    # The series form is reparented into the selected card; Qt only flips
    # its widgets' shown-state once the event loop processes that.
    QApplication.processEvents()
    return tab


def _pie_chart(project, dataset, *, label_column: str = "name") -> Chart:
    chart = Chart(name="Pie", chart_type="pie")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("name"), y_column_id=dataset.column_id("count"),
        series_type="pie", style=PieSeriesStyle(label_column_id=dataset.column_id(label_column)),
    )
    project.add_item(chart)
    return chart


def test_pie_series_shows_and_loads_its_labels_column():
    app_context, project, dataset = _app_context_with_project()
    chart = _pie_chart(project, dataset)

    tab = _loaded_tab(app_context, project, chart)

    assert tab.label_column_combo.isVisible() is True
    assert tab.label_column_combo.currentData() == dataset.column_id("name")


def test_editing_the_labels_column_updates_the_series():
    app_context, project, dataset = _app_context_with_project()
    chart = _pie_chart(project, dataset)
    tab = _loaded_tab(app_context, project, chart)

    tab.label_column_combo.setCurrentIndex(tab.label_column_combo.findData(dataset.column_id("other")))

    assert chart.data_series[0].style.label_column_id == dataset.column_id("other")


def test_the_labels_column_can_be_cleared_to_none():
    app_context, project, dataset = _app_context_with_project()
    chart = _pie_chart(project, dataset)
    tab = _loaded_tab(app_context, project, chart)

    tab.label_column_combo.setCurrentIndex(tab.label_column_combo.findData(""))

    assert chart.data_series[0].style.label_column_id == ""


def test_pie_series_hides_x_column_y_axis_and_error_rows_and_names_the_values_column():
    app_context, project, dataset = _app_context_with_project()
    chart = _pie_chart(project, dataset)

    tab = _loaded_tab(app_context, project, chart)

    assert tab.x_column_combo.isVisible() is False
    assert tab.series_y_axis_control.isVisible() is False
    assert tab.x_error_column_combo.isVisible() is False
    assert tab.error_asymmetric_check.isVisible() is False
    assert tab.y_column_label.text() == "Values Column:"
    assert tab._expanded_card_y_axis_badge.isVisible() is False


def test_a_line_series_keeps_every_xy_row_and_offers_no_labels_column():
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Line", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("count"), y_column_id=dataset.column_id("count"))
    project.add_item(chart)

    tab = _loaded_tab(app_context, project, chart)

    assert tab.label_column_combo.isVisible() is False
    assert tab.x_column_combo.isVisible() is True
    assert tab.series_y_axis_control.isVisible() is True
    assert tab.x_error_column_combo.isVisible() is True
    assert tab.y_column_label.text() == "Y Column:"


def test_a_histogram_series_hides_its_unused_x_column_but_keeps_its_y_axis():
    """Hist plots a single values column (needs_x_column=False) but, unlike
    a pie, still sits on real axes, so the Y-axis choice stays."""
    app_context, project, dataset = _app_context_with_project()
    chart = Chart(name="Hist", chart_type="hist")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("count"), y_column_id=dataset.column_id("count"))
    project.add_item(chart)

    tab = _loaded_tab(app_context, project, chart)

    assert tab.x_column_combo.isVisible() is False
    assert tab.y_column_label.text() == "Values Column:"
    assert tab.series_y_axis_control.isVisible() is True


def test_add_series_on_a_pie_chart_carries_the_labels_column():
    app_context, project, dataset = _app_context_with_project()
    chart = _pie_chart(project, dataset)
    tab = _loaded_tab(app_context, project, chart)

    tab._add_series()

    new_series = chart.data_series[-1]
    assert new_series.series_type == "pie"
    assert new_series.style.label_column_id == dataset.column_id("name")
