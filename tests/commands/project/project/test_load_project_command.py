"""Tests for LoadProjectCommand (#209): no success dialog on load, and
opting out of CommandExecutor's generic dirty-tracking hook. Also covers
cleanup() (see Command.cleanup) and surfacing items that
ProjectDataManager.load() silently dropped (issue #288)."""
from unittest.mock import Mock

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.project.load_project_command import LoadProjectCommand
from pandaplot.models.project.project import Project
from pandaplot.utils.error_messages import ErrorDescription, describe_error


def _make_app_context():
    app_context = Mock()
    # An int like production: a Mock revision never equals the one captured at dispatch,
    # so every result would look like the project changed during the load.
    app_context.get_app_state.return_value.modification_revision = 0
    return app_context


def test_marks_project_modified_is_false():
    """A freshly loaded project starts with nothing unsaved -- AppState.
    load_project (called from _on_load_result) sets that directly, so this
    must not be double-counted by CommandExecutor's generic
    on_project_modified hook."""
    command = LoadProjectCommand(_make_app_context(), "/p.pplot")
    assert command.marks_project_modified() is False


def test_on_load_result_does_not_show_a_success_dialog():
    """Regression (#209): loading a project used to pop an "loaded
    successfully" info dialog on every load -- unnecessary interruption for
    a routine, already-visible-in-the-UI action."""
    app_context = _make_app_context()
    command = LoadProjectCommand(app_context, "/p.pplot")

    project = Mock()
    project.name = "P"
    command._on_load_result({"success": True, "project": project, "file_path": "/p.pplot"})

    app_context.get_ui_controller.return_value.show_info_message.assert_not_called()


def test_on_load_result_still_loads_the_project_into_app_state():
    app_context = _make_app_context()
    command = LoadProjectCommand(app_context, "/p.pplot")

    project = Mock()
    project.name = "P"
    command._on_load_result({"success": True, "project": project, "file_path": "/p.pplot"})

    command.app_state.load_project.assert_called_once_with(project)


def test_on_load_result_invokes_the_on_loaded_callback():
    app_context = _make_app_context()
    calls = []
    command = LoadProjectCommand(app_context, "/p.pplot", on_loaded=lambda p: calls.append(p))

    project = Mock()
    project.name = "P"
    project.failed_item_ids = []
    command._on_load_result({"success": True, "project": project, "file_path": "/p.pplot"})

    assert calls == [project]


def test_on_load_result_stamps_the_project_with_the_actual_load_path():
    """Regression (PR #235 review): Project.from_dict deserializes
    project_file_path from the saved project.json's own record of where it
    was saved from. If the .pplot file was since moved or copied, that
    stored value is stale -- it must be overwritten with the path this
    command actually loaded from, or later "already open" comparisons and
    Save would keep targeting the old location."""
    app_context = _make_app_context()
    command = LoadProjectCommand(app_context, "/new/location.pplot")

    project = Mock()
    project.name = "P"
    project.project_file_path = "/old/stale-location.pplot"
    command._on_load_result({"success": True, "project": project, "file_path": "/new/location.pplot"})

    assert project.project_file_path == "/new/location.pplot"


