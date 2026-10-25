from unittest.mock import Mock

from PySide6.QtWidgets import QWidget

from pandaplot.gui.components.tabs.floating_tab_window import FloatingTabWindow


def test_user_close_redocks_the_floating_tab(qtbot):
    app_context = Mock()
    app_context.get_manager.return_value.get_surface_palette.return_value = {}
    content = QWidget()
    window = FloatingTabWindow(app_context, "note-1", content, "Note")
    qtbot.addWidget(window)
    redock_requested = Mock()
    window.redock_requested.connect(redock_requested)

    assert window.close() is True

    redock_requested.assert_called_once_with("note-1")
    assert window._content is content
