"""Regression test for PR #383 review: `DataTab.dirtyOnly`-routed edits
(series dataset/X/Y/Y-axis changes) deliberately don't publish
`ChartEvents.CHART_UPDATED` (see `ChartPropertiesPanel._on_dirty_only`'s own
docstring for why -- routing them through CHART_UPDATED would fire it on
every keystroke-driven combo change, a behavior change a prior refactor was
explicitly careful to avoid).

But nothing else was told these edits happened either, so a note's cached
render of that chart (see NoteEditorWidget.on_chart_or_dataset_changed_event)
stayed stale until the user clicked Apply. `DataTab` now emits a second,
narrower signal (`chartDataChanged`) only from handlers that actually just
mutated chart state, and `ChartPropertiesPanel._on_chart_data_changed`
(wired to it) publishes the previously-unwired `ChartEvents.
CHART_DATA_UPDATED` from there -- purely so such a cache can invalidate the
one affected chart without reintroducing the CHART_UPDATED frequency
problem.

`chartDataChanged` is deliberately NOT emitted alongside the generic
`dirtyOnly` marker everywhere: `_on_label_typing` marks dirty on every
keystroke before the label is actually written to the model (see its own
docstring), so wiring cache invalidation to `dirtyOnly` itself reintroduced
the exact per-keystroke synchronous chart re-render this split was meant to
avoid (PR #383 review).
"""
import sys

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.sidebar.chart.chart_properties_panel import ChartPropertiesPanel
from pandaplot.models.events.event_types import ChartEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart, YAxis
from pandaplot.models.project.project import Project


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_dirty_only_edit_publishes_chart_data_updated_not_chart_updated():
    _qapp()
    app_context = build_app_context()
    project = Project(name="Test Project")
    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    dataset = Dataset(name="ds", data=df)
    project.add_item(dataset)

    chart = Chart(name="Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    panel = ChartPropertiesPanel(app_context=app_context)
    panel.set_project(project)
    panel.load_chart_object(chart)

    published = []
    app_context.event_bus.subscribe(
        ChartEvents.CHART_DATA_UPDATED, lambda data: published.append(("data_updated", data))
    )
    app_context.event_bus.subscribe(
        ChartEvents.CHART_UPDATED, lambda data: published.append(("updated", data))
    )

    assert panel.data_tab._expanded_series_index == 0  # first series auto-expanded by load()
    # setCurrentValue() alone never emits currentValueChanged (see
    # SegmentedControl._select_button) -- only an actual click does, same as
    # a real user toggling the Y-axis segment.
    secondary_index = panel.data_tab.series_y_axis_control._values.index(YAxis.SECONDARY)
    panel.data_tab.series_y_axis_control._buttons[secondary_index].click()

    data_updated_calls = [data for kind, data in published if kind == "data_updated"]
    assert any(data.get("chart_id") == chart.id for data in data_updated_calls)
    assert not any(kind == "updated" for kind, _ in published)


def test_label_keystroke_does_not_publish_chart_data_updated(qtbot):
    """`_on_label_typing` marks the panel dirty on every keystroke before
    writing anything to the model, so it must not also fire
    CHART_DATA_UPDATED -- doing so would evict and synchronously
    re-render a visible note's cached chart preview on every keystroke
    (see PR #383 review)."""
    _qapp()
    app_context = build_app_context()
    project = Project(name="Test Project")
    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    dataset = Dataset(name="ds", data=df)
    project.add_item(dataset)

    chart = Chart(name="Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    panel = ChartPropertiesPanel(app_context=app_context)
    panel.set_project(project)
    panel.load_chart_object(chart)

    published = []
    app_context.event_bus.subscribe(
        ChartEvents.CHART_DATA_UPDATED, lambda data: published.append(data)
    )

    qtbot.keyClicks(panel.data_tab.series_label_edit, "My Label")
    assert published == []

    qtbot.keyClick(panel.data_tab.series_label_edit, Qt.Key.Key_Return)
    assert any(data.get("chart_id") == chart.id for data in published)
