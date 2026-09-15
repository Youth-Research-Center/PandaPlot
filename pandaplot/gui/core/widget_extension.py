

import logging
from abc import abstractmethod
from collections.abc import Callable
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog, QMainWindow, QMenuBar, QTabWidget, QWidget, QWizard, QWizardPage

from pandaplot.models.events.event_types import ThemeEvents
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.unsaved_changes_registry import UnsavedChangesRegistry


class WidgetExtension:
    def __init__(self, app_context: AppContext):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.app_context = app_context
        self._subscriptions : List[Tuple[str, Callable]] = []
        self._unsaved_changes_registry: Optional[UnsavedChangesRegistry] = None
    
    @abstractmethod
    def _init_ui(self):
        """Set up the user interface components."""
        pass

    @abstractmethod
    def _apply_theme(self):
        pass

    def _initialize(self):
        self._init_ui()
        self._apply_theme()
        self._setup_base_event_subscriptions()
        self.setup_event_subscriptions()
        self.logger.info(f"{self.__class__.__name__} initialized.")

    def _on_theme_changed(self, event_data: dict):
        """Handle theme changes by applying appropriate background and font settings."""
        try:
            self._apply_theme()
        except Exception as e:
            self.logger.warning("Failed applying theme to main window: %s", e)
    
    def setup_event_subscriptions(self):    
        """Set up event subscriptions for the main window."""
        pass

    def _setup_base_event_subscriptions(self):
        self.subscribe_to_event(ThemeEvents.THEME_CHANGED, self._on_theme_changed)

    def publish_event(self, event_type: str, data: Dict[str, Any] | None = None) -> None:
        """Publish an event through the event bus."""
        event_data = data or {}
        event_data["source_component"] = self.__class__.__name__
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

    def register_unsaved_changes_source(self) -> None:
        """Opt into flush_pending_edits(): this object must implement
        has_unsaved_changes()/save() (see UnsavedChangesSource). Deregistered
        by unsubscribe_all() -- the same synchronous teardown call already
        invoked (via unsubscribe_widget_tree) at every place a widget is
        closed, so a closed widget is never left flushable mid-teardown.
        Relying on the destroyed signal alone was already tried and rejected
        for event-bus subscriptions (see unsubscribe_widget_tree below) -- it
        only fires once Qt's deferred deleteLater() destruction actually
        runs, leaving the same race window this avoids.
        """
        self._unsaved_changes_registry = self.app_context.get_manager(UnsavedChangesRegistry)
        self._unsaved_changes_registry.register(self)

    def unsubscribe_all(self) -> None:
        """Unsubscribe from all events, and deregister from the
        unsaved-changes registry if register_unsaved_changes_source() was
        called.

        This should be called in component cleanup/destruction to prevent memory leaks.
        """
        for event_type, handler in self._subscriptions:
            self.app_context.event_bus.unsubscribe(event_type, handler)
        self._subscriptions.clear()
        if self._unsaved_changes_registry is not None:
            self._unsaved_changes_registry.unregister(self)
            self._unsaved_changes_registry = None

    def __del__(self):
        """Clean up subscriptions when object is destroyed."""
        try:
            # we are unsubscribing from all events ideally when destroyed is called
            # leaving this in case we don't use QWidget/QObject
            self.unsubscribe_all()
        except Exception:
            pass  # Ignore errors during cleanup


def unsubscribe_widget_tree(widget: Any) -> None:
    """Unsubscribe `widget` and every descendant of it that subscribes to
    the event bus, from the event bus.

    deleteLater() only defers actual C++ destruction, so a widget left
    subscribed can still have its handler invoked -- e.g. by a theme change --
    between now and whenever Qt gets around to the deferred delete. That
    handler may reach into a nested subscriber (like a tab's chart editor, or
    a non-widget QObject such as a table model parented under the tab) that
    has its own independent subscriptions on top of the top-level widget's
    own, so unsubscribing only the top-level widget still leaves those live.
    Call this instead of `widget.unsubscribe_all()` alone wherever a widget
    subtree is being torn down.

    The descendant search walks every QObject in the subtree, not just
    WidgetExtension ones: a subscriber doesn't have to be a widget at all
    (e.g. PandasTableModel subscribes directly to dataset events despite
    being a QAbstractTableModel, not a widget) -- it only needs its own
    `unsubscribe_all()` and to be Qt-parented somewhere under `widget`.

    Duck-typed like the callers this replaces: `widget` need not be a real
    QWidget/WidgetExtension (tests exercise this with plain Mocks), so both
    the top-level call and the descendant search degrade to a no-op rather
    than raising when the expected methods aren't there. Also tolerates the
    widget's own C++ object already being gone by the time this runs (a
    shiboken RuntimeError, not a TypeError) -- the exact "already deleted"
    failure mode this helper exists to prevent downstream, so it must not
    itself blow up on it.
    """
    if hasattr(widget, "unsubscribe_all"):
        try:
            widget.unsubscribe_all()
        except RuntimeError:
            pass  # fall through -- the descendant search may still work

    find_children = getattr(widget, "findChildren", None)
    if not callable(find_children):
        return
    try:
        children = list(find_children(QObject))
    except (TypeError, RuntimeError):
        return
    for child in children:
        if hasattr(child, "unsubscribe_all"):
            try:
                child.unsubscribe_all()
            except RuntimeError:
                continue


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

class PMenuBar(WidgetExtension, QMenuBar):
    def __init__(self, app_context:AppContext, parent: Optional[QWidget] = None, **kwargs):
        QMenuBar.__init__(self, parent, **kwargs)
        WidgetExtension.__init__(self, app_context=app_context)
        self.destroyed.connect(self.unsubscribe_all)

class PTabWidget(WidgetExtension, QTabWidget):
    def __init__(self, app_context:AppContext, parent: Optional[QWidget] = None, **kwargs):
        QTabWidget.__init__(self, parent, **kwargs)
        WidgetExtension.__init__(self, app_context=app_context)
        self.destroyed.connect(self.unsubscribe_all)

class PDialog(WidgetExtension, QDialog):
    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None, **kwargs):
        QDialog.__init__(self, parent, **kwargs)
        WidgetExtension.__init__(self, app_context=app_context)
        self.destroyed.connect(self.unsubscribe_all)


class PWizard(WidgetExtension, QWizard):
    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None, **kwargs):
        QWizard.__init__(self, parent, **kwargs)
        WidgetExtension.__init__(self, app_context=app_context)
        self.destroyed.connect(self.unsubscribe_all)


class PWizardPage(WidgetExtension, QWizardPage):
    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None, **kwargs):
        QWizardPage.__init__(self, parent, **kwargs)
        WidgetExtension.__init__(self, app_context=app_context)
        self.destroyed.connect(self.unsubscribe_all)
