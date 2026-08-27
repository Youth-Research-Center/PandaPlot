from typing import override

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget

from pandaplot.gui.core.widget_extension import PMainWindow
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class FloatingTabWindow(PMainWindow):
    """A top-level window that hosts a single popped-out tab widget.

    The hosted widget is the exact same widget that used to live in the main
    tab container, so it keeps its state and event subscriptions. Closing the
    window asks the owning TabContainer to re-dock the widget back into the
    main workspace, unless the container closed the window itself.
    """

    redock_requested = Signal(str)  # item_id

    def __init__(self, app_context: AppContext, item_id: str, content: QWidget, title: str):
        super().__init__(app_context=app_context)
        self.item_id = item_id
        self._content = content
        self._redock_on_close = True

        # Do not keep the application alive on our own, and clean ourselves up
        # once closed so redocked/closed windows don't leak.
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, on=False)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, on=True)

        self._initialize()

        self.setWindowTitle(title)
        self.setCentralWidget(content)
        # QTabWidget.removeTab() hides the page widget; make it visible again
        # now that it lives in this window, otherwise the window looks blank.
        content.setVisible(True)
        self.resize(900, 650)

    @override
    def _init_ui(self):
        pass

    @override
    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        background_color = palette.get("card_bg", "#F5F5F5")
        self.setStyleSheet(f"QMainWindow {{ background-color: {background_color}; }}")

    def update_tab_title(self, widget: QWidget, new_title: str):
        """Mirror TabContainer's API so a popped-out tab can refresh its title.

        Tab widgets walk up their parent chain looking for ``update_tab_title``
        to push a new title; once popped out, that parent is this window.
        """
        if widget is self._content:
            self.setWindowTitle(new_title)

    def take_content(self) -> QWidget | None:
        """Release the hosted widget without deleting it (used when re-docking)."""
        content = self.takeCentralWidget()
        self._content = None
        return content

    def close_without_redock(self):
        """Close the window without asking to re-dock (container-driven close)."""
        self._redock_on_close = False
        self.close()

    @override
    def closeEvent(self, event):
        if self._redock_on_close and self._content is not None:
            self.redock_requested.emit(self.item_id)
        super().closeEvent(event)
