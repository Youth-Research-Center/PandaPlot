"""
Event mixins for components that publish or subscribe to events.
These mixins provide standardized event handling patterns.

Usage patterns:
- EventPublisherMixin: for components that emit events
- EventSubscriberMixin: for components that listen to events
- Use both mixins for components that both publish and subscribe

Always call set_event_bus() in component __init__ to connect to the event bus.
"""

from typing import Callable, Dict, Any, List, Tuple
from .event_bus import EventBus


class EventPublisherMixin:
    """Mixin for components that publish events.
    
    Provides standardized event publishing with automatic source tracking.
    Use this mixin for any component that needs to emit events.
    
    Example usage:
        class MyComponent(QWidget, EventPublisherMixin):
            def __init__(self, app_context):
                EventPublisherMixin.__init__(self, app_context.event_bus)
                QWidget.__init__(self)
    """
    
    def __init__(self, event_bus: 'EventBus'):
        self._event_bus: EventBus | None = event_bus
    
    def publish_event(self, event_type: str, data: Dict[str, Any] | None = None) -> None:
        """Publish an event through the event bus with automatic hierarchy.
        
        Args:
            event_type: The most specific event type (e.g., "folder.created")
            data: Optional data to include with the event
            
        This automatically publishes the event hierarchy based on EventHierarchy mapping.
        For example, "folder.created" automatically publishes:
        - folder.created → project.item_added → project.changed
        
        Example:
            self.publish_event("folder.created", {
                'folder_id': folder_data.id,
                'folder_name': folder_data.name
            })
            # Automatically publishes all hierarchy levels
        """
        if self._event_bus:
            event_data = data or {}
            event_data['source_component'] = self.__class__.__name__
            self._event_bus.emit(event_type, event_data)


class EventSubscriberMixin:
    """Mixin for components that subscribe to events.
    
    Provides standardized event subscription with automatic cleanup.
    Use this mixin for any component that needs to listen to events.
    
    Example usage:
        class MyComponent(QWidget, EventSubscriberMixin):
            def __init__(self, app_context):
                EventSubscriberMixin.__init__(self, app_context.event_bus)
                QWidget.__init__(self)
                self.setup_event_subscriptions()
                
            def on_dataset_changed(self, event_data):
                # Handle the event
                pass
    """
    
    def __init__(self, event_bus: 'EventBus'):
        self._event_bus: EventBus | None = event_bus
        self._subscriptions: List[Tuple[str, Callable]] = []
    
    def subscribe_to_event(self, event_type: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Subscribe to an event type.
        
        Args:
            event_type: The type of event to subscribe to (use constants from event_types.py)
            handler: Function to call when event is received (receives event data dict)
            
        Example:
            self.subscribe_to_event(DatasetEvents.DATASET_CHANGED, self.on_dataset_changed)
            
            def on_dataset_changed(self, event_data):
                dataset_id = event_data.get('dataset_id')
                # Handle the dataset change
        """
        if self._event_bus:
            self._event_bus.subscribe(event_type, handler)
            self._subscriptions.append((event_type, handler))
    
    def subscribe_to_multiple_events(self, event_subscriptions: List[Tuple[str, Callable]]) -> None:
        """Subscribe to multiple events at once.
        
        Args:
            event_subscriptions: List of (event_type, handler) tuples
            
        Example:
            self.subscribe_to_multiple_events([
                ("dataset.changed", self.on_dataset_changed),
                ("ui.tab_changed", self.on_tab_changed)
            ])
        """
        for event_type, handler in event_subscriptions:
            self.subscribe_to_event(event_type, handler)
    
    def subscribe_to_changes(self, scope: str, handler: Callable) -> None:
        """Subscribe to changes at the appropriate scope level.
        
        Args:
            scope: "dataset", "dataset_operations", "project", "project_items", "ui", "analysis"
            handler: Function to call when events match
            
        This automatically subscribes to the right granularity level:
        - "dataset": subscribes to "dataset.changed" (generic dataset changes)
        - "dataset_operations": subscribes to "dataset.*" (all dataset operations)
        - "project": subscribes to "project.changed" (generic project changes)
        - "project_items": subscribes to "project.item_*" (project item operations)
        """
        scope_patterns = {
            "dataset": "dataset.changed",  # Generic dataset changes only
            "dataset_operations": "dataset.*",  # All dataset operations
            "project": "project.changed",  # Generic project changes only
            "project_items": "project.item_*",  # Project item operations
            "ui": "ui.*",  # All UI events
            "analysis": "analysis.*",  # All analysis events
        }
        
        pattern = scope_patterns.get(scope, scope)
        self.subscribe_to_event(pattern, handler)
    
    def unsubscribe_all(self) -> None:
        """Unsubscribe from all events.
        
        This should be called in component cleanup/destruction to prevent memory leaks.
        """
        if self._event_bus:
            for event_type, handler in self._subscriptions:
                self._event_bus.unsubscribe(event_type, handler)
            self._subscriptions.clear()
    
    def __del__(self):
        """Cleanup subscriptions when component is destroyed."""
        self.unsubscribe_all()


class EventBusComponentMixin:
    """Combined mixin for components that both publish and subscribe to events.
    
    Use this mixin for components that need both capabilities.
    This is the most common pattern for interactive components.
    
    Example usage:
        class AnalysisPanel(QWidget, EventBusComponentMixin):
            def __init__(self, app_context):
                EventBusComponentMixin.__init__(self, app_context.event_bus)
                QWidget.__init__(self)
                self.setup_event_subscriptions()
                
            def setup_event_subscriptions(self):
                # Subscribe to events we care about
                self.subscribe_to_event(DatasetEvents.DATASET_CHANGED, self.on_dataset_changed)
                
            def apply_analysis(self):
                # Publish events when we do something
                self.publish_event("analysis.completed", {
                    'analysis_type': 'regression',
                    'dataset_id': self.current_dataset_id
                })
    """
    
    def __init__(self, event_bus: EventBus, *args, **kwargs):
        # Use composition instead of inheritance to avoid MRO conflicts
        if event_bus is None:
            raise ValueError("EventBusComponentMixin requires an EventBus instance")
        self._publisher = EventPublisherMixin(event_bus)
        self._subscriber = EventSubscriberMixin(event_bus)
        super().__init__(*args, **kwargs)
    
    # Delegate publisher methods
    def publish_event(self, event_type: str, data: Dict[str, Any] | None = None) -> None:
        """Publish an event through the event bus with automatic hierarchy."""
        return self._publisher.publish_event(event_type, data)
    
    # Delegate subscriber methods
    def subscribe_to_event(self, event_type: str, handler: Callable[[Dict[str, Any]], None]) -> None:
        """Subscribe to an event type."""
        return self._subscriber.subscribe_to_event(event_type, handler)
    
    def unsubscribe_all(self) -> None:
        """Unsubscribe from all events."""
        return self._subscriber.unsubscribe_all()
    
    def __del__(self):
        """Clean up subscriptions when object is destroyed."""
        try:
            self.unsubscribe_all()
        except Exception:
            pass  # Ignore errors during cleanup
