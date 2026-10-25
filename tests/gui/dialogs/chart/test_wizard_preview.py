"""Tests for render_wizard_preview."""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.chart.wizard_preview import render_wizard_preview


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _canvas():
    from pandaplot.gui.components.tabs.chart.chart_canvas import ChartCanvas
    return ChartCanvas(width=3, height=2, dpi=60)


def _project_with_dataset(dataset_id="ds-1", dataset_name="Sales"):
    import pandas as pd

    from pandaplot.models.project.items import Dataset

    dataset = Mock(spec=Dataset)
    dataset.id = dataset_id
    dataset.name = dataset_name
    dataset.data = pd.DataFrame({"Date": [1, 2, 3], "Revenue": [10, 20, 15]})
    dataset.column_id.side_effect = lambda name: {"Date": "col-date", "Revenue": "col-rev"}.get(name)
    dataset.column_name.side_effect = lambda cid: {"col-date": "Date", "col-rev": "Revenue"}.get(cid)

    project = Mock()
    project.find_item.return_value = dataset
    return project


def test_renders_without_error_when_project_is_none():
    canvas = _canvas()

    render_wizard_preview(
        canvas, project=None, chart_type="line", series_configs=[],
        title="My Chart", subtitle="", x_label="X", y_label="Y",
        show_legend=True, show_grid=True,
    )

    assert canvas.axes.get_title() == "My Chart"


def test_sets_title_and_axis_labels():
    canvas = _canvas()

    render_wizard_preview(
        canvas, project=None, chart_type="line", series_configs=[],
        title="Voltage vs time", subtitle="", x_label="t (s)", y_label="V (mV)",
        show_legend=True, show_grid=True,
    )

    assert canvas.axes.get_title() == "Voltage vs time"
    assert canvas.axes.get_xlabel() == "t (s)"
    assert canvas.axes.get_ylabel() == "V (mV)"


def test_plots_a_real_series_when_project_resolves_it():
    canvas = _canvas()
    project = _project_with_dataset()
    series_configs = [{
        "dataset_id": "ds-1", "x_column_id": "col-date", "y_column_id": "col-rev",
        "x_error_column_id": "", "y_error_column_id": "", "error_symmetric": True,
    }]

    render_wizard_preview(
        canvas, project=project, chart_type="line", series_configs=series_configs,
        title="", subtitle="", x_label="", y_label="", show_legend=True, show_grid=True,
    )

    assert len(canvas.axes.get_lines()) == 1


def test_renders_without_error_when_axis_label_has_invalid_mathtext():
    """Regression test for issue #194: an incomplete mathtext label (e.g.
    `$\\theta_$`, missing its subscript body) used to raise a ValueError out
    of matplotlib's mathtext parser during canvas.draw(), breaking the
    wizard preview instead of just falling back to literal text."""
    canvas = _canvas()

    render_wizard_preview(
        canvas, project=None, chart_type="line", series_configs=[],
        title="", subtitle="", x_label=r"$\theta_$", y_label="Y",
        show_legend=True, show_grid=True,
    )

    assert canvas.axes.get_xlabel() == r"$\theta_$"


def test_grid_off_disables_gridlines():
    canvas = _canvas()

    render_wizard_preview(
        canvas, project=None, chart_type="line", series_configs=[],
        title="", subtitle="", x_label="", y_label="", show_legend=True, show_grid=False,
    )

    assert not canvas.axes.xaxis.get_gridlines()[0].get_visible()


def test_title_and_subtitle_combine_into_one_title_instead_of_overlapping():
    """Regression: a separately-drawn subtitle `axes.text(...)` landed in the
    same vertical band as `axes.set_title`, visually colliding with it."""
    canvas = _canvas()

    render_wizard_preview(
        canvas, project=None, chart_type="line", series_configs=[],
        title="Revenue", subtitle="Q1 2026", x_label="", y_label="",
        show_legend=True, show_grid=True,
    )

    title = canvas.axes.get_title()
    assert "\n" in title
    assert "Revenue" in title
    assert "Q1 2026" in title


def test_legend_shows_a_readable_name_not_the_raw_dataset_id():
    """Regression: the preview's legend showed the opaque dataset id (e.g.
    "ds-1") instead of a readable "{dataset name}:{column name}" label."""
    canvas = _canvas()
    project = _project_with_dataset(dataset_name="Sales")
    series_configs = [{
        "dataset_id": "ds-1", "x_column_id": "col-date", "y_column_id": "col-rev",
        "x_error_column_id": "", "y_error_column_id": "", "error_symmetric": True,
    }]

    render_wizard_preview(
        canvas, project=project, chart_type="line", series_configs=series_configs,
        title="", subtitle="", x_label="", y_label="", show_legend=True, show_grid=True,
    )

    label = canvas.axes.get_lines()[0].get_label()
    assert label == "Sales:Revenue"
    assert "ds-1" not in label


def test_box_preview_places_each_series_box_side_by_side():
    """The preview shares one `extra` dict across all its series, which is
    what lets several Box series find their own X slots (#399)."""
    canvas = _canvas()
    project = _project_with_dataset(dataset_name="Sales")
    series_configs = [
        {"dataset_id": "ds-1", "y_column_id": "col-rev"},
        {"dataset_id": "ds-1", "y_column_id": "col-date"},
    ]

    render_wizard_preview(
        canvas, project=project, chart_type="box", series_configs=series_configs,
        title="", subtitle="", x_label="", y_label="", show_legend=True, show_grid=True,
    )

    assert len(canvas.axes.patches) == 2
    assert list(canvas.axes.get_xticks()) == [1, 2]
    assert [t.get_text() for t in canvas.axes.get_xticklabels()] == ["Sales:Revenue", "Sales:Date"]


def test_box_preview_falls_back_to_the_sample_box_with_no_series():
    canvas = _canvas()

    render_wizard_preview(
        canvas, project=None, chart_type="box", series_configs=[],
        title="", subtitle="", x_label="", y_label="", show_legend=True, show_grid=True,
    )

    assert len(canvas.axes.patches) == 1
