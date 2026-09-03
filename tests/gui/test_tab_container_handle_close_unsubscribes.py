"""Regression test: closing a tab must unsubscribe its widget from the event
bus synchronously, rather than relying on Qt's `destroyed` signal (fired only
once deleteLater()'s deferred deletion actually runs). Deferred deletion left
a window where an event (e.g. a rename) could invoke a callback on a widget
whose C++ object was already gone, raising a shiboken RuntimeError -- crash
reported: 'libshiboken: Internal C++ object (ChartTab) already deleted.'
"""
from unittest.mock import Mock

from pandaplot.gui.components.tabs.tab_container import TabContainer


def _container_stub():
    container = TabContainer.__new__(TabContainer)
    container.tabs = {}
    container.publish_event = Mock()
    container._maybe_collapse_pane = Mock()
    container._persist_tab_session = Mock()
    container.logger = Mock()
    container.panes = []
    return container


def test_handle_close_unsubscribes_widget_before_deleting_it():
    container = _container_stub()

    widget = Mock()
    widget.unsubscribe_all = Mock()
    widget.deleteLater = Mock()
    container.tabs["item-1"] = widget

    pane = Mock()
    pane.count.return_value = 1
    pane.tabText.return_value = "My Tab"
    pane.widget.return_value = widget

    container._handle_close(pane, 0)

    widget.unsubscribe_all.assert_called_once()
    widget.deleteLater.assert_called_once()
    # Must unsubscribe before scheduling deletion, not after -- otherwise a
    # callback could still fire in the deleteLater() -> destroyed() window.
    call_names = [name for name, _args, _kwargs in widget.method_calls]
    assert call_names.index("unsubscribe_all") < call_names.index("deleteLater")


def test_close_tab_by_item_id_unsubscribes_floating_window_content():
    """Same race, popped-out-window flavor: FloatingTabWindow's
    WA_DeleteOnClose means close_without_redock() defers destruction the
    same way deleteLater() does for docked tabs."""
    container = _container_stub()

    content = Mock()
    content.unsubscribe_all = Mock()
    content.deleteLater = Mock()

    window = Mock()
    window.take_content.return_value = content

    container.floating_windows = {"item-1": window}
    container.tabs = {"item-1": content}

    container.close_tab_by_item_id("item-1")

    window.take_content.assert_called_once()
    content.unsubscribe_all.assert_called_once()
    content.deleteLater.assert_called_once()
    # The window itself (FloatingTabWindow -> PMainWindow) has its own theme
    # subscription independent of its content's, and is itself deferred-deleted
    # by close_without_redock()'s WA_DeleteOnClose -- same race, same fix.
    window.unsubscribe_all.assert_called_once()
    window.close_without_redock.assert_called_once()
    assert "item-1" not in container.floating_windows


def test_handle_close_tolerates_widget_without_unsubscribe_all():
    """Not every widget hosted in a tab is a PWidget (defensive hasattr guard)."""
    container = _container_stub()

    class _PlainWidget:
        def __init__(self):
            self.deleted = False

        def deleteLater(self):
            self.deleted = True

    widget = _PlainWidget()
    container.tabs["item-1"] = widget

    pane = Mock()
    pane.count.return_value = 1
    pane.tabText.return_value = "My Tab"
    pane.widget.return_value = widget

    container._handle_close(pane, 0)

    assert widget.deleted is True


def test_on_project_closed_unsubscribes_floating_window_content():
    """Same race as test_close_tab_by_item_id_unsubscribes_floating_window_content,
    but via the project-closed path: on_project_closed() used to call
    window.close_without_redock() directly for every popped-out tab, without
    ever detaching/unsubscribing its content first -- leaving a nested
    WidgetExtension (e.g. a chart editor) subscribed during the same
    deleteLater()-deferred-destruction window this file's other tests guard
    against."""
    container = _container_stub()

    content = Mock()
    content.unsubscribe_all = Mock()
    content.deleteLater = Mock()

    window = Mock()
    window.take_content.return_value = content

    container.floating_windows = {"item-1": window}
    container.tabs = {"item-1": content}

    container.on_project_closed()

    window.take_content.assert_called_once()
    content.unsubscribe_all.assert_called_once()
    content.deleteLater.assert_called_once()
    window.unsubscribe_all.assert_called_once()
    window.close_without_redock.assert_called_once()
    assert container.floating_windows == {}
    assert container.tabs == {}
