"""
Event data classes for used event types in PandaPlot.
Only event types that are actually used (subscribed/emitted) have data classes.
Unused event types are commented for future reference.
"""
from dataclasses import asdict, dataclass, fields
from typing import Any, Self, TypeVar

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
