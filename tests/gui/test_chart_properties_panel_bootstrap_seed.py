"""Regression test for `ChartPropertiesPanel.apply_to_chart`'s bootstrap-seed
block (chart_properties_panel.py, around line 505-523).

When `DataTab.apply_to(chart)` creates a chart's first-ever series from
scratch (no series existed before `apply_to_chart` ran), the panel used to
seed `color`/`line_width`/`marker_size` directly onto the flat `DataSeries`
fields from whatever the Style tab's Line card widgets currently show. Once
those flat fields were deleted from `DataSeries` (Phase 3c Task 4), the seed
must instead write into the freshly-created series' typed `.style` object
(`marker_size` nested under `.style.marker`), guarded by `hasattr` so it's a
safe no-op for a style class (e.g. a vector chart's `VectorSeriesStyle`) that
doesn't declare `color`/`line_width`/`marker` at all.
"""
import sys

import pandas as pd
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.sidebar.chart.chart_properties_panel import ChartPropertiesPanel
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _make_project_with_dataset():
    project = Project(name="Bootstrap Seed Project")
    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    dataset = Dataset(name="ds", data=df)
    project.add_item(dataset)
    return project, dataset


def test_bootstrap_seed_writes_typed_style_for_line_chart():
    _qapp()
    app_context = build_app_context()
    project, _dataset = _make_project_with_dataset()

    chart = Chart(name="Chart", chart_type="line")
    project.add_item(chart)

    panel = ChartPropertiesPanel(app_context=app_context)
    panel.set_project(project)
    panel.load_chart_object(chart)
    # `_update_datasets` (run by `set_project`) blocks signals while
    # populating `dataset_combo` for exactly the reason documented at its
    # call site -- so the x/y column combos, which populate lazily off
    # `dataset_combo`'s change signal, never got a chance to fire. Do it
    # explicitly here, matching what a user picking the dataset by hand
    # would trigger.
    panel.data_tab._on_dataset_changed()

    assert not chart.data_series  # no series yet -> bootstrap path will fire

    panel.apply_to_chart(chart)

    assert len(chart.data_series) == 1
    series = chart.data_series[0]
    # Seeded from the Style tab's currently-shown Line-card widget values,
    # now living on the typed style object rather than flat fields.
    assert isinstance(series.style.color, str)
    assert isinstance(series.style.line_width, (int, float))
    assert isinstance(series.style.marker.marker_size, (int, float))


def test_bootstrap_seed_is_noop_for_vector_chart_style_fields():
    _qapp()
    app_context = build_app_context()
    project, _dataset = _make_project_with_dataset()

    chart = Chart(name="Chart", chart_type="vector")
    project.add_item(chart)

    panel = ChartPropertiesPanel(app_context=app_context)
    panel.set_project(project)
    panel.load_chart_object(chart)
    panel.data_tab._on_dataset_changed()

    assert not chart.data_series

    # Must not raise, and must not attach bogus color/line_width/marker_size
    # attributes to a VectorSeriesStyle that doesn't declare them.
    panel.apply_to_chart(chart)

    assert len(chart.data_series) == 1
    style = chart.data_series[0].style
    assert not hasattr(style, "color")
    assert not hasattr(style, "line_width")
    assert not hasattr(style, "marker_size")
