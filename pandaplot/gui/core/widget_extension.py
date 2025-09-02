

from abc import abstractmethod
from collections.abc import Callable
import logging
from typing import Any, Dict, List, Optional, Tuple

from pandaplot.models.events.event_types import ThemeEvents
from pandaplot.models.state.app_context import AppContext
from PySide6.QtWidgets import QMainWindow, QWidget

class WidgetExtension:
    def __init__(self, app_context: AppContext):
        self.logger = logging.getLogger(__name__)
        self.app_context = app_context
        self._subscriptions : List[Tuple[str, Callable]] = []
    
    @abstractmethod
    def _init_ui(self):
        """Set up the user interface components."""
        pass

    @abstractmethod
    def _apply_theme(self):
        pass

    def _on_theme_changed(self, event_data: dict):
        """Handle theme changes by applying appropriate background and font settings."""
        try:
            self._apply_theme()
        except Exception as e:
            self.logger.warning("Failed applying theme to main window: %s", e)

    def publish_event(self, event_type: str, data: Dict[str, Any] | None = None) -> None:
        """Publish an event through the event bus."""
        event_data = data or {}
        event_data['source_component'] = self.__class__.__name__
        self.app_context.event_bus.emit(event_type, event_data)

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
        self.app_context.event_bus.subscribe(event_type, handler)
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

    def setup_event_subscriptions(self):    
        """Set up event subscriptions for the main window."""
        self.subscribe_to_event(ThemeEvents.THEME_CHANGED, self._on_theme_changed)
    
    def unsubscribe_all(self) -> None:
        """Unsubscribe from all events.
        
        This should be called in component cleanup/destruction to prevent memory leaks.
        """
        for event_type, handler in self._subscriptions:
            self.app_context.event_bus.unsubscribe(event_type, handler)
        self._subscriptions.clear()

    def __del__(self):
        """Clean up subscriptions when object is destroyed."""
        try:
            self.unsubscribe_all()
        except Exception:
            pass  # Ignore errors during cleanup


class PMainWindow(WidgetExtension, QMainWindow):
    def __init__(self, app_context:AppContext):
        QMainWindow.__init__(self)
        WidgetExtension.__init__(self, app_context=app_context)
        self.destroyed.connect(self.unsubscribe_all)

class PWidget(WidgetExtension, QWidget):
    def __init__(self, app_context:AppContext, parent: Optional[QWidget] = None, **kwargs):
        QWidget.__init__(self, parent, **kwargs)
        WidgetExtension.__init__(self, app_context=app_context)
        self.destroyed.connect(self.unsubscribe_all)