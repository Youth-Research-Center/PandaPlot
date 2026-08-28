import logging
import os
import sys

from PySide6.QtWidgets import QApplication

from pandaplot.commands.command_executor import CommandExecutor
from pandaplot.commands.project.project import LoadProjectCommand
from pandaplot.gui.components.tabs.tab_factory import TabFactory
from pandaplot.gui.controllers import UIController
from pandaplot.gui.main_window import PandaMainWindow
from pandaplot.gui.resources.app_icon import create_app_icon
from pandaplot.models.events import EventBus
from pandaplot.models.events.event_types import AppEvents
from pandaplot.models.project.items import Chart, Dataset, Folder, Image, ImageGallery, Note
from pandaplot.models.state import AppContext, AppState
from pandaplot.services.autosave import AutoSaveManager
from pandaplot.services.config import ConfigManager
from pandaplot.services.qtasks import TaskScheduler
from pandaplot.services.session import SessionPersistenceManager
from pandaplot.services.theme import ThemeManager
from pandaplot.storage.chart_data_manager import ChartDataManager
from pandaplot.storage.dataset_data_manager import DatasetDataManager
from pandaplot.storage.folder_data_manager import FolderDataManager
from pandaplot.storage.image_data_manager import ImageDataManager
from pandaplot.storage.image_gallery_data_manager import ImageGalleryDataManager
from pandaplot.storage.item_data_manager_factory import ItemDataManagerFactory
from pandaplot.storage.note_data_manager import NoteDataManager
from pandaplot.storage.project_data_manager import ProjectDataManager
from pandaplot.utils.log import setup_logging


def create_project_data_manager() -> ProjectDataManager:
    """Register item data managers and build the project data manager."""
    factory = ItemDataManagerFactory()
    factory.register("note", Note, NoteDataManager(), "note")
    factory.register("folder", Folder, FolderDataManager(), "folder")
    factory.register("chart", Chart, ChartDataManager(), "chart")
    factory.register("dataset", Dataset, DatasetDataManager(), "dataset")
    factory.register("image", Image, ImageDataManager(), "image")
    factory.register("imagegallery", ImageGallery, ImageGalleryDataManager(), "imagegallery")
    return ProjectDataManager(factory)


def create_tab_factory() -> TabFactory:
    """Register tab loaders and build the TabFactory. Each loader lazily
    imports its tab module so heavy deps (matplotlib via ChartTab, markdown
    via NoteTab) aren't pulled in until that tab type is actually opened."""
    factory = TabFactory()

    def _load_note_tab(app_context, item, parent):
        from pandaplot.gui.components.tabs.note.note_tab import NoteTab
        return NoteTab(app_context=app_context, note=item, parent=parent)

    def _load_chart_tab(app_context, item, parent):
        from pandaplot.gui.components.tabs.chart.chart_tab import ChartTab
        return ChartTab(app_context=app_context, chart=item, parent=parent)

    def _load_dataset_tab(app_context, item, parent):
        from pandaplot.gui.components.tabs.dataset.dataset_tab import DatasetTab
        return DatasetTab(app_context=app_context, dataset=item, parent=parent)

    def _load_image_gallery_tab(app_context, item, parent):
        from pandaplot.gui.components.tabs.image.image_gallery_tab import ImageGalleryTab
        return ImageGalleryTab(app_context=app_context, gallery=item, parent=parent)

    factory.register(Note, _load_note_tab)
    factory.register(Chart, _load_chart_tab)
    factory.register(Dataset, _load_dataset_tab)
    factory.register(ImageGallery, _load_image_gallery_tab)
    return factory


