"""render_chart_to_qimage() is the headless entry point background
rendering (Task 6) calls -- it must produce the same kind of usable
QImage the old synchronous ChartEditorWidget-based path did, without
constructing any Qt widget."""
from unittest.mock import MagicMock

import pandas as pd
from PySide6.QtGui import QImage

from pandaplot.gui.components.tabs.chart.chart_editor import (
    ChartSizeDefaults,
    render_chart,
    render_chart_to_qimage,
    resolve_chart_series_data,
)
from pandaplot.models.project.items import Chart, Dataset
from pandaplot.models.project.project import Project
from pandaplot.services.config.config_manager import ConfigManager


def test_renders_a_real_chart_to_a_non_null_qimage(qapp):
    project = Project(name="Test Project")
    dataset = Dataset(name="ds", data=pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]}))
    project.add_item(dataset)
    chart = Chart(name="Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    project.add_item(chart)

    resolved_series_data = resolve_chart_series_data(project, chart)
    size_defaults = ChartSizeDefaults(default_width_cm=10.0, default_height_cm=8.0, dpi=100)

    qimg = render_chart_to_qimage(chart, resolved_series_data, size_defaults)

    assert isinstance(qimg, QImage)
    assert not qimg.isNull()
    assert qimg.width() > 0 and qimg.height() > 0


def test_returns_none_on_render_failure(qapp, monkeypatch):
    """A render failure must not raise out of this function -- the
    background-task caller (Task 6) treats None as a cache-miss-that-
    stays-a-miss, same as today's synchronous failure handling."""
    from pandaplot.gui.components.tabs.chart import chart_editor

    def _boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(chart_editor, "render_chart", _boom)

    project = Project(name="Test Project")
    chart = Chart(name="Chart", chart_type="line")
    qimg = render_chart_to_qimage(chart, [], ChartSizeDefaults(10.0, 8.0, 100))
    assert qimg is None


def test_headless_and_widget_canvas_render_equivalent_output(qapp):
    """render_chart() against a real ChartCanvas (via ChartEditorWidget)
    and against HeadlessChartCanvas, for the same chart, must produce the
    same axis labels/limits/series count/colorbar presence -- the two
    canvases must not silently diverge in what render_chart() sees."""
    from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget

    project = Project(name="Test Project")
    dataset = Dataset(name="ds", data=pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]}))
    project.add_item(dataset)
    chart = Chart(name="Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"))
    chart.config["title"] = "My Title"
    chart.config["x_label"] = "X Axis"
    project.add_item(chart)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    def _get_manager(manager_cls):
        # ConfigManager must come back as "no config available" (None) so
        # that resolve_chart_size_defaults()/create_chart_preview_section()
        # actually exercise their documented fallback-default branches --
        # a bare MagicMock() auto-vivifies a truthy `.config.chart_display`
        # whose numeric-looking attributes (dpi, default_width_cm, ...) are
        # themselves MagicMocks, which matplotlib chokes on with a
        # "setting an array element with a sequence" ValueError deep in
        # Bbox/transforms once they reach Figure(figsize=...).
        if manager_cls is ConfigManager:
            return None
        theme_manager = MagicMock()
        theme_manager.get_surface_palette.return_value = {}
        return theme_manager

    app_context.get_manager.side_effect = _get_manager

    widget = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    widget.update_chart()

    resolved_series_data = resolve_chart_series_data(project, chart)
    size_defaults = ChartSizeDefaults(default_width_cm=10.0, default_height_cm=8.0, dpi=100)
    from pandaplot.gui.components.tabs.chart.headless_chart_canvas import HeadlessChartCanvas
    headless_canvas = HeadlessChartCanvas()
    render_chart(chart, headless_canvas, resolved_series_data, size_defaults, interactive=False)

    assert widget.chart_canvas.axes.get_xlabel() == headless_canvas.axes.get_xlabel() == "X Axis"
    assert widget.chart_canvas.axes.get_title() == headless_canvas.axes.get_title()
    assert len(widget.chart_canvas.axes.get_lines()) == len(headless_canvas.axes.get_lines()) == 1
