"""DataTab's twin Y column combo (#402): an optional second value column for a
line/scatter series, plotted on the Y axis opposite the series' own."""
import sys

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart.tabs.data_tab import DataTab
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
    dataset = Dataset(name="ds1", data=pd.DataFrame({"t": [1, 2], "temp": [20, 21], "pressure": [1000, 990]}))
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


def _chart(project, dataset, *, chart_type="line", series_type=SeriesType.LINE, twin: str = "") -> Chart:
    chart = Chart(name="C", chart_type=chart_type)
    style = LineSeriesStyle(twin_y_column_id=dataset.column_id(twin) or "") if series_type == SeriesType.LINE else None
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("t"), y_column_id=dataset.column_id("temp"),
        series_type=series_type, style=style,
    )
    project.add_item(chart)
    return chart


def test_line_series_shows_and_loads_its_twin_y_column():
    app_context, project, dataset = _app_context_with_project()
    chart = _chart(project, dataset, twin="pressure")

    tab = _loaded_tab(app_context, project, chart)

    assert tab.twin_y_column_combo.isVisible() is True
    assert tab.twin_y_column_combo.currentData() == dataset.column_id("pressure")
    assert tab.twin_y_column_label.text() == "Y₂ Column (optional):"


def test_picking_a_twin_y_column_updates_the_series():
    app_context, project, dataset = _app_context_with_project()
    chart = _chart(project, dataset)
    tab = _loaded_tab(app_context, project, chart)
    assert tab.twin_y_column_combo.currentData() == ""

    tab.twin_y_column_combo.setCurrentIndex(tab.twin_y_column_combo.findData(dataset.column_id("pressure")))

    series = chart.data_series[0]
    assert series.style.twin_y_column_id == dataset.column_id("pressure")
    assert series.twin_y_axis == YAxis.SECONDARY


def test_the_twin_y_column_can_be_cleared_to_none():
    app_context, project, dataset = _app_context_with_project()
    chart = _chart(project, dataset, twin="pressure")
    tab = _loaded_tab(app_context, project, chart)

    tab.twin_y_column_combo.setCurrentIndex(tab.twin_y_column_combo.findData(""))

    assert chart.data_series[0].has_twin_y_column is False


def test_moving_the_series_to_y2_relabels_the_twin_row_as_y1():
    app_context, project, dataset = _app_context_with_project()
    chart = _chart(project, dataset, twin="pressure")
    tab = _loaded_tab(app_context, project, chart)

    tab.series_y_axis_control.setCurrentValue(YAxis.SECONDARY)
    tab._on_series_y_axis_changed()

    assert chart.data_series[0].y_axis == YAxis.SECONDARY
    assert tab.twin_y_column_label.text() == "Y₁ Column (optional):"


def test_bar_series_hides_the_twin_y_row():
    app_context, project, dataset = _app_context_with_project()
    chart = _chart(project, dataset, chart_type="bar", series_type=SeriesType.BAR)

    tab = _loaded_tab(app_context, project, chart)

    assert tab.twin_y_column_combo.isVisible() is False