def build_app_context() -> AppContext:
    """Create and return a fully initialized AppContext (no Qt widgets yet)."""
    event_bus = EventBus()
    project_data_manager = create_project_data_manager()
    tab_factory = create_tab_factory()
    app_state = AppState(event_bus)
    config_manager = ConfigManager(event_bus)
    config_manager.load()
    theme_manager = ThemeManager(event_bus, config_manager)
    auto_save_manager = AutoSaveManager(event_bus, config_manager, app_state)
    session_manager = SessionPersistenceManager(config_manager)
    ui_controller = UIController()
    command_executor = CommandExecutor(on_history_changed=lambda: event_bus.emit(AppEvents.HISTORY_CHANGED))
    task_scheduler = TaskScheduler()

    # Create list of managers to pass to AppContext
    managers = [command_executor, ui_controller, config_manager, theme_manager, session_manager, auto_save_manager, task_scheduler, project_data_manager, tab_factory]

    app_context = AppContext(app_state=app_state, event_bus=event_bus, managers=managers)
    # AutoSaveManager needs the AppContext itself (to construct SaveProjectCommand),
    # which doesn't exist yet while the manager list above is being built.
    auto_save_manager.set_app_context(app_context)

    return app_context


def create_qt_application(app_context: AppContext, argv: list[str] | None = None) -> tuple[QApplication, PandaMainWindow]:
    """Instantiate QApplication and the main window.

    Returns (app, main_window)
    """
    if argv is None:
        argv = sys.argv
    app = QApplication(argv)
    app.setWindowIcon(create_app_icon())

    # Kick off the background import warm-up right after QApplication exists
    # (QObject-based signals -- which the worker uses to report completion --
    # are not safe to use before an application instance exists) and before
    # building the window, so it overlaps with theme application and widget
    # construction instead of waiting for all of that to finish first.
    _schedule_import_warmup(app_context)

    # Apply the theme (QApplication-wide palette/stylesheet/font) before any
    # widgets exist. Setting these on a QApplication forces Qt to re-polish
    # every already-constructed widget -- doing it first means new widgets
    # simply inherit the theme instead of paying that repolish cost after
    # the whole window (menu/sidebar/panels/tabs) has already been built.
    theme_mgr = app_context.get_manager(ThemeManager)
    theme_mgr.set_qt_app(app)
    try:
        theme_mgr.apply_current()
    except Exception:
        logging.getLogger(__name__).exception("Failed applying initial theme")

    main_window = PandaMainWindow(app_context)
    app_context.ui_controller.set_parent_widget(main_window)

    # QTimer needs a running Qt event loop, so start auto-save here rather
    # than in build_app_context().
    app_context.get_manager(AutoSaveManager).start()

    return app, main_window


def _warm_up_heavy_imports(progress_callback=None) -> None:
    """Pre-import dependencies that are otherwise lazily loaded on first use
    (running a fit, opening a chart tab, opening a note tab, running signal
    analysis or LOWESS smoothing). Each of those
    imports costs 1+ seconds; without warm-up, that cost is paid synchronously
    on the UI thread the first time the user triggers the feature, which
    looks like a freeze. Runs on a background thread, so import errors here
    must never propagate to the caller -- the feature will just import (and
    freeze, or fail) normally on first real use instead.
    """
    try:
        from markdown import markdown  # noqa: F401
        from matplotlib.backends.backend_qt import NavigationToolbar2QT  # noqa: F401
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg  # noqa: F401
        from matplotlib.figure import Figure  # noqa: F401
        from scipy import signal  # noqa: F401
        from scipy.optimize import curve_fit  # noqa: F401
        from statsmodels.nonparametric.smoothers_lowess import lowess  # noqa: F401
    except Exception:
        logging.getLogger(__name__).exception("Background import warm-up failed (non-fatal)")


def _schedule_import_warmup(app_context: AppContext) -> None:
    """Kick off _warm_up_heavy_imports on a background thread."""
    task_scheduler = app_context.get_manager(TaskScheduler)
    task_scheduler.run_task(_warm_up_heavy_imports)


