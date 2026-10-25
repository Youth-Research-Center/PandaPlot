"""
Event data classes for used event types in PandaPlot.
Only event types that are actually used (subscribed/emitted) have data classes.
Unused event types are commented for future reference.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import TYPE_CHECKING, Any, Self, TypeVar, override

if TYPE_CHECKING:
    from pandaplot.models.project.items.chart import Chart

T = TypeVar("T", bound="EventData")

@dataclass(frozen=True)
class EventData:
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """
        Create an event instance from a dictionary.
        Only keys matching dataclass fields are used.
        """
        field_names = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in field_names}
        return cls(**filtered)

    def to_dict(self) -> dict[str, Any]:
        """
        Convert dataclass to dictionary.
        """
        return asdict(self)


@dataclass(frozen=True)
class NoteContentChangedData(EventData):
    # TODO(#219): we need project id ideally
    note_id: str
    old_content: str
    new_content: str

@dataclass(frozen=True)
class ChartCreatedData(EventData):
    # TODO(#219): we need project id ideally
    chart_id: str


@dataclass(frozen=True, kw_only=True)
class ChartUpdatedData(EventData):
    """Chart update metadata with an optional reference to the live model."""

    chart_id: str
    chart: Chart | None = None
    update_type: str | None = None

    @override
    def to_dict(self) -> dict[str, Any]:
        """Keep the original chart object and omit unused optional keys.

        EventData's asdict() would deep-copy a model reference, separating
        subscribers from the chart that was actually changed.
        """
        payload: dict[str, Any] = {"chart_id": self.chart_id}
        if self.chart is not None:
            payload["chart"] = self.chart
        if self.update_type is not None:
            payload["update_type"] = self.update_type
        return payload


@dataclass(frozen=True, kw_only=True)
class SeriesSelectedData(EventData):
    """Selection shared by chart properties and series-scoped panels.

    Both index keys address the real data_series position, including fits.
    The kind lets the Fit panel reject a fit as a source for another fit.
    """

    chart_id: str
    series_index: int
    kind: str

    @override
    def to_dict(self) -> dict[str, Any]:
        """Expose the same series position under both existing index keys."""
        return {
            "chart_id": self.chart_id,
            "series_index": self.series_index,
            "kind": self.kind,
            "index": self.series_index,
        }

@dataclass(frozen=True)
class TabOpenRequestedData(EventData):
    # TODO(#219): we need project id ideally
    item_id: str
    item_name: str

@dataclass(frozen=True)
class DatasetDataChangedData(EventData):
    dataset_id: str
    start_index: tuple[int, int]
    end_index: tuple[int, int]

@dataclass(frozen=True)
class DatasetColumnsAddedData(EventData):
    dataset_id: str
    column_positions: list[int]

@dataclass(frozen=True)
class DatasetColumnsRemovedData(EventData):
    dataset_id: str
    column_positions: list[int]

@dataclass(frozen=True)
class DatasetColumnRenamedData(EventData):
    dataset_id: str
    column_index: int
    old_name: str
    new_name: str

@dataclass(frozen=True)
class DatasetRowsAddedData(EventData):
    dataset_id: str
    row_positions: list[int]

@dataclass(frozen=True)
class DatasetRowsRemovedData(EventData):
    dataset_id: str
    row_positions: list[int]
