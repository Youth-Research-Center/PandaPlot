"""Tests for the chart wizard's 3-D support (issue #98): both previews
switching the canvas to an mplot3d projection, and the sample-data
preview being genuinely shared between the Type and Labels steps.
"""
import sys

import pandas as pd
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.chart.chart_canvas import ChartCanvas
from pandaplot.gui.dialogs.chart.chart_type_page import ChartTypePage
from pandaplot.gui.dialogs.chart.series_config_card import SeriesConfigCard
from pandaplot.gui.dialogs.chart.wizard_preview import (
    draw_chart_type_sample,
    render_wizard_preview,
)
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.project import Project

_3D_CHART_TYPES = [
    ChartType.SCATTER3D, ChartType.LINE3D, ChartType.SURFACE,
    ChartType.WIREFRAME, ChartType.BAR3D, ChartType.TRISURF,
]


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def _canvas():
    return ChartCanvas(width=4, height=3, dpi=80)


def _project_with_lattice():
    project = Project(name="Preview Project")
    side = 4
    x = [float(i) for i in range(side) for _ in range(side)]
    y = [float(j) for _ in range(side) for j in range(side)]
    df = pd.DataFrame({"x": x, "y": y, "z": [a + b for a, b in zip(x, y, strict=True)]})
    dataset = Dataset(name="ds1", data=df)
    project.add_item(dataset)
    return project, dataset


@pytest.mark.parametrize("chart_type", [chart_type.value for chart_type in ChartType])
def test_the_sample_preview_draws_something_for_every_chart_type(chart_type):
    """The Type step must never show empty axes -- and since this is the
    shared sample renderer, that guarantee covers the Labels step's
    fallback too."""
    canvas = _canvas()

    draw_chart_type_sample(canvas, chart_type)

    axes = canvas.axes
    drew_something = bool(axes.collections) or bool(axes.get_lines()) or bool(axes.patches)
    assert drew_something, f"{chart_type} sample preview drew nothing"


@pytest.mark.parametrize("chart_type", [chart_type.value for chart_type in ChartType])
def test_the_sample_preview_uses_the_projection_the_chart_type_needs(chart_type):
    canvas = _canvas()

    draw_chart_type_sample(canvas, chart_type)

    assert canvas.is_3d is CHART_TYPE_SPECS[ChartType(chart_type)].is_3d


def test_the_sample_preview_canvas_switches_projection_on_a_type_change():
    """The Labels step reuses one canvas across type changes, so the switch
    has to work in both directions on a live canvas, not just at build."""
    canvas = _canvas()

    draw_chart_type_sample(canvas, "surface")
    assert canvas.is_3d is True

    draw_chart_type_sample(canvas, "line")
    assert canvas.is_3d is False


@pytest.mark.parametrize("chart_type", _3D_CHART_TYPES)
def test_a_configured_3d_series_renders_real_data_in_the_labels_preview(chart_type):
    canvas = _canvas()
    project, dataset = _project_with_lattice()
    series_configs = [{
        "dataset_id": dataset.id,
        "x_column_id": dataset.column_id("x"),
        "y_column_id": dataset.column_id("y"),
        "z_column_id": dataset.column_id("z"),
    }]

    render_wizard_preview(canvas, project, chart_type.value, series_configs,
                           "Title", "", "X", "Y", show_legend=True, show_grid=True)

    assert canvas.is_3d is True
    axes = canvas.axes
    assert bool(axes.collections) or bool(axes.get_lines())


def test_a_3d_series_missing_its_z_column_falls_back_to_the_sample():
    """An incomplete series resolves with an error, and the preview must
    still show the chart type rather than empty axes."""
    canvas = _canvas()
    project, dataset = _project_with_lattice()
    series_configs = [{
        "dataset_id": dataset.id,
        "x_column_id": dataset.column_id("x"),
        "y_column_id": dataset.column_id("y"),
        "z_column_id": "",
    }]

    render_wizard_preview(canvas, project, "surface", series_configs,
                           "Title", "", "X", "Y", show_legend=True, show_grid=True)

    assert canvas.is_3d is True
    assert bool(canvas.axes.collections)


@pytest.mark.parametrize("chart_type", _3D_CHART_TYPES)
def test_the_type_step_previews_every_3d_chart_type(chart_type):
    app_context = build_app_context()
    page = ChartTypePage(app_context=app_context)

    row = next(
        row for row in range(page.type_list.count())
        if page.type_list.item(row).data(Qt.ItemDataRole.UserRole) == chart_type
    )
    page.type_list.setCurrentRow(row)

    assert page._preview_canvas.is_3d is True


@pytest.mark.parametrize("chart_type", _3D_CHART_TYPES)
def test_a_3d_series_config_card_asks_for_x_y_and_z(chart_type):
    card = SeriesConfigCard(CHART_TYPE_SPECS[chart_type])

    assert card.x_column_combo is not None
    assert card.y_column_combo is not None
    assert card.z_column_combo is not None
    # mplot3d has no errorbar(), so the card must not offer error bars.
    assert card.error_bars_check is None


def test_a_3d_series_config_card_requires_all_three_columns():
    card = SeriesConfigCard(CHART_TYPE_SPECS[ChartType.SURFACE])
    card.set_datasets([("ds-1", "ds1")])
    card.set_dataset_columns("ds-1", [("col-x", "x"), ("col-y", "y"), ("col-z", "z")])

    assert card.is_complete() is False

    for role, column_id in (("x", "col-x"), ("y", "col-y"), ("z", "col-z")):
        card.apply_picked_columns(role, [column_id])

    assert card.is_complete() is True
    assert card.get_series_config()["z_column_id"] == "col-z"
