"""Tests for ChartDataManager's load path running the per-item chart
migration dispatcher before constructing the Chart."""
import io
import json
from unittest.mock import patch
from zipfile import ZipFile

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
