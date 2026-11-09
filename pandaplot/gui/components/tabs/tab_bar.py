from PySide6.QtCore import QMimeData, QPoint, Qt, Signal, SignalInstance
from PySide6.QtGui import QAction, QDrag
from PySide6.QtWidgets import QApplication, QMenu, QTabBar, QTabWidget, QWidget

TAB_DRAG_MIME_TYPE = "application/x-pandaplot-tab"


class TabHeaderContextMenu(QMenu):
    def __init__(
        self,
        parent: QWidget,
        tab_index: int,
        tab_count: int,
        tab_close_requested: SignalInstance,
        split_requested: SignalInstance,
        move_to_other_pane_requested: SignalInstance,
        close_split_requested: SignalInstance,
        tab_popout_requested: SignalInstance,
        *,
        can_split: bool,
        can_merge: bool,
    ):
        super().__init__(parent)
        self.tab_close_requested = tab_close_requested
        self.tab_popout_requested = tab_popout_requested
        self.tab_count = tab_count
        self.tab_index = tab_index

        self.setup_ui()

        popout_action = QAction("Open in New Window", self)
        popout_action.triggered.connect(lambda: self.tab_popout_requested.emit(self.tab_index))
        self.addAction(popout_action)

        if can_split:
            split_action = QAction("Split Right", self)
            split_action.triggered.connect(lambda: split_requested.emit(self.tab_index))
            self.addAction(split_action)

        if can_merge:
            move_action = QAction("Move to Other Pane", self)
            move_action.triggered.connect(lambda: move_to_other_pane_requested.emit(self.tab_index))
            self.addAction(move_action)

            close_split_action = QAction("Close Split", self)
            close_split_action.triggered.connect(lambda: close_split_requested.emit())
            self.addAction(close_split_action)

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
    split_requested = Signal(int)
    move_to_other_pane_requested = Signal(int)
    close_split_requested = Signal()
    tab_popout_requested = Signal(int)
    bar_drop_requested = Signal(object, int, int)  # source_pane_id, source_index, drop_index

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setMovable(True)  # Enable drag and drop
        self.setTabsClosable(True)  # Enable close buttons
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setAcceptDrops(True)

        self.can_split = True
        self.can_merge = False

        self._press_pos: QPoint | None = None
        self._press_index: int = -1

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
            menu = TabHeaderContextMenu(
                self,
                tab_index,
                self._get_tab_count(),
                self.tab_close_requested,
                self.split_requested,
                self.move_to_other_pane_requested,
                self.close_split_requested,
                self.tab_popout_requested,
                can_split=self.can_split,
                can_merge=self.can_merge,
            )
            menu.exec(self.mapToGlobal(position))

    # ----- drag start (escalates to a real QDrag once the cursor leaves the bar) -----
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.pos()
            self._press_index = self.tabAt(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (
            self._press_pos is not None
            and self._press_index >= 0
            and (event.buttons() & Qt.MouseButton.LeftButton)
            and not self.rect().contains(event.pos())
            and (event.pos() - self._press_pos).manhattanLength() >= QApplication.startDragDistance()
        ):
            self._start_drag()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._press_pos = None
        self._press_index = -1
        super().mouseReleaseEvent(event)

    def _start_drag(self):
        index = self._press_index
        self._press_pos = None
        self._press_index = -1

        pane = self.parentWidget()
        if pane is None or index < 0:
            return

        mime = QMimeData()
        mime.setData(TAB_DRAG_MIME_TYPE, f"{id(pane)}:{index}".encode())

        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)

    # ----- drop target (tabs dropped from either bar) -----
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(TAB_DRAG_MIME_TYPE):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(TAB_DRAG_MIME_TYPE):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event):
        mime = event.mimeData()
        if not mime.hasFormat(TAB_DRAG_MIME_TYPE):
            super().dropEvent(event)
            return

        payload = bytes(mime.data(TAB_DRAG_MIME_TYPE)).decode()
        pane_id_str, index_str = payload.split(":")
        source_pane_id = int(pane_id_str)
        source_index = int(index_str)

        drop_index = self.tabAt(event.position().toPoint())
        if drop_index < 0:
            drop_index = self.count()

        self.bar_drop_requested.emit(source_pane_id, source_index, drop_index)
        event.acceptProposedAction()
