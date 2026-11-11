"""Shared "may we discard unsaved changes?" guard.

Every path that can end with the current project going away -- explicit
Project > Close, File > Exit, the OS window-close button/Cmd+Q, opening a
different project -- needs the same check so none of them can silently
discard edits. This is the single implementation; callers that need it
(CloseProjectCommand, ExitCommand, PandaMainWindow.closeEvent) all go
through it rather than each re-implementing the confirmation dialog.
"""
import logging
from pathlib import Path

from pandaplot.models.events import ProjectEvents
from pandaplot.models.state import AppState, UnsavedChangesRegistry
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.autosave.recovery import delete_session_recovery_copy
from pandaplot.services.data_managers.project_manager import ProjectManager
from pandaplot.services.session import SessionPersistenceManager
from pandaplot.utils.examples import is_in_examples_dir

PROJECT_FILE_SUFFIX = ".pplot"


def flush_pending_edits(app_context: AppContext) -> bool:
    """Commit every registered UnsavedChangesSource's pending edit before a
    lifecycle guard reads/acts on AppState.is_modified (see
    WidgetExtension.register_unsaved_changes_source and
    UnsavedChangesRegistry.flush_all for the aggregate success/failure
    contract this delegates to)."""
    return app_context.get_manager(UnsavedChangesRegistry).flush_all()


def remember_session_project(app_context: AppContext, project_path: str | None) -> None:
    """Record ``project_path`` as the project to restore on the next launch.

    A failure to persist is logged as a warning and never raised, since the
    project change itself has already succeeded.

    Args:
        app_context: Application context providing the SessionPersistenceManager.
        project_path: Path of the project now open, or None when it has no file.
    """
    try:
        app_context.get_manager(SessionPersistenceManager).update_project(project_path)
    except Exception:
        logging.getLogger(__name__).warning("Failed to persist last_project_path", exc_info=True)


def _save_now(app_context: AppContext, app_state: AppState, project_name: str) -> bool:
    """Synchronously save `app_state.current_project` to its existing file
    path, surfacing a dialog on failure or if a save is already in flight.
    Shared by the autosave-on-exit branch and the explicit "Save and Close"
    choice below -- both need the same in-flight/failure handling."""
    ui_controller = app_context.get_ui_controller()

    if app_state.is_saving:
        # A SaveProjectCommand (manual or auto-save) is already writing
        # this project's file. ProjectDataManager.save() opens the target
        # in write mode, so writing over it concurrently here could
        # corrupt it. Rather than block the UI waiting for it to finish,
        # just refuse to proceed -- the in-flight save will itself clear
        # is_modified on success, and the user can retry once it's done (a
        # narrow, easily-retried window, not a silent failure).
        ui_controller.show_info_message(
            "Save In Progress",
            f"A save of project '{project_name}' is already in progress.\n"
            "Please wait for it to finish, then try again.",
        )
        return False

    try:
        project_manager = app_context.get_manager(ProjectManager)
        project_manager.save_project(app_state.current_project, app_state.project_file_path)
    except Exception as e:
        logging.getLogger(__name__).exception("Autosave of project '%s' failed", project_name)
        ui_controller.show_error_message(
            "Save Failed",
            f"Couldn't save project '{project_name}'.\n\nThe application will stay open so these changes aren't lost.",
            error=e,
        )
        return False

    app_state.mark_saved()
    return True


def refuse_save_into_examples_dir(app_context: AppContext, save_path: str) -> bool:
    """Warn and return True when ``save_path`` is inside the bundled examples folder.

    Saving there would let later saves (Ctrl+S, auto-save, the save on quit)
    overwrite a bundled example (#607), so every save path is checked here.

    Args:
        app_context: Application context providing the UI controller.
        save_path: The path chosen for the save.

    Returns:
        True if the save must not go ahead.
    """
    if not is_in_examples_dir(save_path):
        return False
    logging.getLogger(__name__).warning("Refusing to save project into the examples directory: '%s'", save_path)
    app_context.get_ui_controller().show_warning_message(
        "Save Project",
        "Projects can't be saved in the bundled examples folder.\n\nChoose a location outside it.",
    )
    return True