class TestLoadProjectCommandRaceGuard:
    """Regression (PR #235 review): the unsaved-changes confirmation shown
    (if any) before dispatch only covers the state at that moment. The old
    project stays active and editable while the background load runs, so a
    command executed after the user confirms can create new unsaved
    changes that confirmation never saw -- _on_load_result must re-confirm
    before silently discarding those too, rather than always installing
    the loaded project unconditionally."""

    def _dispatch(self, *, project_file_path="/p/current.pplot"):
        app_context, app_state = _make_configured_app_context(
            has_project=True, project_file_path=project_file_path, is_modified=False)
        app_state.modification_revision = 0
        command = LoadProjectCommand(app_context, "/p/other.pplot")
        assert command.execute() is CommandResult.SUCCESS
        return command, app_context, app_state

    def test_reconfirms_when_the_project_changed_during_the_load(self):
        command, app_context, app_state = self._dispatch()
        app_state.modification_revision = 1  # an edit landed while loading
        app_state.is_modified = True
        app_context.get_ui_controller.return_value.show_question.return_value = True

        project = Mock()
        project.name = "New"
        project.failed_item_ids = []
        command._on_load_result({"success": True, "project": project, "file_path": "/p/other.pplot"})

        app_context.get_ui_controller.return_value.show_question.assert_called_once()
        app_state.load_project.assert_called_once_with(project)

    def test_discards_the_load_when_the_user_declines_reconfirmation(self):
        command, app_context, app_state = self._dispatch()
        app_state.modification_revision = 1
        app_state.is_modified = True
        app_context.get_ui_controller.return_value.show_question.return_value = False

        project = Mock()
        project.name = "New"
        command._on_load_result({"success": True, "project": project, "file_path": "/p/other.pplot"})

        app_state.load_project.assert_not_called()
        assert command.loaded_project is None

    def test_does_not_reconfirm_when_nothing_changed_during_the_load(self):
        command, app_context, app_state = self._dispatch()
        # modification_revision unchanged from dispatch time.

        project = Mock()
        project.name = "New"
        project.failed_item_ids = []
        command._on_load_result({"success": True, "project": project, "file_path": "/p/other.pplot"})

        app_context.get_ui_controller.return_value.show_question.assert_not_called()
        app_state.load_project.assert_called_once_with(project)

    def test_reconfirms_for_a_note_edit_flushed_during_the_load(self, monkeypatch):
        """Regression (PR #352 review): a note edit typed while the load ran
        in the background can still be inside its 2s debounce window when
        this callback fires -- modification_revision would read unchanged
        (the EditNoteCommand hasn't run yet) unless it's flushed here too,
        the same way LoadProjectCommand.execute()'s own pre-dispatch check
        needed flushing. Without this, the callback would silently install
        the loaded project over that not-yet-committed edit."""
        command, app_context, app_state = self._dispatch()

        def fake_flush(ctx):
            app_state.modification_revision = 1  # simulates the note's EditNoteCommand landing
            app_state.is_modified = True
            return True

        monkeypatch.setattr(
            "pandaplot.commands.project.project.load_project_command.flush_pending_edits",
            fake_flush,
        )
        app_context.get_ui_controller.return_value.show_question.return_value = True

        project = Mock()
        project.name = "New"
        project.failed_item_ids = []
        command._on_load_result({"success": True, "project": project, "file_path": "/p/other.pplot"})

        app_context.get_ui_controller.return_value.show_question.assert_called_once()
        app_state.load_project.assert_called_once_with(project)

    def test_discards_the_load_and_reports_an_error_when_the_flush_fails_during_the_load(self, monkeypatch):
        """A flush failure here means a note edit is still stuck unsaved --
        must not install the loaded project over it, and must say why
        instead of silently discarding (same as declining reconfirmation,
        but the user was never asked)."""
        command, app_context, app_state = self._dispatch()
        monkeypatch.setattr(
            "pandaplot.commands.project.project.load_project_command.flush_pending_edits",
            lambda ctx: False,
        )

        project = Mock()
        project.name = "New"
        command._on_load_result({"success": True, "project": project, "file_path": "/p/other.pplot"})

        app_state.load_project.assert_not_called()
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
        app_context.get_ui_controller.return_value.show_question.assert_not_called()


class TestLateEditOfAnUntitledProject:
    """Review (#634): an untitled project edited while another project loads must be offered Save As, not a yes/no question."""

    def _dispatch_untitled(self):
        app_context, app_state = _make_configured_app_context(has_project=True, project_file_path=None, is_modified=False)
        app_state.modification_revision = 0
        command = LoadProjectCommand(app_context, "/p/other.pplot")
        assert command.execute() is CommandResult.SUCCESS
        app_state.modification_revision = 1  # an edit landed while loading
        app_state.is_modified = True
        project = Mock()
        project.name = "New"
        project.failed_item_ids = []
        return command, app_context, app_state, project

    @pytest.mark.parametrize(("choice", "loads"), [("discard", True), ("cancel", False)])
    def test_offers_save_as_discard_cancel(self, choice, *, loads):
        command, app_context, app_state, project = self._dispatch_untitled()
        ui = app_context.get_ui_controller.return_value
        ui.show_save_as_discard_cancel.return_value = choice

        command._on_load_result({"success": True, "project": project, "file_path": "/p/other.pplot"})

        ui.show_save_as_discard_cancel.assert_called_once()
        ui.show_question.assert_not_called()
        assert app_state.load_project.called is loads

    def test_titled_project_keeps_the_additional_changes_question(self):
        app_context, app_state = _make_configured_app_context(has_project=True, project_file_path="/p/current.pplot", is_modified=False)
        app_state.modification_revision = 0
        command = LoadProjectCommand(app_context, "/p/other.pplot")
        assert command.execute() is CommandResult.SUCCESS
        app_state.modification_revision = 1
        app_state.is_modified = True
        ui = app_context.get_ui_controller.return_value
        ui.show_question.return_value = True
        project = Mock()
        project.name = "New"
        project.failed_item_ids = []

        command._on_load_result({"success": True, "project": project, "file_path": "/p/other.pplot"})

        ui.show_save_as_discard_cancel.assert_not_called()
        assert "changed while the new one was loading" in ui.show_question.call_args.args[1]
        app_state.load_project.assert_called_once_with(project)

