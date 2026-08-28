"""Regression test: re-running `DataTab.set_project` (as happens on every
chart-tab switch) must not silently corrupt the currently selected series'
dataset_id/x_column_id/y_column_id.

Root cause: `_update_datasets()` repopulated `dataset_combo` without
blocking signals, so `currentTextChanged` cascaded into
`_on_series_config_changed` and overwrote the selected series with whatever
dataset landed at combo index 0.
"""
import sys

import pandas as pd
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.sidebar.chart.tabs.data_tab import DataTab
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_reapplying_project_does_not_corrupt_selected_series():
    _qapp()
    app_context = build_app_context()
    project = Project(name="Dataset Refresh Project")

    # Two datasets: "aaa" sorts/iterates before "zzz", so if the combo
    # silently defaults to index 0, it lands on "aaa" -- the bug's
    # observable symptom is the series switching to whichever dataset ends
    # up first in the freshly rebuilt combo.
    df_a = pd.DataFrame({"ax": [1, 2], "ay": [3, 4]})
    dataset_a = Dataset(name="aaa", data=df_a)
    project.add_item(dataset_a)

    df_z = pd.DataFrame({"zx": [5, 6], "zy": [7, 8]})
    dataset_z = Dataset(name="zzz", data=df_z)
    project.add_item(dataset_z)

    chart = Chart(name="Chart", chart_type="line")
    chart.add_data_series(
        dataset_z.id,
        x_column_id=dataset_z.column_id("zx"),
        y_column_id=dataset_z.column_id("zy"),
        label="Series on zzz",
    )
    project.add_item(chart)

    data_tab = DataTab(app_context=app_context)
    data_tab.set_project(project)
    data_tab.load(chart)

    series = chart.data_series[0]
    assert series.dataset_id == dataset_z.id

    # Simulate revisiting the chart tab: ChartPropertiesPanel._on_tab_changed
    # calls set_project on every switch, regardless of whether anything
    # about the project actually changed.
    data_tab.set_project(project)

    assert series.dataset_id == dataset_z.id
    assert series.x_column_id == dataset_z.column_id("zx")
    assert series.y_column_id == dataset_z.column_id("zy")


def test_reapplying_project_preserves_combo_selection_and_picks_up_new_label():
    """Regression test: `_update_datasets()` used to clear+repopulate
    `dataset_combo` without restoring the previously selected entry, so a
    rename-triggered refresh (ChartPropertiesPanel.PROJECT_ITEM_RENAMED
    handler) would silently desync the combo's visible selection from the
    series actually loaded into the form -- it would fall back to whichever
    dataset landed at index 0 after the rebuild."""
    _qapp()
    app_context = build_app_context()
    project = Project(name="Dataset Refresh Project")

    df_a = pd.DataFrame({"ax": [1, 2], "ay": [3, 4]})
    dataset_a = Dataset(name="aaa", data=df_a)
    project.add_item(dataset_a)

    df_z = pd.DataFrame({"zx": [5, 6], "zy": [7, 8]})
    dataset_z = Dataset(name="zzz", data=df_z)
    project.add_item(dataset_z)

    chart = Chart(name="Chart", chart_type="line")
    chart.add_data_series(
        dataset_z.id,
        x_column_id=dataset_z.column_id("zx"),
        y_column_id=dataset_z.column_id("zy"),
        label="Series on zzz",
    )
    project.add_item(chart)

    data_tab = DataTab(app_context=app_context)
    data_tab.set_project(project)
    data_tab.load(chart)

    assert data_tab.dataset_combo.currentData() == dataset_z.id

    # Simulate renaming "zzz" while this chart's properties panel is open.
    dataset_z.update_name("zzz renamed")
    data_tab.set_project(project)

    assert data_tab.dataset_combo.currentData() == dataset_z.id
    assert data_tab.dataset_combo.currentText() == "zzz renamed"
