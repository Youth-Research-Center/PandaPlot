"""SearchPanel keeps its results live when notes are added, removed or renamed."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from pandaplot.gui.components.sidebar.search.search_panel import _ROLE_NOTE_ID, SearchPanel
from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project import Project
from pandaplot.models.project.items import Note

# Sidebar panels draw a title icon from these design tokens, so a mocked theme manager must provide them.
ICON_TOKENS = {"text_primary": "#1C1E26", "text_muted": "#6B7280", "accent_icon_active": "#404BAC", "text_disabled": "#AEB2BC"}


@pytest.fixture
def search_setup(qtbot):
    project = Project(name="Search refresh")
    alpha = Note(name="Alpha", content="needle in here")
    beta = Note(name="Beta needle", content="nothing")
    project.add_item(alpha)
    project.add_item(beta)
    app_state = SimpleNamespace(has_project=True, current_project=project)
    context = Mock()
    context.event_bus = EventBus()
    context.get_app_state.return_value = app_state
    context.get_manager.return_value.get_surface_palette.return_value = {}
    context.get_manager.return_value.get_design_tokens.return_value = dict(ICON_TOKENS)
    panel = SearchPanel(context)
    qtbot.addWidget(panel)
    panel.search_input.setText("needle")
    panel._debounce.stop()  # only an event may schedule the next refresh
    panel.run_search()
    assert panel.results.topLevelItemCount() == 2
    return panel, context.event_bus, project, alpha, beta


def _note_ids(panel):
    return {panel.results.topLevelItem(i).data(0, _ROLE_NOTE_ID) for i in range(panel.results.topLevelItemCount())}


def test_removed_note_drops_out_of_results(qtbot, search_setup):
    panel, bus, project, alpha, beta = search_setup
    project.remove_item(alpha)
    bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {"project": project, "item_id": alpha.id, "item_type": "note"})
    qtbot.waitUntil(lambda: panel.results.topLevelItemCount() == 1, timeout=2000)
    assert _note_ids(panel) == {beta.id}


def test_renamed_note_title_match_refreshes(qtbot, search_setup):
    panel, bus, project, alpha, beta = search_setup
    beta.name = "Beta"
    bus.emit(ProjectEvents.PROJECT_ITEM_RENAMED, {"project": project, "item_id": beta.id, "old_name": "Beta needle", "new_name": "Beta"})
    qtbot.waitUntil(lambda: panel.results.topLevelItemCount() == 1, timeout=2000)
    assert _note_ids(panel) == {alpha.id}


def test_added_note_appears_in_results(qtbot, search_setup):
    panel, bus, project, alpha, beta = search_setup
    gamma = Note(name="Gamma", content="another needle")
    project.add_item(gamma)
    bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {"project": project, "item_id": gamma.id, "item_type": "note"})
    qtbot.waitUntil(lambda: panel.results.topLevelItemCount() == 3, timeout=2000)
    assert _note_ids(panel) == {alpha.id, beta.id, gamma.id}


def test_edited_note_content_refreshes(qtbot, search_setup):
    from pandaplot.models.events.event_types import NoteEvents

    panel, bus, _project, alpha, beta = search_setup
    alpha.content = "nothing here any more"
    bus.emit(NoteEvents.NOTE_CONTENT_CHANGED, {"note_id": alpha.id})
    qtbot.waitUntil(lambda: panel.results.topLevelItemCount() == 1, timeout=2000)
    assert _note_ids(panel) == {beta.id}


def test_item_event_from_any_source_refreshes_through_project_changed(qtbot, search_setup):
    """Any event that bubbles to project.changed (e.g. a deleted dataset that a note search does not list) re-runs
    the query, so new emitters cannot leave results stale."""
    from pandaplot.models.events.event_types import DatasetEvents

    panel, bus, project, alpha, beta = search_setup
    project.remove_item(alpha)
    bus.emit(DatasetEvents.DATASET_DELETED, {"dataset_id": "unrelated"})
    qtbot.waitUntil(lambda: panel.results.topLevelItemCount() == 1, timeout=2000)
    assert _note_ids(panel) == {beta.id}