def _make_configured_app_context(*, has_project=False, project_file_path=None, is_modified=False):
    """Like _make_app_context, but with an app_state whose has_project/
    project_file_path/is_modified are explicitly controllable -- needed to
    exercise execute()'s centralized already-open/unsaved-changes guards."""
    app_context = Mock()
    app_state = Mock()
    app_state.has_project = has_project
    app_state.project_file_path = project_file_path
    app_state.is_modified = is_modified
    app_context.get_app_state.return_value = app_state
    return app_context, app_state


class TestLoadProjectCommandGuards:
    """Regression (PR #235 review): these checks used to live only in
    OpenProjectCommand's file-dialog flow. The welcome tab's recent/example
    project handlers and the main menu's Examples dialog all call
    LoadProjectCommand directly and had no such protection -- they now get
    it for free since the guard lives in the one place every caller goes
    through."""

    def test_execute_skips_reload_when_the_same_file_is_already_open(self):
        app_context, _ = _make_configured_app_context(has_project=True, project_file_path="/p/current.pplot")
        command = LoadProjectCommand(app_context, "/p/current.pplot")

        assert command.execute() is CommandResult.NOOP
        command.task_scheduler.run_task.assert_not_called()

    def test_execute_treats_equivalent_paths_as_the_same_file(self):
        """Comparison is canonical (os.path.realpath), so a differently-
        spelled path to the same file (relative segments here) is still
        recognized as already open."""
        app_context, _ = _make_configured_app_context(has_project=True, project_file_path="/p/current.pplot")
        command = LoadProjectCommand(app_context, "/p/sub/../current.pplot")

        assert command.execute() is CommandResult.NOOP
        command.task_scheduler.run_task.assert_not_called()

    def test_execute_proceeds_without_asking_when_unmodified(self):
        app_context, _ = _make_configured_app_context(
            has_project=True, project_file_path="/p/current.pplot", is_modified=False)
        command = LoadProjectCommand(app_context, "/p/other.pplot")

        assert command.execute() is CommandResult.SUCCESS
        command.ui_controller.show_question.assert_not_called()
        command.task_scheduler.run_task.assert_called_once()

    def test_execute_asks_for_confirmation_when_modified(self):
        app_context, _ = _make_configured_app_context(
            has_project=True, project_file_path="/p/current.pplot", is_modified=True)
        command = LoadProjectCommand(app_context, "/p/other.pplot")
        command.ui_controller.show_question.return_value = True

        assert command.execute() is CommandResult.SUCCESS
        command.ui_controller.show_question.assert_called_once()
        command.task_scheduler.run_task.assert_called_once()

    def test_execute_aborts_when_user_declines_confirmation(self):
        app_context, _ = _make_configured_app_context(
            has_project=True, project_file_path="/p/current.pplot", is_modified=True)
        command = LoadProjectCommand(app_context, "/p/other.pplot")
        command.ui_controller.show_question.return_value = False

        assert command.execute() is CommandResult.NOOP
        command.task_scheduler.run_task.assert_not_called()

    def test_execute_proceeds_without_asking_when_no_project_loaded(self):
        app_context, _ = _make_configured_app_context(has_project=False)
        command = LoadProjectCommand(app_context, "/p/new.pplot")

        assert command.execute() is CommandResult.SUCCESS
        command.ui_controller.show_question.assert_not_called()
        command.task_scheduler.run_task.assert_called_once()

    def test_execute_flushes_pending_note_edits_before_checking_modified(self, monkeypatch):
        """Regression (#318): a note's debounced edit must be flushed (and so
        reflected in is_modified) before this command decides whether
        loading a different project would discard anything."""
        calls = []
        monkeypatch.setattr(
            "pandaplot.commands.project.project.load_project_command.flush_pending_edits",
            lambda ctx: calls.append(ctx) or True,
        )
        app_context, _ = _make_configured_app_context(
            has_project=True, project_file_path="/p/current.pplot", is_modified=False)
        command = LoadProjectCommand(app_context, "/p/other.pplot")

        assert command.execute() is CommandResult.SUCCESS
        assert calls == [app_context]
        command.ui_controller.show_question.assert_not_called()

    def test_execute_does_not_flush_when_reload_is_skipped_as_already_open(self, monkeypatch):
        """No point flushing (or reading is_modified at all) when the load
        is about to be skipped as a no-op."""
        calls = []
        monkeypatch.setattr(
            "pandaplot.commands.project.project.load_project_command.flush_pending_edits",
            lambda ctx: calls.append(ctx) or True,
        )
        app_context, _ = _make_configured_app_context(has_project=True, project_file_path="/p/current.pplot")
        command = LoadProjectCommand(app_context, "/p/current.pplot")

        assert command.execute() is CommandResult.NOOP
        assert calls == []

    def test_execute_fails_and_reports_an_error_when_flush_fails(self, monkeypatch):
        """Regression (PR #352 review): a flush failure means a note edit is
        still stuck unsaved -- must refuse to load a different project
        (which would discard the current one) instead of silently
        proceeding with a stale is_modified reading."""
        monkeypatch.setattr(
            "pandaplot.commands.project.project.load_project_command.flush_pending_edits",
            lambda ctx: False,
        )
        app_context, _ = _make_configured_app_context(
            has_project=True, project_file_path="/p/current.pplot", is_modified=False)
        command = LoadProjectCommand(app_context, "/p/other.pplot")

        assert command.execute() is CommandResult.FAILURE
        command.ui_controller.show_error_message.assert_called_once()
        command.task_scheduler.run_task.assert_not_called()


