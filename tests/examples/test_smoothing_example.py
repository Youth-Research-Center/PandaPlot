import numpy as np

from examples.smoothing_derivatives.create_smoothing_example import (
    create_project_data_manager,
    create_signal_data,
    create_smoothing_project,
)
from pandaplot.models.project.items import Chart, Dataset, Note


def test_signal_is_reproducible_and_smoothing_reduces_error():
    data = create_signal_data()
    assert data.equals(create_signal_data())
    assert np.isfinite(data.to_numpy()).all()
    noisy_error = np.mean((data["Noisy signal"] - data["Clean signal"]) ** 2)
    smoothed_error = np.mean((data["Smoothed signal"] - data["Clean signal"]) ** 2)
    assert smoothed_error < noisy_error
    np.testing.assert_allclose(data["First derivative"], np.gradient(data["Smoothed signal"], data["Time (s)"]))


def test_generated_project_round_trip(tmp_path):
    path = create_smoothing_project(tmp_path)
    project = create_project_data_manager().load(str(path))
    assert project.failed_item_ids == []
    items = project.get_all_items()
    charts = [item for item in items if isinstance(item, Chart)]
    datasets = [item for item in items if isinstance(item, Dataset)]
    notes = [item for item in items if isinstance(item, Note)]
    assert len(charts) == 3
    assert len(datasets) == 1
    assert len(notes) == 1
    dataset = datasets[0]
    assert len(dataset.data) == 501
    for chart in charts:
        assert len(chart.data_series) == 2
        for series in chart.data_series:
            assert series.dataset_id == dataset.id
            assert series.x_column_id == dataset.column_id(series.x_column)
            assert series.y_column_id == dataset.column_id(series.y_column)
    assert "polynomial" in notes[0].content.lower()
    assert "endpoint" in notes[0].content.lower()
    assert (tmp_path / "smoothing_derivatives.png").is_file()


def test_loaded_charts_render_in_app(tmp_path, qtbot):
    from pandaplot.app import build_app_context
    from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget

    path = create_smoothing_project(tmp_path)
    project = create_project_data_manager().load(str(path))
    app_context = build_app_context()
    app_context.app_state.load_project(project)
    for chart in (item for item in project.get_all_items() if isinstance(item, Chart)):
        editor = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
        qtbot.addWidget(editor)
        editor.update_chart()
        lines = editor.chart_canvas.axes.lines
        assert len(lines) == 2
        assert all(len(line.get_xdata()) == 501 for line in lines)
        assert all(np.isfinite(line.get_ydata()).all() for line in lines)