def _flush_save_on_quit(app_context: AppContext) -> None:
    """Synchronously save the current project (if it already has a file path)
    right before the app exits.

    Auto-save only fires on a timer, so an edit made seconds before the user
    quits (via the window's close button, File > Exit, Cmd+Q, ...) can be
    lost if it hasn't ticked yet. This runs the save directly on the main
    thread instead of through SaveProjectCommand's background-task path, so
    it's guaranteed to finish before the process actually exits rather than
    racing shutdown.
    """
    app_state = app_context.get_app_state()
    if not app_state.has_project:
        return
    project = app_state.current_project
    if project is None:
        return
    file_path = app_state.project_file_path
    if not file_path:
        # Never-saved project: nothing to silently write to.
        return
    try:
        project_data_manager = app_context.get_manager(ProjectDataManager)
        project_data_manager.save(project, file_path)
        logging.getLogger(__name__).info("Flushed project save on quit: %s", file_path)
    except Exception:
        logging.getLogger(__name__).exception("Failed to flush project save on quit")


def restore_last_session(app_context: AppContext, main_window: PandaMainWindow) -> None:
    """Reopen the project (and tabs) that were open at the end of the previous session.

    No-op if no project was remembered, or the remembered file no longer exists.
    """
    session_manager = app_context.get_manager(SessionPersistenceManager)
    last_path = session_manager.last_project_path
    if not last_path or not os.path.isfile(last_path):
        return

    panes_data = session_manager.last_tab_panes
    active_tab_id = session_manager.last_active_tab_id
    splitter_sizes = session_manager.last_splitter_sizes

    def _on_loaded(project) -> None:  # noqa: ANN001 - Project, avoiding import cycle concerns
        main_window.tab_container.restore_tab_session(panes_data, active_tab_id, splitter_sizes)

    command = LoadProjectCommand(app_context, last_path, on_loaded=_on_loaded)
    app_context.get_command_executor().execute_command(command)


def launch(app_context: AppContext) -> int:
    """Launch the GUI event loop.

    Returns the Qt application's exit code.
    """
    if app_context is None:
        raise RuntimeError("AppContext must be provided to launch the application")

    app, main_window = create_qt_application(app_context)
    main_window.show()
    restore_last_session(app_context, main_window)

    # If the app quits while the background import warm-up task is still
    # running, interpreter teardown can race the worker thread's signal
    # emission ("RuntimeError: Signal source has been deleted", printed by
    # Qt but non-fatal). Give it a bounded window to finish before the app
    # actually exits -- a no-op once warm-up has already completed, which is
    # true for the vast majority of real sessions. This is a mitigation, not
    # a guarantee: on a slow/cold-cache import, waitForDone(2000) can still
    # time out and shutdown proceeds regardless, leaving the same race (and
    # its harmless stderr noise) possible -- just less likely.
    task_scheduler = app_context.get_manager(TaskScheduler)
    app.aboutToQuit.connect(lambda: task_scheduler.threadpool.waitForDone(2000))

    # Flush any unsaved edits before the process actually exits, regardless
    # of how the user is quitting (window close, File > Exit, Cmd+Q, ...) --
    # auto-save alone can miss edits made just before quitting.
    app.aboutToQuit.connect(lambda: _flush_save_on_quit(app_context))

    return app.exec()


def main() -> None:
    """CLI entry point for `python -m pandaplot.app`."""
    debug = os.environ.get("PANDAPLOT_DEBUG", "").lower() in ("1", "true", "yes")
    logger = setup_logging(level=logging.DEBUG if debug else logging.INFO)
    logger.info("--------------Starting PandaPlot application--------------")
    app_context = build_app_context()
    sys.exit(launch(app_context))


if __name__ == "__main__":
    main()
    # TODO(#206): fix add/remove series on energy graph
    # TODO(#208): fix transformed columns not saving correctly
    # TODO(#209): misc project open/save/close UX issues (dialogs, saved-state tracking, tab cleanup)
    # TODO(#210): clean state on new project / support multiple projects
    # TODO(#211): multi-threaded processing; improve initial app load time
    # TODO(#212): use mm instead of cm, or make units configurable
    # TODO(#213): copy/paste support
    # TODO(#214): styles/themes: font size, dark theme colors
    # TODO(#215): chart creation/properties panel fixes; scrollable chart area
    # TODO(#216): improve project info display in sidebar
    # TODO(#217): dataset tab: lazy disk loading, sorting/filtering, export
    # TODO(#154): support formulas in dataset tab
    # TODO(#218): encapsulate project data manager inside project manager
