"""Regression tests: `ChartPropertiesPanel.apply_to_chart` never invents a series.

Apply used to create a chart's first series from the Data tab's combos (and seed its style
from the Style tab). A series now only comes from "+ Add series", so Apply on an empty chart
applies chart, axes and legend settings only.
"""
import sys

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.sidebar.chart.chart_properties_panel import ChartPropertiesPanel
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


@pytest.mark.parametrize("chart_type", ["line", "vector"])
def test_apply_on_an_empty_chart_creates_no_series(chart_type):
    _qapp()
    app_context = build_app_context()
    project = Project(name="Apply Project")
    project.add_item(Dataset(name="ds", data=pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})))
    chart = Chart(name="Chart", chart_type=chart_type)
    project.add_item(chart)

    panel = ChartPropertiesPanel(app_context=app_context)
    panel.set_project(project)
    panel.load_chart_object(chart)
    # The dataset combo is populated with signals blocked, so fire its change handler the way
    # a user picking a dataset would; the form then holds a complete dataset/x/y selection.
    panel.data_tab._on_dataset_changed()
    assert not chart.data_series

    panel.apply_to_chart(chart)

    assert chart.data_series == []
