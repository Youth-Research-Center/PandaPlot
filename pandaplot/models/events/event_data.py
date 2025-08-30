"""
Event data classes for used event types in PandaPlot.
Only event types that are actually used (subscribed/emitted) have data classes.
Unused event types are commented for future reference.
"""
from dataclasses import dataclass, asdict, fields
from typing import Any, Type, TypeVar

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
class ProjectChangedData(EventData):
    project_id: str


@dataclass(frozen=True)
class NoteContentChangedData(EventData):
    note_id: str
    old_content: str
    new_content: str