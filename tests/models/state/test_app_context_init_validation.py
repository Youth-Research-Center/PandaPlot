"""Tests for AppContext.__init__ rejecting None entries in managers."""
import pytest

from pandaplot.models.events import EventBus
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState


class _FakeManager:
    pass


def test_init_raises_value_error_when_a_manager_is_none():
    event_bus = EventBus()
    app_state = AppState(event_bus)

    with pytest.raises(ValueError, match=r"managers\[1\]"):
        AppContext(app_state=app_state, event_bus=event_bus, managers=[_FakeManager(), None])


def test_init_error_identifies_the_none_position():
    event_bus = EventBus()
    app_state = AppState(event_bus)

    with pytest.raises(ValueError, match=r"managers\[0\]"):
        AppContext(app_state=app_state, event_bus=event_bus, managers=[None, _FakeManager()])
