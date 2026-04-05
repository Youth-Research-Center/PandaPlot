from PySide6.QtCore import QPoint, Qt, Signal, SignalInstance
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QTabBar, QTabWidget, QWidget


class TabHeaderContextMenu(QMenu):
    def __init__(self, parent: QWidget, tab_index: int, tab_count: int, tab_close_requested: SignalInstance):
        super().__init__(parent)
        self.tab_close_requested = tab_close_requested
        self.tab_count = tab_count
        self.tab_index = tab_index

        self.setup_ui()

    def setup_ui(self):
        close_action = QAction("Close Tab", self)
        close_action.triggered.connect(lambda: self.tab_close_requested.emit(self.tab_index))
        self.addAction(close_action)

        if self.tab_count > 1:
            # Close Others
            close_others_action = QAction("Close Others", self)
            
            close_others_action.triggered.connect(self._close_others)
            self.addAction(close_others_action)

            # Close All
            close_all_action = QAction("Close All", self)
            
            close_all_action.triggered.connect(self._close_all)
            self.addAction(close_all_action)
        
    def _close_others(self):
        # Iterate in reverse to avoid index shifting
        for i in reversed(range(self.tab_count)):
            if i != self.tab_index:
                self.tab_close_requested.emit(i)
    def _close_all(self):
        # Close all tabs (reverse order for safety)
        for i in reversed(range(self.tab_count)):
            self.tab_close_requested.emit(i)

class CustomTabBar(QTabBar):
    """Custom tab bar that supports drag and drop reordering and close buttons."""
    
    tab_close_requested = Signal(int)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setMovable(True)  # Enable drag and drop
        self.setTabsClosable(True)  # Enable close buttons
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # Connect signals
        self.tabCloseRequested.connect(self.tab_close_requested.emit)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def _get_tab_count(self) -> int:
        parent_tab_widget = self.parentWidget()
        return isinstance(parent_tab_widget, QTabWidget) and parent_tab_widget.count() or 0

    def show_context_menu(self, position: QPoint):
        """Show context menu for tab operations."""
        tab_index = self.tabAt(position)
        if tab_index >= 0:
            menu = TabHeaderContextMenu(self, tab_index, self._get_tab_count(), self.tab_close_requested)
            menu.exec(self.mapToGlobal(position))