@pytest.fixture
def env():
    app_state = Mock()
    app_state.has_project = True
    app_state.modification_revision = 0
    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value = Mock()
    app_context.get_task_scheduler.return_value = Mock()
    app_context.get_manager.return_value = Mock()
    return app_context


def test_undo_restores_the_previous_projects_dirty_state():
    """Regression (PR #235 review): load_project() (called by undo() to
    restore the previous project) unconditionally clears is_modified, since
    it assumes a fresh disk load. Undoing a LoadProjectCommand instead
    restores a project that may still have had unsaved changes -- those
    must survive, not be silently reported as saved."""
    from pandaplot.models.events import EventBus
    from pandaplot.models.state.app_state import AppState

    app_state = AppState(EventBus())
    previous_project = Mock()
    previous_project.name = "Previous"
    previous_project.project_file_path = "/p/current.pplot"
    app_state.load_project(previous_project)
    app_state.mark_modified()

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value.show_question.return_value = True

    command = LoadProjectCommand(app_context, "/p/other.pplot")
    assert command.execute() is CommandResult.SUCCESS

    assert command.undo() is CommandResult.SUCCESS
    assert app_state.current_project is previous_project
    assert app_state.is_modified is True


def test_undo_flushes_pending_note_edits_before_restoring_the_previous_project(monkeypatch):
    """Regression (PR #352 review): a note edited in the currently-installed
    project, right before the user hits Undo, can still be mid-debounce --
    no EditNoteCommand has run yet to invalidate anything, so nothing else
    protects this swap. Must flush first, same as execute()."""
    from pandaplot.models.events import EventBus
    from pandaplot.models.state.app_state import AppState

    app_state = AppState(EventBus())
    previous_project = Mock()
    previous_project.name = "Previous"
    previous_project.project_file_path = "/p/current.pplot"
    app_state.load_project(previous_project)

    app_context = Mock()
    app_context.get_app_state.return_value = app_state
    app_context.get_ui_controller.return_value.show_question.return_value = True

    command = LoadProjectCommand(app_context, "/p/other.pplot")
    assert command.execute() is CommandResult.SUCCESS

    calls = []
    monkeypatch.setattr(
        "pandaplot.commands.project.project.load_project_command.flush_pending_edits",
        lambda ctx: calls.append(ctx) or True,
    )

    assert command.undo() is CommandResult.SUCCESS
    assert calls == [app_context]
    assert app_state.current_project is previous_project


