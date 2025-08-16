from unittest.mock import Mock, call

from pandaplot.models.events.event_bus import EventBus


class TestEventBus:
    """Test suite for the EventBus class."""

    def test_init(self):
        """Test EventBus initialization."""
        event_bus = EventBus()

        assert hasattr(event_bus, '_subscribers')
        assert len(event_bus._subscribers) == 0

    def test_subscribe_single_callback(self):
        """Test subscribing a single callback to an event."""
        event_bus = EventBus()
        callback = Mock()

        event_bus.subscribe("test_event", callback)

        assert "test_event" in event_bus._subscribers
        assert callback in event_bus._subscribers["test_event"]
        assert len(event_bus._subscribers["test_event"]) == 1

    def test_subscribe_multiple_callbacks_same_event(self):
        """Test subscribing multiple callbacks to the same event."""
        event_bus = EventBus()
        callback1 = Mock()
        callback2 = Mock()
        callback3 = Mock()

        event_bus.subscribe("test_event", callback1)
        event_bus.subscribe("test_event", callback2)
        event_bus.subscribe("test_event", callback3)

        assert len(event_bus._subscribers["test_event"]) == 3
        assert callback1 in event_bus._subscribers["test_event"]
        assert callback2 in event_bus._subscribers["test_event"]
        assert callback3 in event_bus._subscribers["test_event"]

    def test_subscribe_same_callback_multiple_times(self):
        """Test subscribing the same callback multiple times to the same event."""
        event_bus = EventBus()
        callback = Mock()

        event_bus.subscribe("test_event", callback)
        event_bus.subscribe("test_event", callback)
        event_bus.subscribe("test_event", callback)

        # Should have the callback multiple times (by design)
        assert len(event_bus._subscribers["test_event"]) == 3
        assert all(
            cb == callback for cb in event_bus._subscribers["test_event"])

    def test_subscribe_different_events(self):
        """Test subscribing callbacks to different events."""
        event_bus = EventBus()
        callback1 = Mock()
        callback2 = Mock()
        callback3 = Mock()

        event_bus.subscribe("event1", callback1)
        event_bus.subscribe("event2", callback2)
        event_bus.subscribe("event3", callback3)

        assert len(event_bus._subscribers) == 3
        assert "event1" in event_bus._subscribers
        assert "event2" in event_bus._subscribers
        assert "event3" in event_bus._subscribers

        assert callback1 in event_bus._subscribers["event1"]
        assert callback2 in event_bus._subscribers["event2"]
        assert callback3 in event_bus._subscribers["event3"]

    def test_subscribe_callback_to_multiple_events(self):
        """Test subscribing the same callback to multiple events."""
        event_bus = EventBus()
        callback = Mock()

        event_bus.subscribe("event1", callback)
        event_bus.subscribe("event2", callback)
        event_bus.subscribe("event3", callback)

        assert len(event_bus._subscribers) == 3
        assert callback in event_bus._subscribers["event1"]
        assert callback in event_bus._subscribers["event2"]
        assert callback in event_bus._subscribers["event3"]

    def test_emit_no_data(self):
        """Test emitting an event without data."""
        event_bus = EventBus()
        callback = Mock()

        event_bus.subscribe("test_event", callback)
        event_bus.emit("test_event")

        # EventBus converts None to {} and adds metadata
        expected_data = {
            'event_type': 'test_event',
            'original_event': 'test_event'
        }
        callback.assert_called_once_with(expected_data)

    def test_emit_with_data(self):
        """Test emitting an event with data."""
        event_bus = EventBus()
        callback = Mock()
        test_data = {"key": "value", "number": 42}

        event_bus.subscribe("test_event", callback)
        event_bus.emit("test_event", test_data)

        # EventBus adds metadata to the data
        expected_data = {
            "key": "value",
            "number": 42,
            'event_type': 'test_event',
            'original_event': 'test_event'
        }
        callback.assert_called_once_with(expected_data)

    def test_emit_with_none_data(self):
        """Test emitting an event with explicit None data."""
        event_bus = EventBus()
        callback = Mock()

        event_bus.subscribe("test_event", callback)
        event_bus.emit("test_event", None)

        # EventBus treats None as empty dict and adds metadata
        expected_data = {
            'event_type': 'test_event',
            'original_event': 'test_event'
        }
        callback.assert_called_once_with(expected_data)

    def test_emit_with_various_data_types(self):
        """Test emitting events with different data types."""
        event_bus = EventBus()
        callback = Mock()

        # New API only accepts dict data, so we wrap values in dicts
        test_cases = [
            ("string", {"value": "hello world"}),
            ("int", {"value": 123}),
            ("float", {"value": 3.14}),
            ("list", {"value": [1, 2, 3]}),
            ("dict", {"a": 1, "b": 2}),
            ("bool", {"value": True}),
            ("tuple", {"value": (1, 2, 3)}),
        ]

        event_bus.subscribe("test_event", callback)

        for event_name, data in test_cases:
            callback.reset_mock()
            event_bus.emit("test_event", data)

            # Expected data includes the original data plus metadata
            expected_data = data.copy()
            expected_data.update({
                'event_type': 'test_event',
                'original_event': 'test_event'
            })
            callback.assert_called_once_with(expected_data)

    def test_emit_to_multiple_callbacks(self):
        """Test emitting an event to multiple callbacks."""
        event_bus = EventBus()
        callback1 = Mock()
        callback2 = Mock()
        callback3 = Mock()
        test_data = {"message": {"data": "test_data"}}

        event_bus.subscribe("test_event", callback1)
        event_bus.subscribe("test_event", callback2)
        event_bus.subscribe("test_event", callback3)

        event_bus.emit("test_event", test_data)

        # Expected data includes metadata
        expected_data = {
            "message": {"data": "test_data"},
            'event_type': 'test_event',
            'original_event': 'test_event'
        }
        callback1.assert_called_once_with(expected_data)
        callback2.assert_called_once_with(expected_data)
        callback3.assert_called_once_with(expected_data)

    def test_emit_nonexistent_event(self):
        """Test emitting an event with no subscribers."""
        event_bus = EventBus()

        # Should not raise any error
        event_bus.emit("nonexistent_event", {"data": "test"})

    def test_emit_multiple_events(self):
        """Test emitting multiple different events."""
        event_bus = EventBus()
        callback1 = Mock()
        callback2 = Mock()
        callback3 = Mock()

        event_bus.subscribe("event1", callback1)
        event_bus.subscribe("event2", callback2)
        event_bus.subscribe("event3", callback3)

        event_bus.emit("event1", {"data": "data1"})
        event_bus.emit("event2", {"data": "data2"})
        event_bus.emit("event3", {"data": "data3"})

        # Expect calls with metadata added by EventBus
        expected_call1 = {"data": "data1",
                          "event_type": "event1", "original_event": "event1"}
        expected_call2 = {"data": "data2",
                          "event_type": "event2", "original_event": "event2"}
        expected_call3 = {"data": "data3",
                          "event_type": "event3", "original_event": "event3"}

        callback1.assert_called_once_with(expected_call1)
        callback2.assert_called_once_with(expected_call2)
        callback3.assert_called_once_with(expected_call3)

    def test_emit_same_event_multiple_times(self):
        """Test emitting the same event multiple times."""
        event_bus = EventBus()
        callback = Mock()

        event_bus.subscribe("test_event", callback)

        event_bus.emit("test_event", {"data": "data1"})
        event_bus.emit("test_event", {"data": "data2"})
        event_bus.emit("test_event", {"data": "data3"})

        # Expect calls with metadata added by EventBus
        expected_calls = [
            call({"data": "data1", "event_type": "test_event",
                 "original_event": "test_event"}),
            call({"data": "data2", "event_type": "test_event",
                 "original_event": "test_event"}),
            call({"data": "data3", "event_type": "test_event",
                 "original_event": "test_event"})
        ]
        callback.assert_has_calls(expected_calls)
        assert callback.call_count == 3

    def test_callback_exception_handling(self):
        """Test that exceptions in callbacks don't affect other callbacks."""
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

        # The EventBus catches exceptions and prints them, doesn't re-raise
        event_bus.emit("test_event", {"data": "test_data"})

        # The first callback should have been called
        expected_data = {"data": "test_data",
                         "event_type": "test_event", "original_event": "test_event"}
        assert good_callback.called is True
        assert good_callback.data == expected_data

        # The third callback should also be called since exceptions are caught
        assert another_good_callback.called is True
        assert another_good_callback.data == expected_data

    def test_callback_execution_order(self):
        """Test callback execution order (note: order is not guaranteed with defaultdict(list))."""
        event_bus = EventBus()
        execution_order = []

        def callback1(data):
            execution_order.append("callback1")

        def callback2(data):
            execution_order.append("callback2")

        def callback3(data):
            execution_order.append("callback3")

        event_bus.subscribe("test_event", callback1)
        event_bus.subscribe("test_event", callback2)
        event_bus.subscribe("test_event", callback3)

        event_bus.emit("test_event", {"data": "test"})

        # All callbacks should be executed
        assert len(execution_order) == 3
        assert "callback1" in execution_order
        assert "callback2" in execution_order
        assert "callback3" in execution_order

        # Order should be preserved since we're using a list
        assert execution_order == ["callback1", "callback2", "callback3"]

    def test_lambda_callbacks(self):
        """Test subscribing lambda functions as callbacks."""
        event_bus = EventBus()
        results = []

        # Subscribe lambda callbacks
        event_bus.subscribe(
            "test_event", lambda data: results.append(f"lambda1: {data}"))
        event_bus.subscribe(
            "test_event", lambda data: results.append(f"lambda2: {data}"))

        event_bus.emit("test_event", {"data": "test_data"})

        assert len(results) == 2
        # EventBus adds metadata to the data, so the lambda receives the full dict
        expected_data_repr = "{'data': 'test_data', 'event_type': 'test_event', 'original_event': 'test_event'}"
        assert f"lambda1: {expected_data_repr}" in results
        assert f"lambda2: {expected_data_repr}" in results

    def test_method_callbacks(self):
        """Test subscribing class methods as callbacks."""
        event_bus = EventBus()

        class TestSubscriber:
            def __init__(self):
                self.received_data = []

            def handle_event(self, data):
                self.received_data.append(data)

        subscriber1 = TestSubscriber()
        subscriber2 = TestSubscriber()

        event_bus.subscribe("test_event", subscriber1.handle_event)
        event_bus.subscribe("test_event", subscriber2.handle_event)

        event_bus.emit("test_event", {"data": "test_data"})

        expected_data = {"data": "test_data",
                         "event_type": "test_event", "original_event": "test_event"}
        assert len(subscriber1.received_data) == 1
        assert len(subscriber2.received_data) == 1
        assert subscriber1.received_data[0] == expected_data
        assert subscriber2.received_data[0] == expected_data

    def test_mixed_callback_types(self):
        """Test mixing different types of callbacks."""
        event_bus = EventBus()
        results = []

        # Function callback
        def function_callback(data):
            results.append(f"function: {data}")

        # Lambda callback
        def lambda_callback(data):
            results.append(f"lambda: {data}")

        # Method callback
        class TestClass:
            def method_callback(self, data):
                results.append(f"method: {data}")

        test_instance = TestClass()

        event_bus.subscribe("test_event", function_callback)
        event_bus.subscribe("test_event", lambda_callback)
        event_bus.subscribe("test_event", test_instance.method_callback)

        event_bus.emit("test_event", {"data": "test_data"})

        expected_data_repr = "{'data': 'test_data', 'event_type': 'test_event', 'original_event': 'test_event'}"
        assert len(results) == 3
        assert f"function: {expected_data_repr}" in results
        assert f"lambda: {expected_data_repr}" in results
        assert f"method: {expected_data_repr}" in results

    def test_complex_data_structures(self):
        """Test emitting events with complex data structures."""
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
                {"id": 1, "name": "Item 1", "tags": ["tag1", "tag2"]},
                {"id": 2, "name": "Item 2", "tags": ["tag3"]},
            ],
            "metadata": {
                "timestamp": "2025-01-01T00:00:00Z",
                "version": "1.0.0"
            }
        }

        event_bus.subscribe("complex_event", callback)
        event_bus.emit("complex_event", complex_data)

        # EventBus adds metadata to the data
        expected_data = complex_data.copy()
        expected_data.update(
            {"event_type": "complex_event", "original_event": "complex_event"})
        callback.assert_called_once_with(expected_data)

        # Verify the data structure is preserved
        call_args = callback.call_args[0][0]
        assert call_args["user"]["id"] == 123
        assert call_args["user"]["name"] == "John Doe"
        assert call_args["user"]["preferences"]["theme"] == "dark"
        assert len(call_args["items"]) == 2
        assert call_args["items"][0]["tags"] == ["tag1", "tag2"]

    def test_event_bus_isolation(self):
        """Test that different EventBus instances are isolated."""
        event_bus1 = EventBus()
        event_bus2 = EventBus()

        callback1 = Mock()
        callback2 = Mock()

        event_bus1.subscribe("test_event", callback1)
        event_bus2.subscribe("test_event", callback2)

        # Emit on first bus
        event_bus1.emit("test_event", {"data": "test_data"})

        expected_data = {"data": "test_data",
                         "event_type": "test_event", "original_event": "test_event"}
        callback1.assert_called_once_with(expected_data)
        callback2.assert_not_called()

        # Reset and emit on second bus
        callback1.reset_mock()
        event_bus2.emit("test_event", {"data": "test_data"})

        callback1.assert_not_called()
        callback2.assert_called_once_with(expected_data)

    def test_defaultdict_behavior(self):
        """Test that _subscribers uses defaultdict correctly."""
        event_bus = EventBus()

        # Accessing non-existent key should create empty list
        subscribers = event_bus._subscribers["nonexistent_event"]
        assert isinstance(subscribers, list)
        assert len(subscribers) == 0

        # Should now exist in the dict
        assert "nonexistent_event" in event_bus._subscribers

    def test_stress_test_many_callbacks(self):
        """Test with many callbacks subscribed to the same event."""
        event_bus = EventBus()
        callbacks = []

        # Create 100 mock callbacks
        for i in range(100):
            callback = Mock()
            callbacks.append(callback)
            event_bus.subscribe("stress_test", callback)

        test_data = {"data": "test_data"}
        event_bus.emit("stress_test", test_data)

        # All callbacks should have been called with metadata added
        expected_data = {"data": "test_data",
                         "event_type": "stress_test", "original_event": "stress_test"}
        for callback in callbacks:
            callback.assert_called_once_with(expected_data)

    def test_stress_test_many_events(self):
        """Test with many different events."""
        event_bus = EventBus()
        callbacks = {}

        # Create 100 different events with callbacks
        for i in range(100):
            event_name = f"event_{i}"
            callback = Mock()
            callbacks[event_name] = callback
            event_bus.subscribe(event_name, callback)

        # Emit all events
        for i in range(100):
            event_name = f"event_{i}"
            event_bus.emit(event_name, {"data": f"data_{i}"})

        # Verify all callbacks were called with correct data
        for i in range(100):
            event_name = f"event_{i}"
            expected_data = {"data": f"data_{i}",
                             "event_type": event_name, "original_event": event_name}
            callbacks[event_name].assert_called_once_with(expected_data)

    def test_event_names_are_strings(self):
        """Test various event name formats."""
        event_bus = EventBus()
        callback = Mock()

        event_names = [
            "simple_event",
            "CamelCaseEvent",
            "kebab-case-event",
            "dot.separated.event",
            "event_with_123_numbers",
            "event/with/slashes",
            "UPPERCASE_EVENT",
            "",  # Empty string
            "🎉emoji_event",
        ]

        for event_name in event_names:
            callback.reset_mock()
            event_bus.subscribe(event_name, callback)
            event_bus.emit(event_name, {"data": f"data_for_{event_name}"})
            expected_data = {"data": f"data_for_{event_name}",
                             "event_type": event_name, "original_event": event_name}
            callback.assert_called_once_with(expected_data)

    def test_real_world_usage_scenario(self):
        """Test a realistic usage scenario."""
        event_bus = EventBus()

        # Simulate different components subscribing to events
        ui_updates = []
        log_entries = []
        metrics = {"events_processed": 0}

        def ui_handler(data):
            ui_updates.append(f"UI: {data['message']}")

        def logger_handler(data):
            log_entries.append(f"LOG: {data['level']} - {data['message']}")

        def metrics_handler(data):
            metrics["events_processed"] += 1

        # Subscribe handlers to different events
        event_bus.subscribe("user_action", ui_handler)
        event_bus.subscribe("user_action", logger_handler)
        event_bus.subscribe("user_action", metrics_handler)

        event_bus.subscribe("system_error", logger_handler)
        event_bus.subscribe("system_error", metrics_handler)

        # Emit events
        event_bus.emit("user_action", {
            "message": "User clicked button",
            "level": "INFO"
        })

        event_bus.emit("system_error", {
            "message": "Database connection failed",
            "level": "ERROR"
        })

        event_bus.emit("user_action", {
            "message": "User logged out",
            "level": "INFO"
        })

        # Verify results
        assert len(ui_updates) == 2
        assert "UI: User clicked button" in ui_updates
        assert "UI: User logged out" in ui_updates

        assert len(log_entries) == 3
        assert "LOG: INFO - User clicked button" in log_entries
        assert "LOG: ERROR - Database connection failed" in log_entries
        assert "LOG: INFO - User logged out" in log_entries

        assert metrics["events_processed"] == 3
