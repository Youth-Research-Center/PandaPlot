"""ChartEditorWidget's status label and preview page for charts with and without series."""

import pandas as pd

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget
from pandaplot.models.project.items import Chart, Dataset
from pandaplot.models.project.project import Project


def test_chart_with_no_data_series_shows_no_series_label(qapp):
    project = Project(name="Test Project")
    chart = Chart(name="Empty Chart", chart_type="line")
    project.add_item(chart)

    app_context = build_app_context()
    app_context.app_state.load_project(project)

    widget = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    widget.update_chart()

    assert widget.dataset_label.text() == "No series"
    assert "Chart error" not in widget.status_label.text()


def test_chart_gaining_its_first_series_label_lists_dataset_names(qapp):
    project = Project(name="Test Project")
    dataset = Dataset(name="ds", data=pd.DataFrame({"x": [1, 2], "y": [3, 4]}))
    project.add_item(dataset)
    chart = Chart(name="Chart", chart_type="line")
    project.add_item(chart)

    app_context = build_app_context()
    app_context.app_state.load_project(project)

    widget = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    widget.update_chart()
    assert widget.dataset_label.text() == "No series"

    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    widget.update_chart()
    assert widget.dataset_label.text() == "Datasets: ds"

    chart.data_series.clear()
    widget.refresh_chart()
    assert widget.dataset_label.text() == "No series"