def test_redo_restores_the_loaded_projects_dirty_state():
    """Regression (PR #352 review): a note edited in the just-loaded project
    (flushed during undo(), or dirtied by any other command) must not have
    that dirty state silently discarded when redo()'s cached fast path
    reinstalls this exact project via load_project(), which unconditionally
    reports whatever it loads as clean."""
    from pandaplot.models.events import EventBus
    from pandaplot.models.state.app_state import AppState

    app_state = AppState(EventBus())
    previous_project = Mock()
    previous_project.name = "Previous"
    app_state.load_project(previous_project)

    app_context = Mock()
    app_context.get_app_state.return_value = app_state

    command = LoadProjectCommand(app_context, "/p/other.pplot")
    loaded_project = Mock()
    loaded_project.name = "Loaded"
    command.previous_project = previous_project
    command.loaded_project = loaded_project
    app_state.load_project(loaded_project)  # simulate the load having installed it

    # Simulate a note edit dirtying the just-loaded project.
    app_state.mark_modified()

    assert command.undo() is CommandResult.SUCCESS
    assert app_state.current_project is previous_project

    assert command.redo() is CommandResult.SUCCESS
    assert app_state.current_project is loaded_project
    assert app_state.is_modified is True


def test_undo_restores_a_dirty_state_that_arose_after_a_prior_redo():
    """previous_was_modified must be refreshed on every redo(), not just
    captured once at the original execute() -- otherwise an edit made to
    the previous project during the window between an undo() and a later
    redo() gets silently forgotten the next time undo() runs again."""
    from pandaplot.models.events import EventBus
    from pandaplot.models.state.app_state import AppState

    app_state = AppState(EventBus())
    previous_project = Mock()
    previous_project.name = "Previous"
    app_state.load_project(previous_project)

    app_context = Mock()
    app_context.get_app_state.return_value = app_state

    command = LoadProjectCommand(app_context, "/p/other.pplot")
    loaded_project = Mock()
    loaded_project.name = "Loaded"
    command.previous_project = previous_project
    command.loaded_project = loaded_project
    app_state.load_project(loaded_project)

    assert command.undo() is CommandResult.SUCCESS
    assert app_state.current_project is previous_project

    # Dirty the previous project while it's active, in the window between
    # this undo() and the redo() below.
    app_state.mark_modified()

    assert command.redo() is CommandResult.SUCCESS
    assert command.undo() is CommandResult.SUCCESS
    assert app_state.current_project is previous_project
    assert app_state.is_modified is True


def test_undo_aborts_and_reports_an_error_when_flush_fails(monkeypatch):
    """Regression (PR #352 review): must return ABORTED, not FAILURE --
    CommandExecutor.undo() moves the command to the redo stack regardless
    of result, so FAILURE here would record this load as undone (and
    installable via a later Redo) even though nothing actually changed."""
    app_context = Mock()
    command = LoadProjectCommand(app_context, "/p/other.pplot")
    command.previous_project = Mock()
    monkeypatch.setattr(
        "pandaplot.commands.project.project.load_project_command.flush_pending_edits",
        lambda ctx: False,
    )

    assert command.undo() is CommandResult.ABORTED
    command.ui_controller.show_error_message.assert_called_once()
    command.app_state.load_project.assert_not_called()


def test_redo_flushes_pending_note_edits_before_restoring_the_loaded_project(monkeypatch):
    """Regression (PR #352 review): same race as undo(), but on the
    cached-loaded_project fast path -- a note edited in the project that's
    about to be replaced (by redoing the load) must be flushed first."""
    app_context = _make_app_context()
    command = LoadProjectCommand(app_context, "/p/other.pplot")
    command.loaded_project = Mock()

    calls = []
    monkeypatch.setattr(
        "pandaplot.commands.project.project.load_project_command.flush_pending_edits",
        lambda ctx: calls.append(ctx) or True,
    )

    assert command.redo() is CommandResult.SUCCESS
    assert calls == [app_context]
    app_context.get_app_state.return_value.load_project.assert_called_once_with(command.loaded_project)


def test_redo_aborts_and_reports_an_error_when_flush_fails(monkeypatch):
    """Regression (PR #352 review): must return ABORTED, not FAILURE -- see
    the matching undo() test above."""
    app_context = _make_app_context()
    command = LoadProjectCommand(app_context, "/p/other.pplot")
    command.loaded_project = Mock()
    monkeypatch.setattr(
        "pandaplot.commands.project.project.load_project_command.flush_pending_edits",
        lambda ctx: False,
    )

    assert command.redo() is CommandResult.ABORTED
    app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
    app_context.get_app_state.return_value.load_project.assert_not_called()


