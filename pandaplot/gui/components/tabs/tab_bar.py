from PySide6.QtWidgets import QMenu, QTabBar, QTabWidget
from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QAction

class CustomTabBar(QTabBar):
    """Custom tab bar that supports drag and drop reordering and close buttons."""
    
    tab_close_requested = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(True)  # Enable drag and drop
        self.setTabsClosable(True)  # Enable close buttons
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        
        # Connect signals
        self.tabCloseRequested.connect(self.tab_close_requested.emit)
        self.customContextMenuRequested.connect(self.show_context_menu)
    
    def show_context_menu(self, position: QPoint):
        """Show context menu for tab operations."""
        tab_index = self.tabAt(position)
        if tab_index >= 0:
            menu = QMenu(self)
            
            close_action = QAction("Close Tab", self)
            close_action.triggered.connect(lambda: self.tab_close_requested.emit(tab_index))
            menu.addAction(close_action)

            parent_tab_widget = self.parentWidget()
            if isinstance(parent_tab_widget, QTabWidget) and parent_tab_widget.count() > 1:
                # Close Others
                close_others_action = QAction("Close Others", self)
                def _close_others():
                    # Iterate in reverse to avoid index shifting
                    for i in reversed(range(parent_tab_widget.count())):
                        if i != tab_index:
                            self.tab_close_requested.emit(i)
                close_others_action.triggered.connect(_close_others)
                menu.addAction(close_others_action)

                # Close All
                close_all_action = QAction("Close All", self)
                def _close_all():
                    # Close all tabs (reverse order for safety)
                    for i in reversed(range(parent_tab_widget.count())):
                        self.tab_close_requested.emit(i)
                close_all_action.triggered.connect(_close_all)
                menu.addAction(close_all_action)
            
            # Show context menu at the cursor position
            menu.exec(self.mapToGlobal(position))


