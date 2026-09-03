"""Regression test for the "closed chart tab still reacts to theme changes"
bug: a tab like ChartTab embeds its own independently-subscribed child
widget (ChartEditorWidget), each a PWidget with its own event-bus
subscriptions. Closing the tab only ever unsubscribed the top-level widget,
leaving the nested child's subscription live until Qt got around to the
deferred deleteLater() destruction -- a window in which a theme change (or
any other event that child listens for) invoked its handler on a widget
whose C++ object could already be partially torn down.
"""
import sys
from unittest.mock import Mock

import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from pandaplot.gui.components.tabs.dataset.pandas_table_model import PandasTableModel
from pandaplot.gui.core.widget_extension import PWidget, unsubscribe_widget_tree
from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.events.event_types import DatasetEvents, ThemeEvents
from pandaplot.models.project.items.dataset import Dataset


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


class _FakeAppContext:
    def __init__(self):
        self.event_bus = EventBus()

    def get_app_state(self):
        return None


class _Leaf(PWidget):
    """Stands in for ChartEditorWidget: a nested PWidget with its own
    independent subscription."""

    def _init_ui(self):
        pass

    def _apply_theme(self):
        pass


class _Parent(PWidget):
    """Stands in for ChartTab: a PWidget that embeds a child PWidget."""

    def __init__(self, app_context, parent=None):
        super().__init__(app_context=app_context, parent=parent)
        self._initialize()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        self.child = _Leaf(app_context=self.app_context, parent=self)
        self.child._initialize()
        layout.addWidget(self.child)

    def _apply_theme(self):
        pass


def test_unsubscribe_widget_tree_covers_nested_pwidget_children():
    app_context = _FakeAppContext()
    parent = _Parent(app_context=app_context)

    theme_subscribers = app_context.event_bus._subscribers[ThemeEvents.THEME_CHANGED]
    assert parent._on_theme_changed in theme_subscribers
    assert parent.child._on_theme_changed in theme_subscribers

    unsubscribe_widget_tree(parent)

    theme_subscribers = app_context.event_bus._subscribers[ThemeEvents.THEME_CHANGED]
    assert parent._on_theme_changed not in theme_subscribers
    assert parent.child._on_theme_changed not in theme_subscribers


def test_unsubscribe_widget_tree_tolerates_plain_qwidget():
    """A widget with no WidgetExtension mixin at all must not raise."""
    widget = QWidget()
    unsubscribe_widget_tree(widget)  # no-op, must not raise


def test_unsubscribe_widget_tree_tolerates_already_deleted_widget():
    """The widget's own C++ object can already be gone by the time this
    runs (shiboken raises RuntimeError, not TypeError) -- this is the exact
    "already deleted" failure this helper exists to prevent downstream, so
    it must degrade to a no-op rather than raising itself."""
    widget = Mock()
    widget.unsubscribe_all.side_effect = RuntimeError(
        "Internal C++ object already deleted."
    )
    widget.findChildren.side_effect = RuntimeError(
        "Internal C++ object already deleted."
    )

    unsubscribe_widget_tree(widget)  # must not raise

    widget.unsubscribe_all.assert_called_once()


def test_unsubscribe_widget_tree_tolerates_a_child_already_deleted():
    """One nested child raising on unsubscribe_all() must not stop the
    others in the same subtree from being unsubscribed."""
    ok_child = Mock()
    dying_child = Mock()
    dying_child.unsubscribe_all.side_effect = RuntimeError("already deleted")

    widget = Mock()
    widget.findChildren.return_value = [dying_child, ok_child]

    unsubscribe_widget_tree(widget)  # must not raise

    dying_child.unsubscribe_all.assert_called_once()
    ok_child.unsubscribe_all.assert_called_once()


def test_unsubscribe_widget_tree_covers_non_widget_qobject_subscribers():
    """PandasTableModel subscribes directly to dataset events despite being
    a QAbstractTableModel, not a WidgetExtension -- e.g. DatasetTab parents
    one under itself. The descendant search must not be scoped to
    WidgetExtension only, or a subscriber like this would stay subscribed
    after its owning tab closes and still react to a later dataset event."""
    app_context = _FakeAppContext()
    parent = QWidget()
    dataset = Dataset(id="ds-1", name="Test", data=pd.DataFrame({"a": [1, 2, 3]}))
    model = PandasTableModel(app_context, dataset, parent=parent)

    subscribers = app_context.event_bus._subscribers[DatasetEvents.DATASET_DATA_CHANGED]
    assert model.on_dataset_changed in subscribers

    unsubscribe_widget_tree(parent)

    subscribers = app_context.event_bus._subscribers[DatasetEvents.DATASET_DATA_CHANGED]
    assert model.on_dataset_changed not in subscribers