def test_cleanup_releases_the_previous_and_loaded_project_references(env):
    command = LoadProjectCommand(env, "/some/path.pplot")
    command.previous_project = Mock()
    command.loaded_project = Mock()

    command.cleanup()

    assert command.previous_project is None
    assert command.loaded_project is None


def test_on_load_result_warns_when_items_failed_to_load(env):
    command = LoadProjectCommand(env, "/some/path.pplot")
    project = Project(name="My Project")
    project.failed_item_ids = ["ds-1", "chart-2"]

    command._on_load_result({
        "success": True, "error": None, "project": project, "file_path": "/some/path.pplot",
    })

    ui_controller = env.get_ui_controller.return_value
    warning_call = ui_controller.show_warning_message.call_args
    assert warning_call is not None
    _title, message = warning_call.args
    assert "ds-1" in message
    assert "chart-2" in message


def test_on_load_result_does_not_warn_when_no_items_failed(env):
    command = LoadProjectCommand(env, "/some/path.pplot")
    project = Project(name="My Project")

    command._on_load_result({
        "success": True, "error": None, "project": project, "file_path": "/some/path.pplot",
    })

    ui_controller = env.get_ui_controller.return_value
    ui_controller.show_warning_message.assert_not_called()


class TestLoadFailureMessages:
    """The load worker sends a plain-language ErrorDescription, never raw exception text (#595)."""

    def test_garbage_project_file_gives_a_described_failure(self, tmp_path):
        from pandaplot.services.data_managers.project_manager import ProjectManager
        from pandaplot.storage.project_data_manager import ProjectDataManager

        bad_file = tmp_path / "broken.pplot"
        bad_file.write_text("this is not a zip archive", encoding="utf-8")
        app_context = _make_app_context()
        app_context.get_manager.return_value = ProjectManager(ProjectDataManager(Mock()))
        command = LoadProjectCommand(app_context, str(bad_file))

        result = command._load_project_task(None)

        assert result["success"] is False
        description = result["error_description"]
        assert isinstance(description, ErrorDescription)
        assert description.reason == "This file is damaged or is not the type its name suggests."
        assert "BadZipFile" in description.details

    def test_failed_load_dialog_shows_the_description_not_the_raw_text(self):
        app_context = _make_app_context()
        command = LoadProjectCommand(app_context, "/p.pplot")
        description = describe_error(FileNotFoundError("/p.pplot"))

        command._on_load_result({"success": False, "error": "Error during project load: raw", "error_description": description})

        command.ui_controller.show_error_message.assert_called_once_with(
            "Load Failed", "Couldn't open the project.", error=description
        )

    def test_non_exception_failure_keeps_its_plain_reason(self):
        command = LoadProjectCommand(_make_app_context(), "")

        result = command._load_project_task(None)

        assert result["success"] is False
        assert result["error_description"].reason == "No file was chosen to open."
        assert result["error_description"].details == ""

    def test_worker_error_signal_passes_the_exception(self):
        command = LoadProjectCommand(_make_app_context(), "/p.pplot")
        error = PermissionError("denied")

        command._on_load_error((PermissionError, error, "traceback"))

        command.ui_controller.show_error_message.assert_called_once_with(
            "Load Project Error", "Couldn't open the project.", error=error
        )


