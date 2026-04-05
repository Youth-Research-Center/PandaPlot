"""
Event system for pandaplot application.

This module provides a simplified event bus architecture for decoupling components.
"""

from .event_bus import EventBus
from .event_types import (
    AnalysisEvents,
    AppEvents,
    ChartEvents,
    DatasetEvents,
    DatasetOperationEvents,
    EventHierarchy,
    FitEvents,
    NoteEvents,
    ProjectEvents,
    UIEvents,
)

__all__ = [
    "AppEvents",
    "EventBus",
    "DatasetEvents",
    "DatasetOperationEvents", 
    "AnalysisEvents",
    "ChartEvents",
    "UIEvents",
    "ProjectEvents",
    "NoteEvents",
    "EventHierarchy",
    "FitEvents"
]