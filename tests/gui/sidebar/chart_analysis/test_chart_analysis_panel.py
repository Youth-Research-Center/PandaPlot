"""Tests for ChartAnalysisPanel segment index -> (x, y) preview labels."""
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.chart_analysis.chart_analysis_panel import (
    ChartAnalysisPanel,
)
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def project():
    project = Project(name="P")
    t = np.linspace(0.0, 10.0, 101)
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"t": t, "sq": t ** 2}))
    project.add_item(dataset)

    chart = Chart(id="chart-1", name="C")
    x_id = dataset.column_id("t")
    y_id = dataset.column_id("sq")
    chart.add_data_series(dataset_id="ds-1", x_column_id=x_id, y_column_id=y_id,
                          x_column="t", y_column="sq", label="Squared")
    project.add_item(chart)
    return project


@pytest.fixture
def app_context(project):
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    app_state = Mock(spec=AppState)
    app_state.current_project = project
    ctx.get_app_state.return_value = app_state
    return ctx


@pytest.fixture
def panel(app_context, project):
    panel = ChartAnalysisPanel(app_context)
    panel.current_chart = project.find_item("chart-1")
    panel.current_chart_id = "chart-1"
    panel._populate_sources()
    return panel


class TestChartAnalysisPanelRangeLabels:
    def test_labels_show_no_selection_placeholder_without_source(self, app_context):
        panel = ChartAnalysisPanel(app_context)

        assert panel.start_value_label.text() == "–"
        assert panel.end_value_label.text() == "–"

    def test_start_label_updates_on_index_change(self, panel):
        panel.start_index.setValue(10)

        assert panel.start_value_label.text() == "x=1, y=1"

    def test_end_index_defaults_to_the_last_point(self, panel):
        assert panel.end_index.minimum() == 0
        assert panel.end_index.value() == 100
        assert panel.end_value_label.text() == "x=10, y=100"

    def test_end_label_updates_on_explicit_index(self, panel):
        panel.end_index.setValue(50)

        assert panel.end_value_label.text() == "x=5, y=25"

    def test_end_index_shrinks_the_segment_when_decreased(self, panel):
        panel.end_index.setValue(panel.end_index.value() - 1)

        assert panel.end_value_label.text() == "x=9.9, y=98.01"

    def test_build_parameters_sends_inclusive_end_as_exclusive_boundary(self, panel):
        panel.start_index.setValue(0)
        panel.end_index.setValue(50)

        assert panel._build_parameters()["end_index"] == 51