class TestAsUntitledCopy:
    """Opening a bundled example must not tie the project to the example's
    file, so Save asks for a location instead of overwriting it (#607)."""

    def test_defaults_to_a_normal_load(self):
        assert LoadProjectCommand(_make_app_context(), "/p.pplot").as_untitled_copy is False

    def test_loaded_project_has_no_file_path_and_session_records_no_project(self, env):
        command = LoadProjectCommand(env, "/examples/demo.pplot", as_untitled_copy=True)
        project = Mock()
        project.name = "Demo"
        project.project_file_path = "/examples/demo.pplot"
        project.failed_item_ids = []

        command._on_load_result({"success": True, "project": project, "file_path": "/examples/demo.pplot"})

        assert project.project_file_path is None
        assert project.name == "Demo"
        command.app_state.load_project.assert_called_once_with(project)
        env.get_manager.return_value.update_project.assert_called_once_with(None)

    def test_normal_load_still_records_path_and_session(self, env):
        command = LoadProjectCommand(env, "/p/a.pplot")
        project = Mock()
        project.failed_item_ids = []

        command._on_load_result({"success": True, "project": project, "file_path": "/p/a.pplot"})

        assert project.project_file_path == "/p/a.pplot"
        env.get_manager.return_value.update_project.assert_called_once_with("/p/a.pplot")

    def test_skips_the_already_open_shortcut(self):
        app_context, _ = _make_configured_app_context(has_project=True, project_file_path="/p/demo.pplot")
        command = LoadProjectCommand(app_context, "/p/demo.pplot", as_untitled_copy=True)

        assert command.execute() is CommandResult.SUCCESS
        command.task_scheduler.run_task.assert_called_once()

    def test_undo_and_redo_swap_projects_and_untitled_copy_stays_clean(self):
        from pandaplot.models.events import EventBus
        from pandaplot.models.state.app_state import AppState

        app_state = AppState(EventBus())
        previous = Mock()
        previous.name = "Previous"
        previous.project_file_path = "/p/current.pplot"
        app_state.load_project(previous)

        app_context = Mock()
        app_context.get_app_state.return_value = app_state
        command = LoadProjectCommand(app_context, "/examples/demo.pplot", as_untitled_copy=True)
        assert command.execute() is CommandResult.SUCCESS

        copy = Mock()
        copy.name = "Demo"
        copy.project_file_path = "/examples/demo.pplot"
        copy.failed_item_ids = []
        command._on_load_result({"success": True, "project": copy, "file_path": "/examples/demo.pplot"})
        assert app_state.current_project is copy
        assert app_state.project_file_path is None
        assert not app_state.is_modified

        assert command.undo() is CommandResult.SUCCESS
        assert app_state.current_project is previous
        assert command.redo() is CommandResult.SUCCESS
        assert app_state.current_project is copy
        assert app_state.project_file_path is None

    @staticmethod
    def _open_then_undo(command_path: str, *, as_untitled_copy: bool) -> tuple[LoadProjectCommand, Mock, Mock, Mock]:
        """Open ``command_path``, then undo it, returning the pieces the redo tests need."""
        from pandaplot.models.events import EventBus
        from pandaplot.models.state.app_state import AppState

        app_state = AppState(EventBus())
        previous = Mock()
        previous.name = "Previous"
        previous.project_file_path = "/p/current.pplot"
        app_state.load_project(previous)

        session_manager = Mock()
        app_context = Mock()
        app_context.get_app_state.return_value = app_state
        app_context.get_manager.return_value = session_manager
        command = LoadProjectCommand(app_context, command_path, as_untitled_copy=as_untitled_copy)
        assert command.execute() is CommandResult.SUCCESS

        loaded = Mock()
        loaded.name = "Loaded"
        loaded.project_file_path = command_path
        loaded.failed_item_ids = []
        command._on_load_result({"success": True, "project": loaded, "file_path": command_path})

        assert command.undo() is CommandResult.SUCCESS
        return command, loaded, previous, session_manager

    def test_cached_redo_of_an_untitled_copy_records_no_project_in_the_session(self):
        """Regression (PR #616 review): open an example, undo, Save the restored
        project (which records its path in the session without clearing redo
        history), then redo. The session must go back to "no project" instead of
        keeping the replaced project's path, which the next launch would reopen."""
        command, loaded, previous, session_manager = self._open_then_undo("/examples/demo.pplot", as_untitled_copy=True)
        session_manager.update_project.reset_mock()

        assert command.redo() is CommandResult.SUCCESS

        assert command.app_state.current_project is loaded
        session_manager.update_project.assert_called_once_with(None)
        assert previous.project_file_path == "/p/current.pplot"

    def test_cached_redo_records_the_path_the_loaded_project_has_since_been_saved_to(self):
        command, loaded, _, session_manager = self._open_then_undo("/examples/demo.pplot", as_untitled_copy=True)
        loaded.project_file_path = "/saved/copy.pplot"
        session_manager.update_project.reset_mock()

        assert command.redo() is CommandResult.SUCCESS

        session_manager.update_project.assert_called_once_with("/saved/copy.pplot")

    def test_cached_redo_of_a_normal_load_records_its_path_in_the_session(self):
        command, _, _, session_manager = self._open_then_undo("/p/a.pplot", as_untitled_copy=False)
        session_manager.update_project.reset_mock()

        assert command.redo() is CommandResult.SUCCESS

        session_manager.update_project.assert_called_once_with("/p/a.pplot")


