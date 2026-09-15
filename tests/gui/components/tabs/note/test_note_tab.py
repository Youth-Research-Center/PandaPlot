from unittest.mock import MagicMock, Mock, call

from pandaplot.gui.components.tabs.note.note_tab import NoteTab
from pandaplot.models.project.items.note import Note
from pandaplot.models.state.unsaved_changes_registry import UnsavedChangesRegistry


def test_get_tab_data_returns_note_type_and_id():
    tab = NoteTab.__new__(NoteTab)
    tab.note = Mock(id="note-1")

    assert tab.get_tab_data() == {"type": "note", "id": "note-1"}


def test_on_note_renamed_event_refreshes_title_for_matching_note():
    tab = NoteTab.__new__(NoteTab)
    tab.note = Mock(id="note-1")
    tab.refresh_tab_title = Mock()

    tab.on_note_renamed_event({"item_id": "note-1", "new_name": "Renamed"})

    tab.refresh_tab_title.assert_called_once()


def test_on_note_renamed_event_ignores_other_items():
    tab = NoteTab.__new__(NoteTab)
    tab.note = Mock(id="note-1")
    tab.refresh_tab_title = Mock()

    tab.on_note_renamed_event({"item_id": "other-id", "new_name": "Renamed"})

    tab.refresh_tab_title.assert_not_called()


def test_has_unsaved_changes_delegates_to_note_editor():
    tab = NoteTab.__new__(NoteTab)
    tab.note_editor = Mock()

    tab.note_editor.has_unsaved_changes.return_value = True
    assert tab.has_unsaved_changes() is True

    tab.note_editor.has_unsaved_changes.return_value = False
    assert tab.has_unsaved_changes() is False


def test_save_propagates_note_editors_reported_result():
    """Regression (PR #352 review): save() used to swallow save_content()'s
    result and always report True unless an exception escaped, so a save
    that ran but failed (e.g. EditNoteCommand rejected) was reported as
    successful -- a caller relying on that to decide whether it's safe to
    discard the tab would silently lose the edit."""
    tab = NoteTab.__new__(NoteTab)
    tab.note_editor = Mock()

    tab.note_editor.save_content.return_value = True
    assert tab.save() is True

    tab.note_editor.save_content.return_value = False
    assert tab.save() is False


def test_save_commits_without_occupying_an_undo_slot():
    """Regression (PR #352 review): NoteTab.save() is the flush path
    UnsavedChangesRegistry invokes -- it must not occupy a normal undo slot
    (see NoteEditorWidget.save_content's track_undo parameter), since a
    flush can run while another command already occupies a stack slot for
    an operation that hasn't finished yet."""
    tab = NoteTab.__new__(NoteTab)
    tab.note_editor = Mock()

    tab.save()

    tab.note_editor.save_content.assert_called_once_with(track_undo=False)


def test_save_returns_false_when_note_editor_raises():
    tab = NoteTab.__new__(NoteTab)
    tab.note_editor = Mock()
    tab.note_editor.save_content.side_effect = RuntimeError("boom")

    assert tab.save() is False


def test_init_registers_as_an_unsaved_changes_source(qapp):
    app_context = MagicMock()
    app_context.get_manager.return_value.get_surface_palette.return_value = {}
    note = Note(name="My Note", content="hello")

    tab = NoteTab(app_context=app_context, note=note, parent=None)

    assert call(UnsavedChangesRegistry) in app_context.get_manager.call_args_list
    app_context.get_manager.return_value.register.assert_called_once_with(tab)
