"""Typed chart events preserve the payloads used by existing subscribers."""

from typing import Any

import pytest

from pandaplot.models.events import ChartEvents, EventBus
from pandaplot.models.events.event_data import ChartUpdatedData, SeriesSelectedData
from pandaplot.models.project.items.chart import Chart


@pytest.mark.parametrize("payload_shape", ["id_only", "model", "update_type", "model_and_type"])
def test_chart_update_round_trip_preserves_optional_keys_and_model_identity(payload_shape: str) -> None:
    chart = Chart(id="chart-1")
    payload: dict[str, Any] = {"chart_id": "chart-1"}
    if payload_shape in ("model", "model_and_type"):
        payload["chart"] = chart
    if payload_shape in ("update_type", "model_and_type"):
        payload["update_type"] = "series_added"

    restored = ChartUpdatedData.from_dict(payload).to_dict()

    assert restored == payload
    if "chart" in payload:
        assert restored["chart"] is chart
        chart.name = "Renamed after dispatch"
        assert restored["chart"].name == "Renamed after dispatch"


@pytest.mark.parametrize("kind", ["series", "fit"])
def test_selection_round_trip_keeps_both_sidebar_index_keys(kind: str) -> None:
    payload = {"chart_id": "chart-1", "series_index": 3, "kind": kind, "index": 3}

    event = SeriesSelectedData.from_dict(payload)

    assert event.to_dict() == payload
    assert SeriesSelectedData(chart_id="chart-1", series_index=3, kind=kind).to_dict() == payload


def test_chart_model_reference_reaches_real_event_bus_subscribers() -> None:
    bus = EventBus()
    chart = Chart(id="chart-1")
    received: list[dict[str, Any]] = []
    bus.subscribe(ChartEvents.CHART_UPDATED, received.append)

    bus.emit(ChartEvents.CHART_UPDATED, ChartUpdatedData(chart_id=chart.id, chart=chart).to_dict())

    assert len(received) == 1
    assert received[0] == {
        "chart_id": "chart-1",
        "chart": chart,
        "event_type": "chart.updated",
        "original_event": "chart.updated",
    }
    assert received[0]["chart"] is chart
