"""Shared "may we discard unsaved changes?" guard.

Every path that can end with the current project going away -- explicit
Project > Close, File > Exit, the OS window-close button/Cmd+Q, opening a
different project -- needs the same check so none of them can silently
discard edits. This is the single implementation; callers that need it
(CloseProjectCommand, ExitCommand, PandaMainWindow.closeEvent) all go
through it rather than each re-implementing the confirmation dialog.
"""
from pandaplot.models.state import AppState, UnsavedChangesRegistry
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.data_managers.project_manager import ProjectManager


def flush_pending_edits(app_context: AppContext) -> bool:
    """Commit every registered UnsavedChangesSource's pending edit before a
    lifecycle guard reads/acts on AppState.is_modified (see
    WidgetExtension.register_unsaved_changes_source and
    UnsavedChangesRegistry.flush_all for the aggregate success/failure
    contract this delegates to)."""
    return app_context.get_manager(UnsavedChangesRegistry).flush_all()


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
    except Exception as e:  # noqa: BLE001 -- Command-pattern boundary -- any failure (pandas/numpy/scipy/business-logic error) must become CommandResult.FAILURE instead of crashing the app
        ui_controller.show_error_message(
            "Save Failed",
            f"Project '{project_name}' could not be saved:\n{e}\n\n"
            "The application will stay open so these changes aren't lost.",
        )
        return False

    app_state.mark_saved()
    return True


def confirm_discard_unsaved_changes(app_context: AppContext, *, will_autosave: bool = False, offer_save: bool = False) -> bool:
    """Return True if it's fine to proceed (no project loaded, no unsaved
    changes, the autosave/explicit save succeeded, or the user confirmed
    discarding); False if the caller should cancel whatever it was about to
    do.

    `will_autosave` must be True for a caller whose proceeding is followed
    by `app.launch()`'s unconditional `_flush_save_on_quit` (currently
    ExitCommand and PandaMainWindow.closeEvent, the two paths that end the
    process) -- those never actually discard an *already-saved-once*
    project's edits. CloseProjectCommand (the default, project-only close)
    genuinely discards, so it still asks, as does exiting a never-saved
    project (`_flush_save_on_quit` has no file path to write to, so it
    really is discarded).

    For the autosaving case there's nothing to confirm -- proceeding always
    saves and staying leaves the user exactly where they were -- so this
    skips the question and just performs that save synchronously, right
    here, surfacing a dialog only if it actually fails. Doing it here
    (rather than trusting `_flush_save_on_quit` to make good on it later)
    means a disk-full/permission/serialization failure can still cancel the
    shutdown and leave the project (and its unsaved state) intact, instead
    of `_flush_save_on_quit` swallowing it into a log line after the point
    of no return (mid-`aboutToQuit`).

    `offer_save` (for callers like CloseProjectCommand that genuinely
    discard, i.e. `will_autosave=False`, and where there's no background
    flush coming to save the user) adds an explicit "Save and Close" choice
    alongside Discard/Cancel when the project already has a file path to
    save to -- see issue #409. There's no such option for a never-saved
    project (no path to write to without a Save As dialog this guard
    doesn't own), so that case falls back to the plain discard/cancel
    question.
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
    autosaving = will_autosave and bool(file_path)

    if autosaving:
        return _save_now(app_context, app_state, project_name)

    if offer_save and file_path:
        choice = ui_controller.show_save_discard_cancel(
            "Unsaved Changes",
            f"Project '{project_name}' has unsaved changes.\n\n"
            "Do you want to save them before closing?",
        )
        if choice == "save":
            return _save_now(app_context, app_state, project_name)
        return choice == "discard"

    return ui_controller.show_question(
        "Unsaved Changes",
        f"Project '{project_name}' has unsaved changes.\n"
        "Continuing now will discard them.\n\nDo you want to continue?",
    )
