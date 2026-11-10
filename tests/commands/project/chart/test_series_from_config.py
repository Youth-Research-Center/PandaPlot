"""Tests for the shared series construction helpers."""
from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.project.chart.series_from_config import (
    build_series_from_config,
    dataset_columns,
)
from pandaplot.models.chart.series_style.heatmap import HeatmapSeriesStyle
from pandaplot.models.chart.series_style.line import LineSeriesStyle
from pandaplot.models.chart.series_style.pie import PieSeriesStyle
from pandaplot.models.chart.series_style.scatter3d import Scatter3DSeriesStyle
from pandaplot.models.chart.series_style.vector import VectorSeriesStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import YAxis


@pytest.fixture
def dataset() -> Dataset:
    return Dataset(
        id="ds-1",
        name="Measurements",
        data=pd.DataFrame({"t": [1, 2], "v": [3, 4], "e": [0.1, 0.2], "e2": [0.3, 0.4], "u": [1, 1], "z": [5, 6]}),
    )


@pytest.fixture
def project(dataset):
    project = Mock()
    project.find_item.side_effect = lambda item_id: dataset if item_id == dataset.id else None
    project.get_all_items.return_value = [dataset]
    return project


def _cid(dataset: Dataset, name: str) -> str:
    column_id = dataset.column_id(name)
    assert column_id
    return column_id


def test_dataset_columns_returns_id_name_pairs(project, dataset):
    assert dataset_columns(project, "ds-1") == [(_cid(dataset, n), n) for n in dataset.data.columns]


def test_dataset_columns_empty_for_missing_dataset(project):
    assert dataset_columns(project, "nope") == []


def test_dataset_columns_empty_for_non_dataset_item(project):
    project.find_item.side_effect = None
    project.find_item.return_value = Mock()
    assert dataset_columns(project, "ds-1") == []


def test_dataset_columns_empty_when_data_is_none(project, dataset):
    dataset.data = None
    assert dataset_columns(project, "ds-1") == []


def test_line_with_x_and_y(project, dataset):
    series = build_series_from_config(
        project, "line",
        {"dataset_id": "ds-1", "x_column_id": _cid(dataset, "t"), "y_column_id": _cid(dataset, "v")},
        color="#112233",
    )
    assert series.series_type is SeriesType.LINE
    assert series.dataset_id == "ds-1"
    assert series.x_column_id == _cid(dataset, "t")
    assert series.y_column_id == _cid(dataset, "v")
    assert isinstance(series.style, LineSeriesStyle)
    assert series.style.color == "#112233"
    assert series.label == "Measurements:v"


def test_line_without_x(project, dataset):
    series = build_series_from_config(
        project, "line", {"dataset_id": "ds-1", "y_column_id": _cid(dataset, "v")}, color="#112233",
    )
    assert series.x_column_id == ""
    assert series.y_column_id == _cid(dataset, "v")


def test_histogram_values(project, dataset):
    series = build_series_from_config(
        project, "hist", {"dataset_id": "ds-1", "y_column_id": _cid(dataset, "v")}, color="#112233",
    )
    assert series.series_type is SeriesType.HIST
    assert series.y_column_id == _cid(dataset, "v")
    assert series.x_column_id == ""


def test_pie_values_and_labels(project, dataset):
    series = build_series_from_config(
        project, "pie",
        {"dataset_id": "ds-1", "y_column_id": _cid(dataset, "v"), "label_column_id": _cid(dataset, "t")},
        color="#112233",
    )
    assert series.series_type is SeriesType.PIE
    assert isinstance(series.style, PieSeriesStyle)
    assert series.style.label_column_id == _cid(dataset, "t")


def test_vector_with_u_v_and_magnitude(project, dataset):
    series = build_series_from_config(
        project, "vector",
        {
            "dataset_id": "ds-1", "x_column_id": _cid(dataset, "t"), "y_column_id": _cid(dataset, "v"),
            "u_column_id": _cid(dataset, "u"), "v_column_id": _cid(dataset, "e"), "magnitude_column_id": _cid(dataset, "z"),
        },
        color="#112233",
    )
    assert series.series_type is SeriesType.VECTOR
    assert isinstance(series.style, VectorSeriesStyle)
    assert series.style.u_column_id == _cid(dataset, "u")
    assert series.style.v_column_id == _cid(dataset, "e")
    assert series.style.magnitude_column_id == _cid(dataset, "z")
    assert series.style.vector_color == "#112233"


def test_heatmap_x_y_z(project, dataset):
    series = build_series_from_config(
        project, "heatmap",
        {"dataset_id": "ds-1", "x_column_id": _cid(dataset, "t"), "y_column_id": _cid(dataset, "v"), "z_column_id": _cid(dataset, "z")},
        color="#112233",
    )
    assert series.series_type is SeriesType.HEATMAP
    assert isinstance(series.style, HeatmapSeriesStyle)
    assert series.style.z_column_id == _cid(dataset, "z")


def test_scatter3d_z(project, dataset):
    series = build_series_from_config(
        project, "scatter3d",
        {"dataset_id": "ds-1", "x_column_id": _cid(dataset, "t"), "y_column_id": _cid(dataset, "v"), "z_column_id": _cid(dataset, "z")},
        color="#112233",
    )
    assert series.series_type is SeriesType.SCATTER3D
    assert isinstance(series.style, Scatter3DSeriesStyle)
    assert series.style.z_column_id == _cid(dataset, "z")


def test_box_is_on_primary_axis(project, dataset):
    series = build_series_from_config(
        project, "box", {"dataset_id": "ds-1", "y_column_id": _cid(dataset, "v")}, color="#112233",
    )
    assert series.series_type is SeriesType.BOX
    assert series.y_axis is YAxis.PRIMARY


def test_symmetric_error_bars(project, dataset):
    series = build_series_from_config(
        project, "line",
        {
            "dataset_id": "ds-1", "x_column_id": _cid(dataset, "t"), "y_column_id": _cid(dataset, "v"),
            "y_error_column_id": _cid(dataset, "e"), "x_error_column_id": _cid(dataset, "e2"),
        },
        color="#112233",
    )
    bars = series.style.error_bars
    assert bars.y_error_column_id == _cid(dataset, "e")
    assert bars.x_error_column_id == _cid(dataset, "e2")
    assert bars.error_symmetric is True
    assert bars.y_error_minus_column_id == ""


def test_asymmetric_error_bars(project, dataset):
    series = build_series_from_config(
        project, "line",
        {
            "dataset_id": "ds-1", "x_column_id": _cid(dataset, "t"), "y_column_id": _cid(dataset, "v"),
            "y_error_column_id": _cid(dataset, "e"), "y_error_minus_column_id": _cid(dataset, "e2"),
            "x_error_minus_column_id": _cid(dataset, "u"), "error_symmetric": False,
        },
        color="#112233",
    )
    bars = series.style.error_bars
    assert bars.error_symmetric is False
    assert bars.y_error_column_id == _cid(dataset, "e")
    assert bars.y_error_minus_column_id == _cid(dataset, "e2")
    assert bars.x_error_minus_column_id == _cid(dataset, "u")


def test_label_falls_back_to_dataset_name_without_y_column(project):
    series = build_series_from_config(project, "line", {"dataset_id": "ds-1"}, color="#112233")
    assert series.label == "Measurements"


def test_label_falls_back_to_dataset_id_for_unknown_dataset(project):
    series = build_series_from_config(project, "line", {"dataset_id": "gone", "y_column_id": "c"}, color="#112233")
    assert series.label == "gone"
