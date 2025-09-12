"""
Event data classes for used event types in PandaPlot.
Only event types that are actually used (subscribed/emitted) have data classes.
Unused event types are commented for future reference.
"""
from dataclasses import asdict, dataclass, fields
from typing import Any, List, Tuple, Type, TypeVar

T = TypeVar("T", bound="EventData")

@dataclass(frozen=True)
class EventData:
    @classmethod
    def from_dict(cls: Type[T], data: dict[str, Any]) -> T:
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
    # TODO: we need project id ideally
    note_id: str
    old_content: str
    new_content: str

@dataclass(frozen=True)
class ChartCreatedData(EventData):
    # TODO: we need project id ideally
    chart_id: str

@dataclass(frozen=True)
class TabOpenRequestedData(EventData):
    # TODO: we need project id ideally
    item_id: str
    item_name: str

@dataclass(frozen=True)
class DatasetDataChangedData(EventData):
    dataset_id: str
    start_index: Tuple[int, int]
    end_index: Tuple[int, int]

@dataclass(frozen=True)
class DatasetColumnsAddedData(EventData):
    dataset_id: str
    column_positions: List[int]

@dataclass(frozen=True)
class DatasetColumnsRemovedData(EventData):
    dataset_id: str
    column_positions: List[int]

@dataclass(frozen=True)
class DatasetRowsAddedData(EventData):
    dataset_id: str
    row_positions: List[int]

@dataclass(frozen=True)
class DatasetRowsRemovedData(EventData):
    dataset_id: str
    row_positions: List[int]