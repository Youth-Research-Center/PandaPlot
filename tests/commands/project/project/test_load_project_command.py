"""Tests for LoadProjectCommand (#209): no success dialog on load, and
opting out of CommandExecutor's generic dirty-tracking hook. Also covers
cleanup() (see Command.cleanup) and surfacing items that
ProjectDataManager.load() silently dropped (issue #288)."""
from unittest.mock import Mock

import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.project.load_project_command import LoadProjectCommand
from pandaplot.models.project.project import Project


def _make_app_context():
    return Mock()


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
    title, message = warning_call.args
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