class TestBundledExamplesAlwaysOpenAsUntitledCopy:
    """A file inside the bundled examples directory opens as an untitled copy
    however it was reached (File > Open, recent projects, session restore)."""

    @pytest.fixture
    def examples_dir(self, tmp_path, monkeypatch):
        directory = tmp_path / "examples"
        directory.mkdir()
        monkeypatch.setattr("pandaplot.utils.examples.get_examples_dir", lambda: directory)
        return directory

    def test_path_inside_examples_dir_is_an_untitled_copy_without_the_flag(self, env, examples_dir):
        path = str(examples_dir / "demo.pplot")
        command = LoadProjectCommand(env, path)
        assert command.as_untitled_copy is True

        project = Mock()
        project.failed_item_ids = []
        command._on_load_result({"success": True, "project": project, "file_path": path})

        assert project.project_file_path is None
        env.get_manager.return_value.update_project.assert_called_once_with(None)

    def test_dotdot_path_that_resolves_into_examples_dir_is_detected(self, env, examples_dir):
        (examples_dir / "sub").mkdir()
        assert LoadProjectCommand(env, str(examples_dir / "sub" / ".." / "demo.pplot")).as_untitled_copy is True

    def test_path_outside_examples_dir_is_unchanged(self, env, examples_dir, tmp_path):
        path = str(tmp_path / "mine.pplot")
        command = LoadProjectCommand(env, path)
        assert command.as_untitled_copy is False

        project = Mock()
        project.failed_item_ids = []
        command._on_load_result({"success": True, "project": project, "file_path": path})

        assert project.project_file_path == path
        env.get_manager.return_value.update_project.assert_called_once_with(path)

    def test_sibling_directory_with_the_same_prefix_is_not_an_example(self, env, examples_dir):
        assert LoadProjectCommand(env, str(examples_dir) + "-other/demo.pplot").as_untitled_copy is False


class TestUndoRestoresSessionProject:
    """Undoing a load must put the session back on the previous project, or the
    next launch reopens the project the user just undid."""

    def test_undo_of_a_normal_load_records_the_previous_projects_path(self):
        _, _, _, session_manager = TestAsUntitledCopy._open_then_undo("/p/a.pplot", as_untitled_copy=False)

        session_manager.update_project.assert_called_with("/p/current.pplot")
        assert session_manager.update_project.call_args_list[-2].args == ("/p/a.pplot",)

    def test_undo_of_an_untitled_copy_load_records_the_previous_projects_path(self):
        _, _, _, session_manager = TestAsUntitledCopy._open_then_undo("/examples/demo.pplot", as_untitled_copy=True)

        assert [call.args for call in session_manager.update_project.call_args_list] == [(None,), ("/p/current.pplot",)]

    def test_undo_with_no_previous_project_records_no_project(self):
        from pandaplot.models.events import EventBus
        from pandaplot.models.state.app_state import AppState

        app_state = AppState(EventBus())
        session_manager = Mock()
        app_context = Mock()
        app_context.get_app_state.return_value = app_state
        app_context.get_manager.return_value = session_manager
        command = LoadProjectCommand(app_context, "/p/a.pplot")
        assert command.execute() is CommandResult.SUCCESS
        loaded = Mock()
        loaded.failed_item_ids = []
        command._on_load_result({"success": True, "project": loaded, "file_path": "/p/a.pplot"})

        assert command.undo() is CommandResult.SUCCESS

        session_manager.update_project.assert_called_with(None)
        assert not app_state.has_project


class TestLoadProjectCommandUntitledProject:
    """Opening another project over an edited untitled project offers Save As... (#629)."""

    def _context(self, choice):
        app_context, app_state = _make_configured_app_context(has_project=True, project_file_path=None, is_modified=True)
        app_state.current_project.name = "Untitled"
        ui_controller = app_context.get_ui_controller.return_value
        ui_controller.show_save_as_discard_cancel.return_value = choice
        return app_context, app_state, ui_controller

    def test_offers_save_as_instead_of_the_plain_question(self):
        app_context, _app_state, ui_controller = self._context("discard")
        command = LoadProjectCommand(app_context, "/p/other.pplot")

        assert command.execute() is CommandResult.SUCCESS
        ui_controller.show_save_as_discard_cancel.assert_called_once()
        ui_controller.show_question.assert_not_called()
        command.task_scheduler.run_task.assert_called_once()

    def test_cancel_keeps_the_current_project_and_loads_nothing(self):
        app_context, _app_state, _ui_controller = self._context("cancel")
        command = LoadProjectCommand(app_context, "/p/other.pplot")

        assert command.execute() is CommandResult.NOOP
        command.task_scheduler.run_task.assert_not_called()
