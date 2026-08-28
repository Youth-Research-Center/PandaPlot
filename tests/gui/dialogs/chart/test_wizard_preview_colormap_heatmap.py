"""Tests for the wizard Labels step's Colormap/Heatmap preview."""
import sys

import pandas as pd
from matplotlib.collections import PathCollection, QuadMesh
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.tabs.chart.chart_canvas import ChartCanvas
from pandaplot.gui.dialogs.chart.wizard_preview import render_wizard_preview
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.project import Project


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_colormap_preview_with_no_series_falls_back_to_sample_scatter():
    _qapp()
    canvas = ChartCanvas(width=4, height=3, dpi=80)

    render_wizard_preview(canvas, None, "colormap", [], "Title", "", "X", "Y", show_legend=True, show_grid=True)

    scatters = [c for c in canvas.axes.collections if isinstance(c, PathCollection)]
    assert len(scatters) == 1


def test_heatmap_preview_with_no_series_falls_back_to_sample_pcolormesh():
    _qapp()
    canvas = ChartCanvas(width=4, height=3, dpi=80)

    render_wizard_preview(canvas, None, "heatmap", [], "Title", "", "X", "Y", show_legend=True, show_grid=True)

    meshes = [c for c in canvas.axes.collections if isinstance(c, QuadMesh)]
    assert len(meshes) == 1


def _project_with_grid_dataset():
    project = Project(name="Preview Project")
    df = pd.DataFrame({
        "x": [0, 0, 1, 1],
        "y": [0, 1, 0, 1],
        "z": [1.0, 2.0, 3.0, 4.0],
    })
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    return project, dataset


def test_colormap_preview_with_a_configured_series_draws_real_data():
    _qapp()
    canvas = ChartCanvas(width=4, height=3, dpi=80)
    project, dataset = _project_with_grid_dataset()

    series_configs = [{
        "dataset_id": dataset.id,
        "x_column_id": dataset.column_id("x"), "y_column_id": dataset.column_id("y"),
        "z_column_id": dataset.column_id("z"),
    }]

    render_wizard_preview(canvas, project, "colormap", series_configs, "Title", "", "X", "Y", show_legend=True, show_grid=True)

    scatters = [c for c in canvas.axes.collections if isinstance(c, PathCollection)]
    assert len(scatters) == 1
    assert list(scatters[0].get_array()) == [1.0, 2.0, 3.0, 4.0]


def test_heatmap_preview_with_a_configured_series_draws_real_data():
    _qapp()
    canvas = ChartCanvas(width=4, height=3, dpi=80)
    project, dataset = _project_with_grid_dataset()

    series_configs = [{
        "dataset_id": dataset.id,
        "x_column_id": dataset.column_id("x"), "y_column_id": dataset.column_id("y"),
        "z_column_id": dataset.column_id("z"),
    }]

    render_wizard_preview(canvas, project, "heatmap", series_configs, "Title", "", "X", "Y", show_legend=True, show_grid=True)

    meshes = [c for c in canvas.axes.collections if isinstance(c, QuadMesh)]
    assert len(meshes) == 1


def test_heatmap_preview_second_series_failing_to_grid_does_not_erase_the_first():
    """`any_plotted` used to be reset to False whenever a LATER series
    failed to grid, even after an EARLIER series had already drawn real
    data -- triggering the sample-data fallback to draw ON TOP of the
    already-rendered real mesh and suppressing the legend for it.
    Flagged in PR #190 review."""
    _qapp()
    canvas = ChartCanvas(width=4, height=3, dpi=80)
    project = Project(name="Preview Project")
    df = pd.DataFrame({
        "x": [0, 0, 1, 1],
        "y": [0, 1, 0, 1],
        "z": [1.0, 2.0, 3.0, 4.0],
        # A second X/Y pair that resolves fine (real columns, so
        # resolve_series_data reports no error) but is entirely non-finite,
        # so build_heatmap_grid's finite-coordinate filter leaves nothing
        # to grid and raises ValueError.
        "x_allnan": [float("nan")] * 4,
        "y_allnan": [float("nan")] * 4,
    })
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)

    good_series = {
        "dataset_id": dataset.id,
        "x_column_id": dataset.column_id("x"), "y_column_id": dataset.column_id("y"),
        "z_column_id": dataset.column_id("z"),
    }
    ungriddable_series = {
        "dataset_id": dataset.id,
        "x_column_id": dataset.column_id("x_allnan"), "y_column_id": dataset.column_id("y_allnan"),
        "z_column_id": dataset.column_id("z"),
    }

    render_wizard_preview(
        canvas, project, "heatmap", [good_series, ungriddable_series],
        "Title", "", "X", "Y", show_legend=True, show_grid=True,
    )

    meshes = [c for c in canvas.axes.collections if isinstance(c, QuadMesh)]
    # Exactly one mesh: the real, successfully-gridded first series --
    # NOT two (real + sample-data fallback drawn on top of it). That count
    # is the whole assertion now: it was previously paired with a
    # `get_legend() is not None` check as an indirect proxy for
    # `any_plotted` staying True, but the preview no longer draws an empty
    # legend box for a chart type whose artists carry no label (a heatmap's
    # QuadMesh has no legend handler), so the proxy no longer holds. The
    # mesh count covers the same ground directly: a reset `any_plotted`
    # would have drawn the sample fallback here as a second mesh.
    assert len(meshes) == 1