def _save_untitled_as(app_context: AppContext, app_state: AppState, project_name: str) -> bool:
    """Ask for a path and synchronously save the untitled current project there.

    Returns True once the project is saved and now has that path (marked
    saved, remembered for the next session, this session's recovery copy
    deleted). Like Ctrl+S Save As it does not add a Recent Projects entry
    (recent-project tracking is #210).
    Returns False, leaving the project untitled and still modified, if the
    path dialog is cancelled, a save is already in flight, or the save fails.
    """
    ui_controller = app_context.get_ui_controller()
    project = app_state.current_project
    if project is None:
        return False

    if app_state.is_saving:
        ui_controller.show_info_message(
            "Save In Progress",
            f"A save of project '{project_name}' is already in progress.\n"
            "Please wait for it to finish, then try again.",
        )
        return False

    chosen = ui_controller.show_save_project_dialog(default_name=f"{project_name}{PROJECT_FILE_SUFFIX}")
    if not chosen:
        return False
    save_path = chosen if Path(chosen).suffix else chosen + PROJECT_FILE_SUFFIX
    if refuse_save_into_examples_dir(app_context, save_path):
        return False

    try:
        app_context.get_manager(ProjectManager).save_project(project, save_path)
    except Exception as e:
        logging.getLogger(__name__).exception("Save As of untitled project '%s' failed", project_name)
        ui_controller.show_error_message("Save Failed", "Couldn't save the project.", error=e)
        return False

    # Only now does the project have a file: setting the path earlier would
    # make a failed or cancelled Save As look like a titled project.
    project.project_file_path = save_path
    app_state.mark_saved()
    remember_session_project(app_context, save_path)
    delete_session_recovery_copy()
    app_context.event_bus.emit(ProjectEvents.PROJECT_SAVED, {"project": project, "file_path": save_path, "previous_path": None})
    return True


def confirm_discard_unsaved_changes(
    app_context: AppContext,
    *,
    will_autosave: bool = False,
    offer_save: bool = False,
    title: str = "Unsaved Changes",
    discard_message: str | None = None,
) -> bool:
    """Return True if it's fine to proceed (no project loaded, no unsaved
    changes, a save succeeded, or the user confirmed discarding); False if
    the caller should cancel whatever it was about to do.

    An untitled project (no file path, e.g. a New project or an opened
    example) with unsaved changes gets a Save As... / Discard / Cancel
    prompt regardless of the other arguments. Save As... asks for a path and
    saves synchronously; cancelling the path dialog or a failed save returns
    False so the project stays open. Discard deletes the project's recovery
    copy (see AutoSaveManager) because nothing is left to recover.

    For a project that has a file path:

    `will_autosave` must be True for a caller whose proceeding is followed
    by `app.launch()`'s unconditional `_flush_save_on_quit` (currently
    ExitCommand and PandaMainWindow.closeEvent, the two paths that end the
    process) -- those never actually discard an already-saved-once
    project's edits, so there is nothing to confirm: this performs that save
    synchronously, right here, surfacing a dialog only if it fails, so a
    disk-full/permission/serialization failure can still cancel the shutdown
    instead of `_flush_save_on_quit` swallowing it after the point of no
    return.

    `offer_save` (for callers like CloseProjectCommand that genuinely
    discard) adds an explicit "Save and Close" choice alongside
    Discard/Cancel -- see issue #409. Without it the question is the plain
    yes/no `title` / `discard_message` (default wording when None), which
    is what opening or creating another project uses.
    """
    if not flush_pending_edits(app_context):
        app_context.get_ui_controller().show_error_message(
            "Unsaved Changes",
            "One or more open notes could not be saved. Save them manually before continuing.",
        )
        return False

    app_state = app_context.get_app_state()
    if not app_state.has_project or not app_state.is_modified:
        return True

    project_name = app_state.current_project.name if app_state.current_project else "Unknown"
    ui_controller = app_context.get_ui_controller()
    file_path = app_state.project_file_path
    if is_in_examples_dir(file_path):
        # A bundled example is never written back to (#607), so it is treated like an untitled project.
        file_path = None

    if not file_path:
        # Never saved: there is no file for _flush_save_on_quit or Save and
        # Close to write to, so the only way to keep the edits is Save As.
        choice = ui_controller.show_save_as_discard_cancel(
            title,
            f"Project '{project_name}' has not been saved to a file yet, and has unsaved changes.\n\n"
            "Do you want to save it with Save As... first? Discarding loses the changes.",
        )
        if choice == "save_as":
            return _save_untitled_as(app_context, app_state, project_name)
        if choice == "discard":
            delete_session_recovery_copy()
            return True
        return False

    if will_autosave:
        return _save_now(app_context, app_state, project_name)

    if offer_save:
        choice = ui_controller.show_save_discard_cancel(
            title,
            f"Project '{project_name}' has unsaved changes.\n\n"
            "Do you want to save them before closing?",
        )
        if choice == "save":
            return _save_now(app_context, app_state, project_name)
        return choice == "discard"

    return ui_controller.show_question(
        title,
        discard_message
        or f"Project '{project_name}' has unsaved changes.\nContinuing now will discard them.\n\nDo you want to continue?",
    )
