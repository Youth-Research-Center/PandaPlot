"""The note editor status bar shows a check icon beside plain success messages instead of a trailing glyph."""

import pytest

from pandaplot.app import build_app_context
from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.components.tabs.note.note_editor import NoteEditorWidget
from pandaplot.models.project.items import Note
from pandaplot.models.project.project import Project
from pandaplot.services.theme.theme_manager import ThemeManager
from tests.gui.icon_testing import ICON_TOKENS, assert_tinted, strongest_pixel

DARK_SUCCESS = "#3FB950"


@pytest.fixture
def tokens() -> dict[str, str]:
    return dict(ICON_TOKENS)


@pytest.fixture
def editor(qapp, monkeypatch, tokens):
    app_context = build_app_context()
    theme_manager = app_context.get_manager(ThemeManager)
    real_tokens = theme_manager.get_design_tokens
    monkeypatch.setattr(theme_manager, "get_design_tokens", lambda: {**real_tokens(), **tokens})
    project = Project(name="Test Project")
    note = Note(name="My Note", content="hello")
    project.add_item(note)
    app_context.app_state.load_project(project)
    widget = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    yield widget
    widget.deleteLater()


def test_status_icon_is_a_hidden_check_while_ready(editor):
    assert isinstance(editor.status_icon, IconLabel)
    assert editor.status_icon.icon_name == "check"
    assert editor.status_label.text() == "Ready"
    assert editor.status_icon.isHidden()


def test_saving_shows_plain_saved_text_with_a_visible_check(editor):
    editor.text_edit.setPlainText("changed")

    assert editor.save_content() is True

    assert editor.status_label.text() == "Saved"
    assert not editor.status_icon.isHidden()


def test_syncing_shows_plain_synced_text_with_a_visible_check(editor):
    editor.on_note_content_changed_event({"note_id": editor.note.id, "new_content": "from elsewhere"})

    assert editor.status_label.text() == "Synced"
    assert not editor.status_icon.isHidden()


def test_check_is_hidden_after_the_reset_timer_slot_runs(editor):
    editor.update_status("Saved", success=True)
    assert not editor.status_icon.isHidden()

    editor._reset_status()

    assert editor.status_label.text() == "Ready"
    assert editor.status_icon.isHidden()


def test_non_success_status_hides_the_check(editor):
    editor.update_status("Saved", success=True)

    editor.update_status("Modified *")

    assert editor.status_icon.isHidden()


def test_saved_and_synced_keep_the_success_colour(editor):
    for text in ("Saved", "Synced"):
        editor.update_status(text, success=True)
        assert "#28a745" in editor.status_label.styleSheet()


def test_status_icon_retints_when_the_theme_changes(editor, tokens):
    assert_tinted(strongest_pixel(editor.status_icon.pixmap().toImage()), ICON_TOKENS["status_success"])

    tokens["status_success"] = DARK_SUCCESS
    editor._apply_theme()

    assert_tinted(strongest_pixel(editor.status_icon.pixmap().toImage()), DARK_SUCCESS)
