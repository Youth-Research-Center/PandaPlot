"""Tests for AppState's project lifecycle and unsaved-changes (is_modified)
tracking (#209)."""
from pandaplot.models.events import EventBus
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.project import Project
from pandaplot.models.state.app_state import AppState


def _make_state():
    return AppState(EventBus())


def test_is_modified_starts_false():
    state = _make_state()
    assert state.is_modified is False


def test_mark_modified_requires_a_loaded_project():
    state = _make_state()
    state.mark_modified()
    assert state.is_modified is False


def test_mark_modified_sets_the_flag_and_emits_once():
    state = _make_state()
    state.load_project(Project(name="P"))

    events = []
    state.event_bus.subscribe(ProjectEvents.PROJECT_MODIFIED_CHANGED, lambda data: events.append(data))

    state.mark_modified()
    state.mark_modified()  # second call is a no-op, must not re-emit

    assert state.is_modified is True
    assert len(events) == 1
    assert events[0]["is_modified"] is True


def test_mark_saved_clears_the_flag_and_emits_once():
    state = _make_state()
    state.load_project(Project(name="P"))
    state.mark_modified()

    events = []
    state.event_bus.subscribe(ProjectEvents.PROJECT_MODIFIED_CHANGED, lambda data: events.append(data))

    state.mark_saved()
    state.mark_saved()  # second call is a no-op, must not re-emit

    assert state.is_modified is False
    assert len(events) == 1
    assert events[0]["is_modified"] is False


def test_load_project_resets_is_modified():
    state = _make_state()
    state.load_project(Project(name="P"))
    state.mark_modified()
    assert state.is_modified is True

    state.load_project(Project(name="Q"))

    assert state.is_modified is False


def test_close_project_resets_is_modified():
    state = _make_state()
    state.load_project(Project(name="P"))
    state.mark_modified()

    state.close_project()

    assert state.is_modified is False


def test_load_project_emits_when_clearing_a_modified_flag():
    """Regression (PR #235 review): load_project() used to clear
    is_modified via a direct assignment, so a True->False flip on load
    never emitted PROJECT_MODIFIED_CHANGED -- an event-only consumer would
    keep reporting the previous project's dirty state after the switch."""
    state = _make_state()
    state.load_project(Project(name="P"))
    state.mark_modified()

    events = []
    state.event_bus.subscribe(ProjectEvents.PROJECT_MODIFIED_CHANGED, lambda data: events.append(data))

    state.load_project(Project(name="Q"))

    assert len(events) == 1
    assert events[0]["is_modified"] is False


def test_load_project_does_not_emit_when_nothing_was_modified():
    state = _make_state()
    state.load_project(Project(name="P"))

    events = []
    state.event_bus.subscribe(ProjectEvents.PROJECT_MODIFIED_CHANGED, lambda data: events.append(data))

    state.load_project(Project(name="Q"))

    assert events == []


def test_close_project_emits_when_clearing_a_modified_flag():
    """Regression (PR #235 review): same gap as load_project() above, for
    closing a dirty project."""
    state = _make_state()
    state.load_project(Project(name="P"))
    state.mark_modified()

    events = []
    state.event_bus.subscribe(ProjectEvents.PROJECT_MODIFIED_CHANGED, lambda data: events.append(data))

    state.close_project()

    assert len(events) == 1
    assert events[0]["is_modified"] is False


def test_is_saving_starts_false():
    state = _make_state()
    assert state.is_saving is False


def test_begin_save_and_end_save_toggle_is_saving():
    state = _make_state()
    state.begin_save()
    assert state.is_saving is True

    state.end_save()
    assert state.is_saving is False


def test_modification_revision_starts_at_zero():
    state = _make_state()
    assert state.modification_revision == 0


def test_mark_modified_bumps_revision_even_while_already_modified():
    """The flag itself only flips once (see test_mark_modified_sets_the_
    flag_and_emits_once), but the revision counter must still move on every
    call -- SaveProjectCommand relies on it to detect a *newer* edit that
    happened after a save's async completion callback was already in
    flight, even if is_modified was already True beforehand."""
    state = _make_state()
    state.load_project(Project(name="P"))

    state.mark_modified()
    first = state.modification_revision
    state.mark_modified()

    assert state.modification_revision == first + 1


def test_mark_saved_with_stale_revision_does_not_clear_flag():
    """A save that started at revision N must not clear is_modified if a
    later edit bumped the revision before the save's completion callback
    ran -- that edit wasn't part of what was actually written to disk."""
    state = _make_state()
    state.load_project(Project(name="P"))
    state.mark_modified()
    started_revision = state.modification_revision

    state.mark_modified()  # a newer edit landed during the "save"

    state.mark_saved(at_revision=started_revision)

    assert state.is_modified is True


def test_mark_saved_with_current_revision_clears_flag():
    state = _make_state()
    state.load_project(Project(name="P"))
    state.mark_modified()
    started_revision = state.modification_revision

    state.mark_saved(at_revision=started_revision)

    assert state.is_modified is False
