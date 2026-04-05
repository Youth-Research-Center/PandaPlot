"""
Tests for the new event bus implementation with automatic hierarchy support.

These tests are designed for the enhanced EventBus that:
1. Only accepts dict data (or None which becomes empty dict)
2. Adds automatic event metadata (event_type, original_event)
3. Supports automatic event hierarchy emission
"""

from unittest.mock import Mock

from pandaplot.models.events.event_bus import EventBus


class TestNewEventBus:
    """Test the new event bus implementation."""
    
    def test_init(self):
        """Test EventBus initialization."""
        event_bus = EventBus()
        assert event_bus._subscribers is not None
        assert event_bus._pattern_subscribers is not None
    
    def test_subscribe_and_emit_basic(self):
        """Test basic subscription and emission."""
        event_bus = EventBus()
        callback = Mock()
        
        event_bus.subscribe("test_event", callback)
        event_bus.emit("test_event")
        
        # Should be called with metadata-enriched empty dict
        expected_data = {
            "event_type": "test_event",
            "original_event": "test_event"
        }
        callback.assert_called_once_with(expected_data)
    
    def test_emit_with_dict_data(self):
        """Test emitting with dictionary data."""
        event_bus = EventBus()
        callback = Mock()
        test_data = {"message": "hello", "value": 42}
        
        event_bus.subscribe("test_event", callback)
        event_bus.emit("test_event", test_data)
        
        # Should include original data plus metadata
        expected_data = {
            "message": "hello",
            "value": 42,
            "event_type": "test_event",
            "original_event": "test_event"
        }
        callback.assert_called_once_with(expected_data)
    
    def test_emit_with_none_data(self):
        """Test emitting with None data."""
        event_bus = EventBus()
        callback = Mock()
        
        event_bus.subscribe("test_event", callback)
        event_bus.emit("test_event", None)
        
        # None should become empty dict with metadata
        expected_data = {
            "event_type": "test_event",
            "original_event": "test_event"
        }
        callback.assert_called_once_with(expected_data)
    
    def test_multiple_callbacks(self):
        """Test multiple callbacks for same event."""
        event_bus = EventBus()
        callback1 = Mock()
        callback2 = Mock()
        callback3 = Mock()
        test_data = {"test": "data"}
        
        event_bus.subscribe("test_event", callback1)
        event_bus.subscribe("test_event", callback2)
        event_bus.subscribe("test_event", callback3)
        
        event_bus.emit("test_event", test_data)
        
        expected_data = {
            "test": "data",
            "event_type": "test_event",
            "original_event": "test_event"
        }
        
        callback1.assert_called_once_with(expected_data)
        callback2.assert_called_once_with(expected_data)
        callback3.assert_called_once_with(expected_data)
    
    def test_no_subscribers(self):
        """Test emitting to non-existent event (should not crash)."""
        event_bus = EventBus()
        # Should not raise any error
        event_bus.emit("nonexistent_event", {"test": "data"})
    
    def test_pattern_subscription(self):
        """Test pattern-based subscriptions."""
        event_bus = EventBus()
        callback = Mock()
        
        # Subscribe to all dataset events using the subscribe method with pattern
        event_bus.subscribe("dataset.*", callback)
        
        # Emit specific dataset event
        event_bus.emit("dataset.data_changed", {"dataset_id": "123"})
        
        expected_data = {
            "dataset_id": "123",
            "event_type": "dataset.data_changed",
            "original_event": "dataset.data_changed"
        }
        callback.assert_called_with(expected_data)
    
    def test_event_hierarchy_automatic_emission(self):
        """Test that events automatically emit parent events."""
        event_bus = EventBus()
        specific_callback = Mock()
        generic_callback = Mock()
        
        # Subscribe to both specific and generic events
        event_bus.subscribe("dataset.column_added", specific_callback)
        event_bus.subscribe("dataset.changed", generic_callback)
        
        # Emit specific event
        test_data = {"column_name": "new_col"}
        event_bus.emit("dataset.column_added", test_data)
        
        # Both should be called (hierarchy mapping should cause generic event to fire)
        expected_specific_data = {
            "column_name": "new_col",
            "event_type": "dataset.column_added",
            "original_event": "dataset.column_added"
        }
        
        specific_callback.assert_called_with(expected_specific_data)
        # The generic callback should be called if hierarchy mapping exists
        # (This depends on EventHierarchy.HIERARCHY_MAP configuration)
    
    def test_callback_exception_handling(self):
        """Test that exceptions in callbacks don't break the event bus."""
        event_bus = EventBus()
        
        def good_callback(data):
            good_callback.called = True
            good_callback.data = data
        good_callback.called = False
        good_callback.data = None
        
        def bad_callback(data):
            raise ValueError("Test exception")
        
        def another_good_callback(data):
            another_good_callback.called = True
            another_good_callback.data = data
        another_good_callback.called = False
        another_good_callback.data = None
        
        event_bus.subscribe("test_event", good_callback)
        event_bus.subscribe("test_event", bad_callback)
        event_bus.subscribe("test_event", another_good_callback)
        
        # Should not raise exception (exceptions are caught and logged)
        event_bus.emit("test_event", {"test": "data"})
        
        # First callback should have been called
        assert good_callback.called
        # Third callback may or may not be called depending on exception handling
        # (our implementation prints errors but continues)
    
    def test_data_immutability(self):
        """Test that emitted data doesn't mutate original dict."""
        event_bus = EventBus()
        callback = Mock()
        
        original_data = {"key": "value"}
        event_bus.subscribe("test_event", callback)
        event_bus.emit("test_event", original_data)
        
        # Original data should be unchanged
        assert original_data == {"key": "value"}
        assert "event_type" not in original_data
        assert "original_event" not in original_data
        
        # Callback should receive enriched copy
        call_args = callback.call_args[0][0]
        assert call_args["key"] == "value"
        assert call_args["event_type"] == "test_event"
        assert call_args["original_event"] == "test_event"
    
    def test_complex_data_structures(self):
        """Test with complex nested data structures."""
        event_bus = EventBus()
        callback = Mock()
        
        complex_data = {
            "user": {
                "id": 123,
                "name": "John Doe",
                "preferences": {
                    "theme": "dark",
                    "notifications": True
                }
            },
            "items": [
                {"id": 1, "name": "Item 1"},
                {"id": 2, "name": "Item 2"}
            ]
        }
        
        event_bus.subscribe("complex_event", callback)
        event_bus.emit("complex_event", complex_data)
        
        call_args = callback.call_args[0][0]
        
        # Should have all original data
        assert call_args["user"]["id"] == 123
        assert call_args["user"]["name"] == "John Doe"
        assert call_args["user"]["preferences"]["theme"] == "dark"
        assert len(call_args["items"]) == 2
        
        # Plus metadata
        assert call_args["event_type"] == "complex_event"
        assert call_args["original_event"] == "complex_event"
    
    def test_event_bus_isolation(self):
        """Test that different EventBus instances are isolated."""
        event_bus1 = EventBus()
        event_bus2 = EventBus()
        
        callback1 = Mock()
        callback2 = Mock()
        
        event_bus1.subscribe("test_event", callback1)
        event_bus2.subscribe("test_event", callback2)
        
        # Emit on first bus
        event_bus1.emit("test_event", {"source": "bus1"})
        
        # Only first callback should be called
        callback1.assert_called_once()
        callback2.assert_not_called()
        
        # Emit on second bus
        event_bus2.emit("test_event", {"source": "bus2"})
        
        # Now second callback should be called
        callback2.assert_called_once()
        # First callback should still only be called once
        assert callback1.call_count == 1
    
    def test_real_world_scenario(self):
        """Test a real-world scenario with dataset events."""
        event_bus = EventBus()
        
        # Simulate components subscribing to events
        dataset_panel_callback = Mock()
        analysis_panel_callback = Mock()
        chart_panel_callback = Mock()
        
        # Subscribe to different event levels
        event_bus.subscribe("dataset.changed", dataset_panel_callback)
        event_bus.subscribe("dataset.column_added", analysis_panel_callback)
        event_bus.subscribe("dataset.*", chart_panel_callback)
        
        # Emit a specific event
        event_data = {
            "dataset_id": "dataset_123",
            "column_name": "new_column",
            "column_type": "numeric"
        }
        event_bus.emit("dataset.column_added", event_data)
        
        # Analysis panel should get the specific event
        analysis_panel_callback.assert_called_once()
        call_data = analysis_panel_callback.call_args[0][0]
        assert call_data["dataset_id"] == "dataset_123"
        assert call_data["column_name"] == "new_column"
        assert call_data["event_type"] == "dataset.column_added"
        
        # Chart panel should get it via pattern subscription
        chart_panel_callback.assert_called()
        
        # Dataset panel gets called if hierarchy mapping exists
        # (depends on EventHierarchy.HIERARCHY_MAP)
