"""Characterization test for ChartEditorWidget.update_chart()'s "no data
series" branch -- written before extracting update_chart() (Task 4) so
that refactor has a regression guard for this specific, previously
untested path."""
import pandas as pd

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget
from pandaplot.models.project.items import Chart, Dataset
from pandaplot.models.project.project import Project


def test_chart_with_no_data_series_shows_no_data_loaded_label(qapp):
    project = Project(name="Test Project")
    chart = Chart(name="Empty Chart", chart_type="line")
    project.add_item(chart)

    app_context = build_app_context()
    app_context.app_state.load_project(project)

    widget = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    widget.update_chart()

    assert widget.dataset_label.text() == "No Data Loaded"
    assert "Chart error" not in widget.status_label.text()


def test_chart_gaining_its_first_series_label_remains_unchanged(qapp):
    """Characterize that update_chart() does NOT clear the no-data label when
    series are added: it only sets the label on the no-series branch. The label
    remains "No Data Loaded" even after a series is added and update_chart()
    is called again. This is a latent gap (the label should update but doesn't),
    but this test documents the current actual behavior as-is. Fixing this gap
    is outside Task 0's scope (which only characterizes, not fixes bugs); a fix
    would belong in a separate behavioral task."""
    project = Project(name="Test Project")
    dataset = Dataset(name="ds", data=pd.DataFrame({"x": [1, 2], "y": [3, 4]}))
    project.add_item(dataset)
    chart = Chart(name="Chart", chart_type="line")
    project.add_item(chart)

    app_context = build_app_context()
    app_context.app_state.load_project(project)

    widget = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    widget.update_chart()
    assert widget.dataset_label.text() == "No Data Loaded"

    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    widget.update_chart()
    # update_chart() does NOT update dataset_label when there are series -- it only
    # sets it to "No Data Loaded" in the no-series branch. So the label stays stuck.
    assert widget.dataset_label.text() == "No Data Loaded"
