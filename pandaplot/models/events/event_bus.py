from collections import defaultdict
import logging
import re
from typing import Callable, Dict, Any
from .event_types import EventHierarchy


class EventBus:
    """
    Event bus for communication between components.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._subscribers = defaultdict(list)
        self._pattern_subscribers = defaultdict(list)
        self.logger.debug("EventBus initialized")

    def subscribe(self, event_pattern: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Subscribe to events matching a pattern.
        
        Args:
            event_pattern: Event name or pattern (e.g., "dataset.changed" or "dataset.*")
            callback: Function to call when event matches
        """
        self.logger.debug("Subscribing to event pattern: %s", event_pattern)
        
        if '*' in event_pattern:
            # Convert glob pattern to regex
            regex_pattern = event_pattern.replace('.', r'\.').replace('*', '.*')
            self._pattern_subscribers[regex_pattern].append(callback)
            self.logger.debug("Added pattern subscriber for: %s (regex: %s)", event_pattern, regex_pattern)
        else:
            self._subscribers[event_pattern].append(callback)
            self.logger.debug("Added direct subscriber for: %s", event_pattern)

    def unsubscribe(self, event_pattern: str, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Remove a subscription.
        
        Args:
            event_pattern: The same pattern used in subscribe
            callback: The same callback function used in subscribe
        """
        self.logger.debug("Unsubscribing from event pattern: %s", event_pattern)
        
        if '*' in event_pattern:
            regex_pattern = event_pattern.replace('.', r'\.').replace('*', '.*')
            if callback in self._pattern_subscribers[regex_pattern]:
                self._pattern_subscribers[regex_pattern].remove(callback)
                self.logger.debug("Removed pattern subscriber for: %s", event_pattern)
            else:
                self.logger.warning("Callback not found in pattern subscribers for: %s", event_pattern)
        else:
            if callback in self._subscribers[event_pattern]:
                self._subscribers[event_pattern].remove(callback)
                self.logger.debug("Removed direct subscriber for: %s", event_pattern)
            else:
                self.logger.warning("Callback not found in direct subscribers for: %s", event_pattern)

    def emit(self, event_type: str, data: Dict[str, Any] | None = None) -> None:
        """Emit an event with automatic hierarchy support.
        
        Args:
            event_type: The most specific event type
            data: Event data dictionary
            
        This automatically emits parent events in the hierarchy based on EventHierarchy mapping.
        """
        if data is None:
            data = {}
        
        self.logger.debug("Emitting event: %s with data keys: %s", event_type, list(data.keys()))
        
        # Get hierarchy for this event type
        hierarchy = EventHierarchy.get_hierarchy(event_type)
        
        total_callbacks_called = 0
        
        # Emit events from specific to generic
        for event_level in hierarchy:
            event_data = data.copy()
            event_data['event_type'] = event_level
            event_data['original_event'] = event_type
            
            # Emit to exact subscribers
            subscriber_count = len(self._subscribers[event_level])
            for callback in self._subscribers[event_level]:
                try:
                    callback(event_data)
                    total_callbacks_called += 1
                except Exception as e:
                    self.logger.error("Error in event callback for '%s': %s", event_level, str(e), exc_info=True)
            
            # Emit to pattern subscribers
            pattern_matches = 0
            for pattern, callbacks in self._pattern_subscribers.items():
                if re.match(pattern, event_level):
                    pattern_matches += len(callbacks)
                    for callback in callbacks:
                        try:
                            callback(event_data)
                            total_callbacks_called += 1
                        except Exception as e:
                            self.logger.error("Error in pattern callback for '%s' (pattern: %s): %s", 
                                            event_level, pattern, str(e), exc_info=True)
            
            if subscriber_count > 0 or pattern_matches > 0:
                self.logger.debug("Emitted event '%s' to %d direct subscribers and %d pattern matches", 
                                event_level, subscriber_count, pattern_matches)
        
        if total_callbacks_called == 0:
            self.logger.debug("Event '%s' emitted but no subscribers found", event_type)
        else:
            self.logger.debug("Event '%s' completed: %d total callbacks executed", event_type, total_callbacks_called)

    def clear_all_subscriptions(self) -> None:
        """Clear all subscriptions - useful for testing."""
        self._subscribers.clear()
        self._pattern_subscribers.clear()
