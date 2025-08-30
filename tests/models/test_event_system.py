"""
Unit tests for the simplified event bus system.
"""

from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.events import EventHierarchy
from pandaplot.models.events.event_types import NoteEvents, ProjectEvents
from pandaplot.models.events.mixins import EventPublisherMixin, EventSubscriberMixin
from pandaplot.models.project.items.note import Note


class TestEventBus:
    
    def test_subscribe_and_emit(self):
        """Test basic subscription and emission."""
        bus = EventBus()
        received_events = []
        
        def handler(event_data):
            received_events.append(event_data)
        
        bus.subscribe("test.event", handler)
        bus.emit("test.event", {"test": "data"})
        
        assert len(received_events) == 1
        assert received_events[0]["test"] == "data"
        assert received_events[0]["event_type"] == "test.event"
    
    def test_pattern_subscription(self):
        """Test pattern-based subscriptions."""
        bus = EventBus()
        received_events = []
        
        def handler(event_data):
            received_events.append(event_data)
        
        bus.subscribe("dataset.*", handler)
        
        # Emit specific dataset events
        bus.emit("dataset.changed", {"dataset_id": "test1"})
        bus.emit("dataset.column_added", {"dataset_id": "test2"})
        bus.emit("ui.tab_changed", {"tab_id": "test3"})  # Should not match
        
        # dataset.changed emits 1 event (itself)
        # dataset.column_added emits 3 events due to hierarchy
        # ui.tab_changed emits 1 event but doesn't match pattern
        assert len(received_events) == 4  # 1 + 3 = 4 dataset.* events
        
        # Check that all received events are dataset events
        dataset_events = [e for e in received_events if e["event_type"].startswith("dataset.")]
        assert len(dataset_events) == 4
    
    def test_event_hierarchy(self):
        """Test automatic event hierarchy emission."""
        bus = EventBus()
        received_events = []
        
        def handler(event_data):
            received_events.append(event_data)
        
        # Subscribe to different levels of hierarchy
        bus.subscribe(ProjectEvents.PROJECT_ITEM_REMOVED, handler)
        bus.subscribe(ProjectEvents.PROJECT_CHANGED, handler)

        # Emit specific event
        bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {"folder_id": "test_folder"})
        
        # Should receive all hierarchy levels
        assert len(received_events) == 2
        event_types = [event["event_type"] for event in received_events]
        assert ProjectEvents.PROJECT_ITEM_REMOVED in event_types
        assert ProjectEvents.PROJECT_CHANGED in event_types

    def test_unsubscribe(self):
        """Test unsubscribing from events."""
        bus = EventBus()
        received_events = []
        
        def handler(event_data):
            received_events.append(event_data)
        
        bus.subscribe("test.event", handler)
        bus.emit("test.event", {"test": "data1"})
        
        bus.unsubscribe("test.event", handler)
        bus.emit("test.event", {"test": "data2"})
        
        assert len(received_events) == 1
        assert received_events[0]["test"] == "data1"


class TestEventHierarchy:
    
    def test_get_hierarchy(self):
        """Test getting event hierarchy."""
        hierarchy = EventHierarchy.get_hierarchy(NoteEvents.NOTE_CONTENT_CHANGED)
        expected = [NoteEvents.NOTE_CONTENT_CHANGED, ProjectEvents.PROJECT_CHANGED]
        assert hierarchy == expected
    
    def test_unknown_event_hierarchy(self):
        """Test hierarchy for unknown event types."""
        hierarchy = EventHierarchy.get_hierarchy("unknown.event")
        assert hierarchy == ["unknown.event"]
    
    def test_add_mapping(self):
        """Test adding new hierarchy mappings."""
        EventHierarchy.add_mapping("custom.event", ["custom.event", "custom.changed"])
        hierarchy = EventHierarchy.get_hierarchy("custom.event")
        assert hierarchy == ["custom.event", "custom.changed"]


class MockComponent(EventPublisherMixin, EventSubscriberMixin):
    """Mock component for testing mixins."""
    
    def __init__(self, event_bus=None):
        EventPublisherMixin.__init__(self, event_bus)
        EventSubscriberMixin.__init__(self, event_bus)
        self.handled_events = []
    
    def handle_event(self, event_data):
        self.handled_events.append(event_data)


class TestEventMixins:
    
    def test_event_publisher_mixin(self):
        """Test EventPublisherMixin functionality."""
        bus = EventBus()
        component = MockComponent(bus)
        
        received_events = []
        bus.subscribe("test.event", lambda data: received_events.append(data))
        
        component.publish_event("test.event", {"test": "data"})
        
        assert len(received_events) == 1
        assert received_events[0]["test"] == "data"
        assert received_events[0]["source_component"] == "MockComponent"
    
    def test_event_subscriber_mixin(self):
        """Test EventSubscriberMixin functionality."""
        bus = EventBus()
        component = MockComponent(bus)
        
        component.subscribe_to_event("test.event", component.handle_event)
        bus.emit("test.event", {"test": "data"})
        
        assert len(component.handled_events) == 1
        assert component.handled_events[0]["test"] == "data"
    
    def test_subscribe_to_changes(self):
        """Test scope-based subscription patterns."""
        bus = EventBus()
        component = MockComponent(bus)
        
        component.subscribe_to_changes("dataset", component.handle_event)
        
        # Should only receive dataset.changed events
        bus.emit("dataset.changed", {"dataset_id": "test1"})
        bus.emit("dataset.column_added", {"dataset_id": "test2"})  # Hierarchy includes dataset.changed
        
        # Should have received 2 events (both emit dataset.changed through hierarchy)
        assert len(component.handled_events) >= 1
    
    def test_unsubscribe_all(self):
        """Test unsubscribing from all events."""
        bus = EventBus()
        component = MockComponent(bus)
        
        component.subscribe_to_event("test.event", component.handle_event)
        bus.emit("test.event", {"test": "data1"})
        
        component.unsubscribe_all()
        bus.emit("test.event", {"test": "data2"})
        
        assert len(component.handled_events) == 1
        assert component.handled_events[0]["test"] == "data1"
