from typing import override

from PySide6.QtCore import Qt
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import QSplitter, QVBoxLayout, QWidget

from pandaplot.commands.project.project.unsaved_changes import confirm_discard_unsaved_changes
from pandaplot.gui.components import CollapsibleSidebar, TabContainer
from pandaplot.gui.components.main_menu.main_menu import MainMenu
from pandaplot.gui.components.sidebar.panels.sidebar_panel_coordinator import (
    SidebarPanelCoordinator,
)
from pandaplot.gui.core.widget_extension import PMainWindow
from pandaplot.gui.resources.app_icon import create_app_icon
from pandaplot.models.events import AppEvents
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.config.config_manager import ConfigManager
from pandaplot.services.theme.theme_manager import ThemeManager


class PandaMainWindow(PMainWindow):
    def __init__(self, app_context: AppContext):
        super().__init__(app_context=app_context)
        # Guards re-entrancy between this flag's two writers: on_app_closing_
        # event (the File > Exit path, which already confirmed via
        # ExitCommand before emitting APP_CLOSING) and closeEvent below (the
        # OS window-close button/Cmd+Q path, which hasn't confirmed yet).
        self._is_closing = False
        self._initialize()

    @override
    def _init_ui(self):
        self.setWindowTitle("PandaPlot")
        self.setWindowIcon(create_app_icon())

        # Set window geometry before showing, but defer showing the window
        # until all widgets are built -- otherwise the OS displays a blank
        # maximized window while the menu/sidebar/panels/tabs are still
        # being constructed on the main thread.
        screen = QScreen.availableGeometry(self.screen())
        self.setGeometry(screen)

        # Create central widget
        central_widget = QWidget()
        central_widget.setObjectName("mainCentralWidget")
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)  # Remove all margins
        main_layout.setSpacing(0)  # Remove spacing between widgets

        self.create_widgets(main_layout)

        self.showMaximized()

    @override
    def _apply_theme(self):
        """Apply theme-specific styling to the main window based on current theme."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        
        # Get theme-appropriate background color
        background_color = palette.get("card_bg", "#F5F5F5")
        
        # Apply background to central widget. Scoped to its object name
        # rather than the bare "QWidget" type selector -- a widget-level
        # style sheet overrides the QApplication-wide one for any property it
        # sets, regardless of selector specificity, so an unscoped "QWidget"
        # rule here would clobber background-color on every descendant
        # QPushButton (Apply, Add to Project, ...) styled by the global
        # [primary="true"] etc. rules, leaving only their border/text colors
        # -- drawn for a colored fill -- visible against a plain background.
        central_widget = self.centralWidget()
        central_widget.setStyleSheet(f"QWidget#mainCentralWidget {{ background-color: {background_color}; }}")
            
        self.logger.debug("Applied theme")
            
    def create_widgets(self, main_layout: QVBoxLayout):
        # Create menu
        self.main_menu = MainMenu(self, self.app_context)
        self.setMenuBar(self.main_menu)

        # Create main horizontal splitter
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # Resolve the persisted dock side for the sidebar (defaults to left)
        sidebar_position = self._get_sidebar_position()

        # Create project manager (side pane) with enhanced styling
        self.sidebar = CollapsibleSidebar(
            self.app_context, self.main_splitter, width=250, position=sidebar_position)
        self.sidebar.position_changed.connect(self.on_sidebar_position_changed)

        # Create main content area with tab container
        self.tab_container = TabContainer(
            app_context=self.app_context, parent=self.main_splitter)
        self.app_context.register_manager(self.tab_container)

        # Order the panes so the sidebar sits on its configured side
        if sidebar_position == "right":
            self.main_splitter.addWidget(self.tab_container)
            self.main_splitter.addWidget(self.sidebar)
            self.main_splitter.setSizes([1000, 250])
        else:
            self.main_splitter.addWidget(self.sidebar)
            self.main_splitter.addWidget(self.tab_container)
            self.main_splitter.setSizes([250, 1000])

        # Register default sidebar panels and wire their conditional visibility
        self.sidebar_panel_coordinator = SidebarPanelCoordinator(self.app_context)
        self.conditional_panel_manager = self.sidebar_panel_coordinator.setup(
            self.sidebar, self.tab_container)

    def _get_sidebar_position(self) -> str:
        """Read the persisted sidebar dock side, defaulting to 'left'."""
        config_manager = self.app_context.get_manager(ConfigManager)
        if config_manager and config_manager.config:
            return config_manager.config.appearance.sidebar_position
        return "left"

    def on_sidebar_position_changed(self, position: str):
        """Reorder the splitter and persist when the sidebar is moved."""
        # Move the sidebar to the appropriate end of the splitter.
        if position == "right":
            self.main_splitter.addWidget(self.sidebar)  # re-adds at the end
        else:
            self.main_splitter.insertWidget(0, self.sidebar)

        # Persist the new dock side so it survives restarts.
        config_manager = self.app_context.get_manager(ConfigManager)
        if config_manager:
            config_manager.update(
                {"appearance": {"sidebar_position": position}}, save=True)

    @override
    def setup_event_subscriptions(self):
        """Set up event subscriptions for the main window."""
        self.subscribe_to_event(AppEvents.APP_CLOSING,
                                self.on_app_closing_event)

        # Keep the title bar showing the current project's name and
        # saved/unsaved state (previously it was always the static
        # "PandaPlot", never reflecting which project -- if any -- was open).
        self.subscribe_to_event(ProjectEvents.PROJECT_LOADED, lambda _data: self._update_window_title())
        self.subscribe_to_event(ProjectEvents.PROJECT_SAVED, lambda _data: self._update_window_title())
        self.subscribe_to_event(ProjectEvents.PROJECT_CLOSED, lambda _data: self._update_window_title())
        self.subscribe_to_event(ProjectEvents.PROJECT_CHANGED, lambda _data: self._update_window_title())
        self.subscribe_to_event(ProjectEvents.PROJECT_MODIFIED_CHANGED, lambda _data: self._update_window_title())

    def _update_window_title(self):
        """Set the title bar to "<project name>[*] - PandaPlot", or plain
        "PandaPlot" when no project is loaded. The trailing "*" mirrors the
        common desktop-app convention for unsaved changes."""
        app_state = self.app_context.get_app_state()
        if not app_state.has_project or not app_state.current_project:
            self.setWindowTitle("PandaPlot")
            return
        marker = "*" if app_state.is_modified else ""
        self.setWindowTitle(f"{app_state.current_project.name}{marker} - PandaPlot")

    @override
    def closeEvent(self, event):
        """Handle the OS window-close button / Cmd+Q.

        Previously this path bypassed every unsaved-changes check: with no
        override here, Qt's default QMainWindow.closeEvent just accepts and
        closes, and File > Exit's ExitCommand (the only other close path)
        didn't check anything either at the time. Route through the same
        confirm_discard_unsaved_changes guard ExitCommand now uses, and
        ignore the event (cancelling the close) if the user declines.
        will_autosave=True for the same reason as ExitCommand: this path
        also ends in app.launch()'s aboutToQuit -> _flush_save_on_quit,
        which unconditionally saves an existing saved project rather than
        discarding it.
        """
        if self._is_closing:
            # Already mid-close via ExitCommand -> APP_CLOSING ->
            # on_app_closing_event -> self.close() -- that path confirmed
            # already, so don't ask a second time.
            event.accept()
            return
        if not confirm_discard_unsaved_changes(self.app_context, will_autosave=True):
            event.ignore()
            return
        event.accept()

    def on_app_closing_event(self, event_data: dict):
        """Handle app closing event from the internal event bus.

        This initiates the normal Qt window close sequence via self.close(),
        which invokes Qt's own default closeEvent handling (there is no
        custom closeEvent override on this class or its PMainWindow base).
        We avoid doing cleanup work here to prevent duplication and to ensure the
        correct event type is passed to Qt's close handling.
        """
        if self._is_closing:
            self.logger.debug(
                "Ignoring app.closing event; close already in progress")
            return

        self.logger.debug(
            "Received app.closing event via event bus; initiating Qt close()")

        # Mark closing state to avoid re-entrancy if event bus emission triggers close()
        self._is_closing = True
        self.logger.info("Application close event triggered")
        try:
            # Close all documents and clean up
            self.logger.debug("Starting application cleanup process")

            # TODO(#221): Implement cleanup logic here
            # we need to ask for saving open modified files/projects
            # this can happen by executing close all tabs command
            # consider moving the logic inside close command
            # we need to cleanup matplotlib charts to avoid memory leaks

            # Log cleanup completion
            self.logger.info("Application cleanup completed successfully")
        except Exception:
            self.logger.exception("Error during cleanup")
            # Force exit even if cleanup fails
            self.logger.warning(
                "Forcing application exit despite cleanup errors")
        finally:
            # close() must run unconditionally, whether cleanup succeeded or
            # raised, and the guard flag must stay True for its full duration
            # since it's the call that could re-enter this handler (e.g. via
            # a synchronous QCloseEvent side effect) -- resetting the flag
            # first would make the re-entrancy guard above a no-op.
            try:
                self.close()
            finally:
                self._is_closing = False

