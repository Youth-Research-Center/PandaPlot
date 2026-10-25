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


def _close_tab_stub(*, choice: str = "save", path: str | None = "/tmp/project.pplot"):
    tab = NoteTab.__new__(NoteTab)
    tab.note = Mock(name="Notes")
    tab.note_editor = Mock()
    tab.note_editor.has_unsaved_changes.return_value = True
    tab.note_editor.save_content.return_value = True
    tab.app_context = Mock()
    tab.app_context.get_manager.return_value.config.auto_save.enabled = False
    tab.app_context.get_ui_controller.return_value.show_save_discard_cancel.return_value = choice
    state = tab.app_context.get_app_state.return_value
    state.project_file_path = path
    state.is_saving = False
    tab.app_context.get_command_executor.return_value.execute_command.return_value = True
    return tab, state


def test_can_close_autosave_on_flushes_and_uses_save_project_command():
    from pandaplot.commands.project.project.save_project_command import SaveProjectCommand

    tab, _state = _close_tab_stub()
    tab.app_context.get_manager.return_value.config.auto_save.enabled = True

    assert tab.can_close() is True

    tab.app_context.get_ui_controller.return_value.show_save_discard_cancel.assert_not_called()
    tab.note_editor.save_content.assert_called_once_with(track_undo=False)
    tab.app_context.get_manager.return_value.flush_all.assert_called_once_with()
    command = tab.app_context.get_command_executor.return_value.execute_command.call_args.args[0]
    assert isinstance(command, SaveProjectCommand)
    tab.app_context.get_command_executor.return_value.execute_command.assert_called_once_with(command, track_undo=False)


def test_can_close_autosave_on_never_saved_project_offers_discard():
    tab, _state = _close_tab_stub(path=None)
    tab.app_context.get_manager.return_value.config.auto_save.enabled = True
    tab.app_context.get_ui_controller.return_value.show_save_discard_cancel.return_value = "discard"

    assert tab.can_close() is True

    tab.app_context.get_ui_controller.return_value.show_save_discard_cancel.assert_called_once()
    tab.note_editor.save_content.assert_not_called()


def test_can_close_save_in_never_saved_project_commits_note_to_model_only():
    tab, _state = _close_tab_stub(path=None)

    assert tab.can_close() is True

    tab.note_editor.save_content.assert_called_once_with(track_undo=True)
    tab.app_context.get_command_executor.return_value.execute_command.assert_not_called()


def test_can_close_discard_does_not_commit_note():
    tab, _state = _close_tab_stub(choice="discard")

    assert tab.can_close() is True
    tab.note_editor.save_content.assert_not_called()
    tab.app_context.get_command_executor.return_value.execute_command.assert_not_called()


def test_can_close_cancel_keeps_dirty_tab():
    tab, _state = _close_tab_stub(choice="cancel")

    assert tab.can_close() is False
    tab.note_editor.save_content.assert_not_called()


def test_can_close_flush_failure_surfaces_error_and_refuses_close():
    tab, _state = _close_tab_stub()
    tab.app_context.get_manager.return_value.config.auto_save.enabled = True
    tab.note_editor.save_content.return_value = False

    assert tab.can_close() is False
    tab.app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_can_close_existing_project_save_in_progress_refuses_close():
    tab, _state = _close_tab_stub()
    tab.app_context.get_manager.return_value.config.auto_save.enabled = True
    tab.app_context.get_app_state.return_value.is_saving = True

    assert tab.can_close() is False
    tab.note_editor.save_content.assert_not_called()
    tab.app_context.get_command_executor.return_value.execute_command.assert_not_called()


def test_can_close_save_command_failure_refuses_close():
    tab, _state = _close_tab_stub()
    tab.app_context.get_manager.return_value.config.auto_save.enabled = True
    tab.app_context.get_command_executor.return_value.execute_command.return_value = False

    assert tab.can_close() is False
    tab.app_context.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_can_close_does_not_save_clean_note():
    tab = NoteTab.__new__(NoteTab)
    tab.note_editor = Mock()
    tab.note_editor.has_unsaved_changes.return_value = False
    tab.save = Mock()

    assert tab.can_close() is True
    tab.save.assert_not_called()
