"""ChartEditorWidget-level tests for Box charts (#399): several box series
on one chart sharing the X axis, which no single renderer call can get
right on its own (see series_renderers/box.py)."""
import sys
from itertools import pairwise

import numpy as np
import pandas as pd
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget
from pandaplot.models.chart.series_style import BoxSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _project_and_dataset():
    project = Project(name="Box Render Project")
    df = pd.DataFrame({
        "a": [1.0, 2.0, 3.0, 4.0, 5.0],
        "b": [10.0, 11.0, 12.0, 13.0, 14.0],
        "c": [20.0, 21.0, 22.0, 23.0, 24.0],
        "empty": [np.nan] * 5,
    })
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    return project, dataset


def _box_chart(dataset, columns_and_labels) -> Chart:
    chart = Chart(name="Box Chart", chart_type="box")
    for column, label in columns_and_labels:
        chart.add_data_series(dataset.id, y_column_id=dataset.column_id(column), label=label,
                              series_type=SeriesType.BOX, style=BoxSeriesStyle())
    return chart


def _editor_for(project, chart):
    project.add_item(chart)
    app_context = build_app_context()
    app_context.app_state.load_project(project)
    editor = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    editor.update_chart()
    return editor


def _box_centers(axes) -> list[float]:
    centers = []
    for patch in axes.patches:
        xs = patch.get_path().vertices[:, 0]
        centers.append(round((xs.min() + xs.max()) / 2, 6))
    return centers


def test_three_box_series_land_at_sequential_non_overlapping_positions_with_their_labels():
    """Regression test for the multi-box coordination: each box takes its
    own slot, and the chart-level X tick settings applied after the series
    render (apply_axis_ticks) must not wipe out the boxes' named ticks."""
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _box_chart(dataset, [("a", "Group A"), ("b", "Group B"), ("c", "Group C")])

    editor = _editor_for(project, chart)
    axes = editor.chart_canvas.axes

    assert _box_centers(axes) == [1.0, 2.0, 3.0]
    # Default box_width 0.5 at a 1.0 spacing: neighbouring boxes can't touch.
    extents = sorted((p.get_path().vertices[:, 0].min(), p.get_path().vertices[:, 0].max()) for p in axes.patches)
    for (_, left_max), (right_min, _) in pairwise(extents):
        assert left_max < right_min
    assert list(axes.get_xticks()) == [1, 2, 3]
    assert [t.get_text() for t in axes.get_xticklabels()] == ["Group A", "Group B", "Group C"]


def test_re_rendering_does_not_shift_the_boxes():
    """box_positions is rebuilt every update_chart(); a list carried over
    between renders would push each re-render's boxes further right."""
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _box_chart(dataset, [("a", "A"), ("b", "B")])

    editor = _editor_for(project, chart)
    editor.update_chart()
    editor.update_chart()

    assert _box_centers(editor.chart_canvas.axes) == [1.0, 2.0]
    assert [t.get_text() for t in editor.chart_canvas.axes.get_xticklabels()] == ["A", "B"]


def test_a_box_series_with_no_values_reports_it_and_leaves_no_gap():
    _qapp()
    project, dataset = _project_and_dataset()
    chart = _box_chart(dataset, [("a", "A"), ("empty", "Nothing"), ("c", "C")])

    editor = _editor_for(project, chart)
    axes = editor.chart_canvas.axes

    assert "no plottable data" in editor.status_label.text()
    assert _box_centers(axes) == [1.0, 2.0]
    assert [t.get_text() for t in axes.get_xticklabels()] == ["A", "C"]


def test_box_color_and_opacity_come_from_the_series():
    from matplotlib.colors import to_hex

    _qapp()
    project, dataset = _project_and_dataset()
    chart = Chart(name="Box Chart", chart_type="box")
    series = chart.add_data_series(dataset.id, y_column_id=dataset.column_id("a"), label="A",
                                   series_type=SeriesType.BOX, style=BoxSeriesStyle(color="#00aa00"))
    series.alpha = 0.4

    editor = _editor_for(project, chart)

    (box,) = editor.chart_canvas.axes.patches
    assert to_hex(box.get_facecolor()) == "#00aa00"
    assert box.get_alpha() == 0.4
