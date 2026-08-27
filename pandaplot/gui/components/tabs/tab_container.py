from typing import Optional, override

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QSplitter, QVBoxLayout, QWidget

from pandaplot.commands.project.chart import CreateChartFromWizardCommand
from pandaplot.commands.project.project import LoadProjectCommand, NewProjectCommand, OpenProjectCommand
from pandaplot.gui.components.tabs.floating_tab_window import FloatingTabWindow
from pandaplot.gui.components.tabs.tab import CustomTabWidget
from pandaplot.gui.components.tabs.welcome_tab import WelcomeTab
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.models.events import (
    AnalysisEvents,
    ChartEvents,
    ProjectEvents,
    UIEvents,
)
from pandaplot.models.project.items import Chart, Dataset, ImageGallery, Note
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.session import SessionPersistenceManager

_UNSET = object()


class TabContainer(PWidget):
    """
    A container widget that manages tabbed content for the main application workspace.
    Holds one or two CustomTabWidget "panes" side by side in a QSplitter, so the user
    can split a tab out into a second pane and view two tabs at once. Supports
    drag-and-drop reordering/splitting and tab closing.
    """

    active_tab_changed = Signal(object)  # the widget of the active pane's current tab, or None

    def __init__(self, app_context: AppContext, parent: QWidget):
        super().__init__(app_context=app_context, parent=parent)
        # TODO(#220): we shouldn't know about these tab types here
        self.tabs = {}
        self.panes: list[CustomTabWidget] = []
        self._pane_registry: dict[int, CustomTabWidget] = {}
        self._active_pane: CustomTabWidget | None = None
        self._last_emitted_widget = _UNSET
        # item_id -> FloatingTabWindow for tabs popped out into their own window.
        # Popped-out tabs stay tracked in self.tabs too, so lookups by item id
        # keep working while a tab lives outside the panes.
        self.floating_windows: dict[str, FloatingTabWindow] = {}

        self._initialize()
        self.create_default_tabs()

    @override
    def _init_ui(self):
        """Initialize the UI layout and components."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        layout.addWidget(self.splitter)

        first_pane = self._create_pane()
        self.splitter.addWidget(first_pane)
        self.panes.append(first_pane)
        self._active_pane = first_pane
        self._update_split_capabilities()

        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.focusChanged.connect(self._on_app_focus_changed)

    @override
    def _apply_theme(self):
        pass

    # ------------------------------------------------------------------
    # Pane management
    # ------------------------------------------------------------------

    def _create_pane(self) -> CustomTabWidget:
        """Build a new tab pane and wire its signals up to this container."""
        pane = CustomTabWidget(app_context=self.app_context, parent=self.splitter)
        self._pane_registry[id(pane)] = pane

        pane.tab_close_requested.connect(lambda index, p=pane: self._handle_close(p, index))
        pane.currentChanged.connect(lambda index, p=pane: self._handle_pane_current_changed(p, index))
        pane.split_requested.connect(lambda index, p=pane: self._handle_split(p, index))
        pane.move_to_other_pane_requested.connect(lambda index, p=pane: self._handle_move_to_other(p, index))
        pane.close_split_requested.connect(self._handle_close_split)
        pane.tab_popout_requested.connect(lambda index, p=pane: self.popout_tab(p, index))
        pane.bar_drop_requested.connect(
            lambda src_id, src_idx, drop_idx, p=pane: self._handle_bar_drop(p, src_id, src_idx, drop_idx)
        )
        pane.edge_drop_requested.connect(
            lambda src_id, src_idx, p=pane: self._handle_edge_drop(p, src_id, src_idx)
        )
        return pane

    def _pane_of(self, widget) -> CustomTabWidget | None:
        """Find which pane currently holds the given tab widget."""
        for pane in self.panes:
            if pane.indexOf(widget) >= 0:
                return pane
        return None

    def _update_split_capabilities(self):
        """Push down whether each pane can still split further or only merge back."""
        can_split = len(self.panes) == 1
        for pane in self.panes:
            pane.set_split_capable(can_split=can_split)
            pane.set_merge_capable(can_merge=not can_split)

    def _activate_pane(self, pane: CustomTabWidget):
        """Mark `pane` as the one driving the sidebar, updating the visual indicator."""
        show_indicator = len(self.panes) > 1
        for p in self.panes:
            p.set_active(is_active=show_indicator and p is pane)

        if pane is self._active_pane:
            return
        self._active_pane = pane
        self._emit_tab_changed_for_active_pane()

    def _on_app_focus_changed(self, _old, new):
        """Clicking anywhere inside a pane (not just its tab header) activates it."""
        if new is None:
            return
        for pane in self.panes:
            if pane is new or pane.isAncestorOf(new):
                self._activate_pane(pane)
                return

    def _maybe_collapse_pane(self, pane: CustomTabWidget):
        """If a pane just lost its last tab, remove it (or show the Welcome placeholder
        if it was the only pane left)."""
        if pane.count() > 0:
            return

        if len(self.panes) > 1:
            self.panes.remove(pane)
            self._pane_registry.pop(id(pane), None)
            pane.setParent(None)
            pane.deleteLater()
            self._update_split_capabilities()
            if self._active_pane is pane:
                self._activate_pane(self.panes[0])
            return

        if self.app_context and not self.app_context.get_app_state().has_project:
            self.create_welcome_tab(pane)

    def _move_tab(
        self,
        source_pane: CustomTabWidget,
        source_index: int,
        target_pane: CustomTabWidget,
        target_index: int | None = None,
    ):
        """Shared primitive behind every split/move action, whether triggered from the
        context menu or via drag-and-drop."""
        if source_index < 0 or source_index >= source_pane.count():
            return

        if source_pane is target_pane:
            dest = source_pane.count() - 1 if target_index is None else target_index
            dest = max(0, min(dest, source_pane.count() - 1))
            source_pane.tabBar().moveTab(source_index, dest)
            return

        widget = source_pane.widget(source_index)
        title = source_pane.tabText(source_index)
        source_pane.removeTab(source_index)

        insert_at = target_pane.count() if target_index is None else target_index
        insert_at = max(0, min(insert_at, target_pane.count()))
        target_pane.insertTab(insert_at, widget, title)
        target_pane.setCurrentIndex(insert_at)

        self._activate_pane(target_pane)
        self._maybe_collapse_pane(source_pane)
        self._persist_tab_session()

    def _handle_split(self, pane: CustomTabWidget, index: int):
        """'Split Right': move a tab out of `pane` into a brand new second pane."""
        if len(self.panes) >= 2:
            return
        new_pane = self._create_pane()
        self.splitter.addWidget(new_pane)
        self.panes.append(new_pane)
        self._update_split_capabilities()
        self._move_tab(pane, index, new_pane, 0)

    def _handle_move_to_other(self, pane: CustomTabWidget, index: int):
        """'Move to Other Pane': relocate a tab to the other existing pane."""
        others = [p for p in self.panes if p is not pane]
        if not others:
            return
        self._move_tab(pane, index, others[0])

    def _handle_close_split(self):
        """'Close Split': merge the secondary pane's tabs back into the primary one."""
        if len(self.panes) < 2:
            return
        primary, secondary = self.panes[0], self.panes[1]
        while secondary.count() > 0:
            self._move_tab(secondary, 0, primary)
        self._activate_pane(primary)

    def _handle_bar_drop(self, target_pane: CustomTabWidget, source_pane_id: int, source_index: int, drop_index: int):
        source_pane = self._pane_registry.get(source_pane_id)
        if source_pane is None:
            return
        self._move_tab(source_pane, source_index, target_pane, drop_index)

    def _handle_edge_drop(self, target_pane: CustomTabWidget, source_pane_id: int, source_index: int):
        """A tab was dropped on the right-edge zone of the (only) pane: split it out."""
        if len(self.panes) >= 2:
            return
        source_pane = self._pane_registry.get(source_pane_id)
        if source_pane is None or source_pane is not target_pane:
            return
        self._handle_split(source_pane, source_index)

    # ------------------------------------------------------------------

    def create_default_tabs(self):
        """Create the default tabs for the application."""
        # Only show Welcome tab if no project is loaded
        if self.app_context and not self.app_context.get_app_state().has_project:
            self.create_welcome_tab()

    def _handle_close(self, pane: CustomTabWidget, index: int):
        """
        Handle tab close request.

        Args:
            pane: The pane the tab belongs to
            index (int): The index of the tab to close
        """
        if index < 0 or index >= pane.count():
            return

        # Get tab title before removing
        tab_title = pane.tabText(index)

        # Get the widget before removing the tab
        widget = pane.widget(index)

        item_id_to_remove = None
        for curr_item_id, curr_tab in self.tabs.items():
            if curr_tab is widget:
                item_id_to_remove = curr_item_id
                break
        if item_id_to_remove:
            del self.tabs[item_id_to_remove]

        # Remove the tab
        pane.removeTab(index)

        # Clean up the widget
        if widget:
            widget.deleteLater()

        # Publish tab closed event
        self.publish_event(UIEvents.TAB_CLOSED, {
            "tab_index": index,
            "tab_title": tab_title,
            "tab_id": id(widget) if widget else None
        })

        # Collapse the pane (or show the Welcome placeholder) if it's now empty
        self._maybe_collapse_pane(pane)

        self._persist_tab_session()

    def close_tab_by_item_id(self, item_id: str):
        """Close a tab by its associated item ID, if open."""
        # Popped-out tabs live in their own window; close it without re-docking.
        if item_id in self.floating_windows:
            window = self.floating_windows.pop(item_id)
            self.tabs.pop(item_id, None)
            window.close_without_redock()
            self._persist_tab_session()
            return
        if item_id not in self.tabs:
            return
        tab_widget = self.tabs[item_id]
        try:
            pane = self._pane_of(tab_widget)
            index = pane.indexOf(tab_widget) if pane is not None else -1
            if pane is not None and index >= 0:
                self._handle_close(pane, index)
            else:
                del self.tabs[item_id]
        except RuntimeError:
            del self.tabs[item_id]

    def popout_tab(self, pane: CustomTabWidget, index: int):
        """Detach the tab at ``index`` of ``pane`` into its own floating window.

        The tab widget is reparented (not recreated) so it keeps all of its
        state; it stays tracked in ``self.tabs`` so lookups by item id still
        resolve while it lives in the floating window.
        """
        if index < 0 or index >= pane.count():
            return

        widget = pane.widget(index)

        # Only item-backed tabs (chart/dataset/note) can be popped out.
        item_id = None
        for curr_item_id, curr_tab in self.tabs.items():
            if curr_tab is widget:
                item_id = curr_item_id
                break
        if item_id is None:
            self.logger.debug("Cannot pop out a tab without an associated item")
            return

        title = pane.tabText(index)
        # Detach from the pane without deleting the widget.
        pane.removeTab(index)

        window = FloatingTabWindow(self.app_context, item_id, widget, title)
        window.redock_requested.connect(self.redock_tab)
        self.floating_windows[item_id] = window
        window.show()
        window.raise_()
        window.activateWindow()

        # A pane emptied by the popout should collapse back.
        self._maybe_collapse_pane(pane)
        self._persist_tab_session()

    def redock_tab(self, item_id: str):
        """Return a popped-out tab to the active pane of the main container."""
        window = self.floating_windows.pop(item_id, None)
        if window is None:
            return

        content = window.take_content()
        if content is None:
            return

        target_pane = self._active_pane or (self.panes[0] if self.panes else None)
        if target_pane is None:
            return

        self._remove_welcome_placeholder(target_pane)

        title = content.get_tab_title() if hasattr(content, "get_tab_title") else item_id
        index = target_pane.addTab(content, title)
        self.tabs[item_id] = content
        target_pane.setCurrentIndex(index)
        self._activate_pane(target_pane)

        self._persist_tab_session()

    def _remove_welcome_placeholder(self, pane: CustomTabWidget):
        """Drop the placeholder Welcome tab from ``pane``, if present."""
        for index in range(pane.count() - 1, -1, -1):
            if isinstance(pane.widget(index), WelcomeTab):
                pane.removeTab(index)

    def _open_tab_into_pane(self, item_id: str, target_pane: CustomTabWidget) -> bool:
        """Create the tab widget for `item_id` and add it into `target_pane`.

        Shared tail used both by interactive opens (`open_tab`) and session restore
        (`restore_tab_session`). Returns True if a tab was created.
        """
        if item_id in self.tabs:
            return False

        if not self.app_context.get_app_state().has_project:
            self.logger.warning("Cannot open item: No project loaded")
            return False

        project = self.app_context.get_app_state().current_project
        if not project:
            self.logger.warning("Cannot open item: No project loaded")
            return False

        item = project.find_item(item_id)
        if item is None:
            self.logger.warning("Cannot open item: Item %s not found", item_id)
            return False

        try:
            new_tab = self._create_tab(item)
            tab_index = target_pane.addTab(new_tab, new_tab.get_tab_title())
            self.tabs[item_id] = new_tab
            target_pane.setCurrentIndex(tab_index)
            return True
        except Exception as e:
            self.logger.error("Failed to open tab for item %s: %s", item_id, str(e))
            return False

    def get_tab_widget(self, item_id: str) -> Optional[QWidget]:
        """Return the live tab widget for `item_id` if it's currently open, else None."""
        return self.tabs.get(item_id)

    def open_tab(self, item_id):
        if not self.app_context:
            self.logger.warning("Cannot open tab: No app context provided")
            return

        # If this tab is popped out, bring its window to the front.
        if item_id in self.floating_windows:
            window = self.floating_windows[item_id]
            window.raise_()
            window.activateWindow()
            return

         # Check if the tab is already open
        if item_id in self.tabs:
            existing_tab = self.tabs[item_id]
            try:
                pane = self._pane_of(existing_tab)
                index = pane.indexOf(existing_tab) if pane is not None else -1
                if pane is not None and index >= 0:
                    pane.setCurrentIndex(index)
                    self._activate_pane(pane)
                    return
                else:
                    # Tab no longer exists, remove from tracking
                    del self.tabs[item_id]
            except RuntimeError:
                # Qt object has been deleted, remove from tracking
                del self.tabs[item_id]

        # Get note data from project
        if not self.app_context.get_app_state().has_project:
            self.logger.warning("Cannot open note: No project loaded")
            return

        target_pane = self._active_pane or self.panes[0]
        if self._open_tab_into_pane(item_id, target_pane):
            self._activate_pane(target_pane)
            self._persist_tab_session()

    def restore_tab_session(
        self,
        panes_data: list[list[str]],
        active_item_id: str | None,
        splitter_sizes: list[int] | None = None,
    ):
        """Reopen tabs (and the pane layout) remembered from the previous session.

        Called once the project a session was saved against has finished
        loading (see pandaplot/app.py's startup restore hook). Restoration always
        happens into a single pane - split layouts are not persisted across restarts.
        """
        panes_data = [list(ids) for ids in panes_data if ids]
        if not panes_data:
            return

        # Drop the placeholder Welcome tab created before the project finished loading
        for pane in self.panes:
            for index in range(pane.count() - 1, -1, -1):
                if isinstance(pane.widget(index), WelcomeTab):
                    pane.removeTab(index)

        # Pre-create enough panes (max 2) so tabs can be opened directly into the
        # right one, instead of always landing in the active pane.
        while len(self.panes) < min(len(panes_data), 2):
            new_pane = self._create_pane()
            self.splitter.addWidget(new_pane)
            self.panes.append(new_pane)
        self._update_split_capabilities()

        for pane_index, item_ids in enumerate(panes_data[:2]):
            target_pane = self.panes[pane_index]
            for item_id in item_ids:
                self._open_tab_into_pane(item_id, target_pane)

        # A recorded pane that ended up with nothing restorable in it shouldn't
        # linger as an empty split.
        for pane in list(self.panes):
            self._maybe_collapse_pane(pane)

        if active_item_id and active_item_id in self.tabs:
            active_widget = self.tabs[active_item_id]
            pane = self._pane_of(active_widget)
            if pane is not None:
                index = pane.indexOf(active_widget)
                if index >= 0:
                    pane.setCurrentIndex(index)
                    self._activate_pane(pane)
        elif self.panes:
            self._activate_pane(self.panes[0])

        if splitter_sizes and len(splitter_sizes) == len(self.panes):
            self.splitter.setSizes(splitter_sizes)

    def _persist_tab_session(self):
        """Remember which tabs are open in which pane (and which is active) for
        next launch.

        No-op when no project is loaded: the placeholder Welcome tab created
        before a project loads (or after one closes) is not a real session and
        must not overwrite a previously remembered one.
        """
        if not self.app_context or not self.app_context.get_app_state().has_project:
            return
        try:
            session_manager = self.app_context.get_manager(SessionPersistenceManager)

            widget_to_id = {widget: item_id for item_id, widget in self.tabs.items()}
            panes_data: list[list[str]] = []
            for pane in self.panes:
                ids = []
                for i in range(pane.count()):
                    item_id = widget_to_id.get(pane.widget(i))
                    if item_id is not None:
                        ids.append(item_id)
                panes_data.append(ids)

            active_widget = self._active_pane.currentWidget() if self._active_pane else None
            active_id = None
            if active_widget is not None:
                data = self.get_tab_data(active_widget)
                if data.get("type") != "other":
                    active_id = data.get("id")

            session_manager.update_tabs(panes_data, active_id, self.splitter.sizes())
        except Exception as e:  # noqa: BLE001
            self.logger.warning("Failed to persist tab session: %s", e)

    def _create_tab(self, item):
        # TODO(#220): move to a separate factory class
        if item is None:
            raise ValueError("Item cannot be None")

        if isinstance(item, Note):
            from pandaplot.gui.components.tabs.note.note_tab import NoteTab
            return NoteTab(app_context=self.app_context, note=item, parent=self)
        elif isinstance(item, Chart):
            from pandaplot.gui.components.tabs.chart.chart_tab import ChartTab
            return ChartTab(app_context=self.app_context, chart=item, parent=self)
        elif isinstance(item, Dataset):
            from pandaplot.gui.components.tabs.dataset.dataset_tab import DatasetTab
            return DatasetTab(app_context=self.app_context, dataset=item, parent=self)
        elif isinstance(item, ImageGallery):
            from pandaplot.gui.components.tabs.image.image_gallery_tab import ImageGalleryTab
            return ImageGalleryTab(app_context=self.app_context, gallery=item, parent=self)
        else:
            raise ValueError(f"Unsupported item type, item class {item.__class__.__name__}")

    def update_tab_title(self, tab_widget, new_title: str):
        """Update the title of a specific tab."""
        pane = self._pane_of(tab_widget)
        if pane is None:
            return
        tab_index = pane.indexOf(tab_widget)
        if tab_index >= 0:
            pane.setTabText(tab_index, new_title)

    def handle_new_project(self):
        """Handle new project request from welcome tab."""
        if self.app_context:
            command = NewProjectCommand(self.app_context)
            self.app_context.get_command_executor().execute_command(command)

    def handle_open_project(self):
        """Handle open project request from welcome tab."""
        if self.app_context:
            command = OpenProjectCommand(self.app_context)
            self.app_context.get_command_executor().execute_command(command)

    def handle_recent_project(self, project_path: str):
        """Handle recent project selection from welcome tab."""
        if self.app_context:
            command = LoadProjectCommand(self.app_context, project_path)
            self.app_context.get_command_executor().execute_command(command)

    def handle_example_project(self, project_path: str):
        """Handle example project selection from welcome tab."""
        if self.app_context:
            command = LoadProjectCommand(self.app_context, project_path)
            self.app_context.get_command_executor().execute_command(command)

    def handle_import_data(self):
        """Handle import data request from welcome tab."""
        if self.app_context:
            # Import data requires a project to be loaded first
            if not self.app_context.get_app_state().has_project:
                # Create a new project first
                self.handle_new_project()

            # Show file dialog for data import (CSV or single-sheet Excel)
            from pandaplot.commands.project.dataset.import_data_command import (
                ImportDataCommand,
            )
            command = ImportDataCommand(self.app_context)
            self.app_context.get_command_executor().execute_command(command)

    def create_welcome_tab(self, pane: CustomTabWidget | None = None):
        """Create and add a welcome tab."""
        target_pane = pane or self._active_pane or (self.panes[0] if self.panes else None)
        if target_pane is None:
            return None

        welcome_tab = WelcomeTab(self.app_context, target_pane)

        # Connect welcome tab signals
        welcome_tab.new_project_requested.connect(self.handle_new_project)
        welcome_tab.open_project_requested.connect(self.handle_open_project)
        welcome_tab.recent_project_selected.connect(self.handle_recent_project)
        welcome_tab.import_data_requested.connect(self.handle_import_data)
        welcome_tab.example_project_selected.connect(self.handle_example_project)

        target_pane.addTab(welcome_tab, welcome_tab.get_tab_title())
        return welcome_tab

    def create_chart_from_dataset(self, dataset_id: str, preselected_column_ids: Optional[list[str]] = None):
        """Open the chart creation wizard for a dataset.

        The wizard is non-blocking, so no chart exists when this returns. The
        resulting chart's tab is opened by this container's
        `ChartEvents.CHART_CREATED` subscription once the user finishes.
        """
        if not self.app_context:
            self.logger.warning("Cannot create chart: No app context provided")
            return

        app_state = self.app_context.get_app_state()
        if app_state.has_project and app_state.current_project is None:
            self.logger.warning("Cannot create chart: No project loaded")
            return

        project = app_state.current_project
        if project is None:
            self.logger.warning("Cannot create chart: No project loaded")
            return
        dataset_item = project.find_item(dataset_id)
        if not dataset_item:
            self.logger.warning("Cannot create chart: Dataset %s not found", dataset_id)
            return

        command = CreateChartFromWizardCommand(
            self.app_context,
            dataset_id=dataset_id,
            preselected_column_ids=preselected_column_ids or [],
        )
        self.app_context.get_command_executor().execute_command(command)

    def on_project_closed(self):
        """Called when a project is closed - close all project-related tabs and show welcome tab if no tabs are open."""
        self.logger.info("Closing all project-related tabs")

        # Close any popped-out tabs (their windows aren't inside the panes).
        for item_id in list(self.floating_windows.keys()):
            window = self.floating_windows.pop(item_id)
            self.tabs.pop(item_id, None)
            window.close_without_redock()

        # Close all project-related tabs (tracked in self.tabs dictionary)
        # We need to collect tabs to close first to avoid modifying dictionary during iteration
        tabs_to_close = list(self.tabs.values())

        for tab_widget in tabs_to_close:
            try:
                pane = self._pane_of(tab_widget)
                index = pane.indexOf(tab_widget) if pane is not None else -1
                if pane is not None and index >= 0:
                    self._handle_close(pane, index)
                else:
                    # Tab not found in tab container, remove from tracking
                    self.logger.warning("Tab widget not found in tab container, cleaning up tracking")
                    item_id_to_remove = None
                    for curr_item_id, curr_tab in self.tabs.items():
                        if curr_tab is tab_widget:
                            item_id_to_remove = curr_item_id
                            break
                    if item_id_to_remove:
                        del self.tabs[item_id_to_remove]
            except RuntimeError:
                # Qt object has been deleted, continue with cleanup
                self.logger.debug("Qt widget already deleted during project close cleanup")

        # Clear tracking dictionaries since project is closed
        self.tabs.clear()

        # Create welcome tab if no tabs remain
        if self.panes and self.panes[0].count() == 0:
            self.create_welcome_tab()

    def setup_event_subscriptions(self):
        """Setup event subscriptions for this component."""
        self.subscribe_to_multiple_events([
            # Keep existing project events
            (ProjectEvents.PROJECT_CLOSED, lambda _: self.on_project_closed()),

            # Subscribe to dataset events
            (AnalysisEvents.ANALYSIS_COMPLETED, self.on_analysis_completed),
            (ChartEvents.CHART_CREATED, lambda event_data: self.open_tab(event_data.get("chart_id"))),
            (UIEvents.TAB_OPEN_REQUESTED, lambda event_data: self.open_tab(event_data.get("item_id"))),
            (ProjectEvents.PROJECT_ITEM_REMOVED, lambda event_data: self.close_tab_by_item_id(event_data.get("item_id"))),
        ])

    def _handle_pane_current_changed(self, pane: CustomTabWidget, index: int):
        """A pane's current tab changed - only the active pane drives the sidebar."""
        if pane is self._active_pane:
            self._emit_tab_changed_for_active_pane()

    def _emit_tab_changed_for_active_pane(self):
        """Publish UIEvents.TAB_CHANGED / active_tab_changed for the active pane's
        current tab, deduped so unrelated focus churn doesn't spam the sidebar."""
        pane = self._active_pane
        widget = pane.currentWidget() if pane else None

        if widget is self._last_emitted_widget:
            return
        self._last_emitted_widget = widget

        self.active_tab_changed.emit(widget)

        tab_data = self.get_tab_data(widget) if widget is not None else {"type": None, "id": None}
        index = pane.currentIndex() if pane else -1

        self.publish_event(UIEvents.TAB_CHANGED, {
            "tab_index": index,
            "tab_type": tab_data.get("type"),
            "tab_id": tab_data.get("id"),
            "tab_title": pane.tabText(index) if pane and index >= 0 else "",
            "dataset_id": tab_data.get("dataset_id"),
            "chart_id": tab_data.get("chart_id"),
            "note_id": tab_data.get("note_id")
        })

        self._persist_tab_session()

    def get_tab_data(self, widget):
        """Get tab data for a widget."""
        if hasattr(widget, "dataset") and widget.dataset:
            return {
                "type": "dataset",
                "id": widget.dataset.id,
                "dataset_id": widget.dataset.id
            }
        elif hasattr(widget, "chart") and widget.chart:
            return {
                "type": "chart",
                "id": widget.chart.id,
                "chart_id": widget.chart.id
            }
        elif hasattr(widget, "note") and widget.note:
            return {
                "type": "note",
                "id": widget.note.id,
                "note_id": widget.note.id
            }
        else:
            return {
                "type": "other",
                "id": id(widget)
            }

    def on_analysis_completed(self, event_data):
        """Handle analysis completion events."""
        dataset_id = event_data.get("dataset_id")
        # Find and refresh the relevant dataset tab
        for tab_widget in self.tabs.values():
            if hasattr(tab_widget, "dataset") and tab_widget.dataset.id == dataset_id:
                if hasattr(tab_widget, "load_dataset_data"):
                    tab_widget.load_dataset_data()  # Refresh to show new analysis column


# TODO(#220): ensure tab name is updated on item name change
