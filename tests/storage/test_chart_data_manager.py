"""Tests for ChartDataManager's load path running the per-item chart
migration dispatcher before constructing the Chart."""
import io
import json
from unittest.mock import patch
from zipfile import ZipFile

import numpy as np

from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import Chart
from pandaplot.storage.chart_data_manager import ChartDataManager


def _round_trip(chart: Chart, schema_version: int = 1) -> Chart:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as zf:
        ChartDataManager().save(chart, zf, "items/test-chart")

    buffer.seek(0)
    with ZipFile(buffer, "r") as zf:
        return ChartDataManager().load(Chart, zf, "items/test-chart", schema_version)


def test_round_trip_preserves_chart_type():
    chart = Chart(id="chart-1", name="My Chart", chart_type="scatter")

    loaded = _round_trip(chart)

    assert loaded.chart_type == "scatter"


def test_load_runs_migrate_chart_before_constructing():
    chart = Chart(id="chart-1", name="My Chart", chart_type="line")
    calls = []

    def spy_migrate_chart(raw, schema_version):
        calls.append(schema_version)
        return raw

    with patch("pandaplot.storage.chart_data_manager.migrate_chart", side_effect=spy_migrate_chart):
        _round_trip(chart, schema_version=0)

    assert calls == [0]


def test_a_genuinely_legacy_flat_shaped_chart_loads_through_both_migrations():
    """End-to-end proof the two-hop migration composes correctly for a
    genuinely old (schema_version=0) file: flat legacy series/fit fields
    (pre migrate_chart_legacy_to_v1) AND flat axis-prefixed config keys
    (pre migrate_chart_v1_to_v2) in the same raw dict, loaded via
    ChartDataManager.load() exactly as a real saved project would be."""
    raw = {
        "id": "chart-1",
        "name": "Legacy Chart",
        "chart_type": "line",
        "data_series": [{
            "dataset_id": "ds1", "x_column": "x", "y_column": "y",
            "color": "#112233",
        }],
        "fit_data": [],
        "config": {
            "title": "Legacy Chart",
            "show_legend": True,
            "x_label": "Time (s)",
            "x_min": -5.0,
            "x_max": 5.0,
            "show_grid_x": False,
            "y_scale": "log",
            "y_log_base": 2.0,
        },
        "style": {},
    }
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as zf:
        zf.writestr("items/test-chart.json", json.dumps(raw))

    buffer.seek(0)
    with ZipFile(buffer, "r") as zf:
        loaded = ChartDataManager().load(Chart, zf, "items/test-chart", schema_version=0)

    # migrate_chart_legacy_to_v1's effect: series got a nested style.
    assert loaded.data_series[0].style.color == "#112233"
    # migrate_chart_v1_to_v2's effect: axis-prefixed config keys are now
    # real typed AxisConfig attributes.
    assert loaded.config.title == "Legacy Chart"
    assert loaded.config.show_legend is True
    assert loaded.config.x.label == "Time (s)"
    assert loaded.config.x.min == -5.0
    assert loaded.config.x.max == 5.0
    assert loaded.config.x.show_grid is False
    assert loaded.config.y.scale == "log"
    assert loaded.config.y.log_base == 2.0
    # An axis key never present in the legacy file still gets its correct
    # per-axis default.
    assert loaded.config.y.side == "left"
    assert loaded.config.y2.side == "right"


def test_saving_a_fit_series_with_confidence_bands_round_trips_through_real_json():
    """Regression test for final-review Critical finding #1: a FIT
    series' confidence_lower/confidence_upper live inside FitStyle and go
    out through Chart.to_dict()'s generic `asdict(series.style)` path --
    without converting ndarray values there, json.dumps() (called
    directly by ChartDataManager.save) raises TypeError, and since
    ProjectDataManager.save() truncates the zip before writing, a real
    project save could destroy an already-saved file. This exercises the
    actual save() -> json.dumps() -> load() path, not just to_dict()."""
    chart = Chart(id="chart-1", name="Fit Chart", chart_type="line")
    chart.add_fit_series(
        source_dataset_id="ds1",
        x_data=np.array([1.0, 2.0, 3.0]),
        y_data=np.array([1.0, 4.0, 9.0]),
        label="My Fit",
        style=FitStyle(
            fit_type="linear",
            confidence_lower=np.array([0.5, 3.5, 8.5]),
            confidence_upper=np.array([1.5, 4.5, 9.5]),
        ),
    )

    loaded = _round_trip(chart)

    assert len(loaded.data_series) == 1
    fit = loaded.data_series[0]
    assert fit.series_type == SeriesType.FIT
    np.testing.assert_array_equal(fit.precomputed_x_data, [1.0, 2.0, 3.0])
    np.testing.assert_array_equal(fit.precomputed_y_data, [1.0, 4.0, 9.0])
    np.testing.assert_array_equal(fit.style.confidence_lower, [0.5, 3.5, 8.5])
    np.testing.assert_array_equal(fit.style.confidence_upper, [1.5, 4.5, 9.5])
