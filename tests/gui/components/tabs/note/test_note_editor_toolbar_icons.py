"""The note editor toolbar shows theme-tinted bundled icons instead of emoji prefixes."""

import re

import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import QToolBar

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.note import note_editor
from pandaplot.gui.components.tabs.note.note_editor import NoteEditorWidget
from pandaplot.gui.resources.icon_library import build_icon
from pandaplot.models.project.items import Note
from pandaplot.models.project.project import Project
from pandaplot.services.theme.theme_manager import ThemeManager

LIGHT_TOKENS = {"text_primary": "#1C1E26", "text_muted": "#6B7280", "accent_icon_active": "#404BAC", "text_disabled": "#AEB2BC"}
DARK_TOKENS = {"text_primary": "#E2E2E2", "text_muted": "#9AA0AB", "accent_icon_active": "#8995FF", "text_disabled": "#5B6270"}

ICON_SIZE = 16
NON_ASCII = re.compile(r"[^\x00-\x7f]")
BADGE = " •"

EXPECTED_ICONS = {
    "Save": "floppy-disk",
    "Clear": "trash",
    "Export PDF": "file-pdf",
    "Insert Image": "image",
    "Artefacts": "paperclip",
    "Edit": "pencil-simple",
    "Preview": "eye",
    "Split": "columns",
    "Sync Scroll": "link",
}

ARTEFACTS_TOOLTIP = "Manage the charts and images in this note"

# QAction falls back to its text when no tooltip is set.
EXPECTED_TOOLTIPS = {
    "Save": "Save",
    "Clear": "Clear",
    "Export PDF": "Export PDF",
    "Insert Image": "Insert an image from the project gallery",
    "Artefacts": ARTEFACTS_TOOLTIP,
    "Edit": "Edit",
    "Preview": "Preview",
    "Split": "Split",
    "Sync Scroll": "Keep the source and preview scrolled to the same place in split view",
}


@pytest.fixture
def tokens() -> dict[str, str]:
    return dict(LIGHT_TOKENS)


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


def _toolbar_actions(editor: NoteEditorWidget) -> dict[str, QAction]:
    return {action.text().removesuffix(BADGE): action for action in editor.toolbar.actions() if not action.isSeparator()}


def _pixels(action: QAction):
    return action.icon().pixmap(QSize(ICON_SIZE, ICON_SIZE)).toImage()


def _strongest(action: QAction) -> QColor:
    image = action.icon().pixmap(QSize(32, 32)).toImage()
    pixels = (image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height()))
    return max(pixels, key=lambda pixel: pixel.alpha())


def _assert_close(actual: QColor, expected: str) -> None:
    wanted = QColor(expected)
    assert abs(actual.red() - wanted.red()) < 12
    assert abs(actual.green() - wanted.green()) < 12
    assert abs(actual.blue() - wanted.blue()) < 12


def test_toolbar_labels_match_the_expected_mapping_and_have_no_emoji(editor):
    actions = _toolbar_actions(editor)

    assert set(actions) == set(EXPECTED_ICONS)
    for text in actions:
        assert NON_ASCII.search(text) is None, f"{text!r} contains emoji or non-ASCII text"


@pytest.mark.parametrize(("label", "icon_name"), list(EXPECTED_ICONS.items()), ids=list(EXPECTED_ICONS))
def test_toolbar_action_uses_the_intended_icon(editor, label, icon_name):
    action = _toolbar_actions(editor)[label]
    expected = build_icon(icon_name, LIGHT_TOKENS["text_primary"], size=ICON_SIZE, disabled_color=LIGHT_TOKENS["text_disabled"])

    assert not action.icon().isNull()
    assert _pixels(action) == expected.pixmap(QSize(ICON_SIZE, ICON_SIZE)).toImage()


@pytest.mark.parametrize(("label", "tooltip"), list(EXPECTED_TOOLTIPS.items()), ids=list(EXPECTED_TOOLTIPS))
def test_tooltips_are_unchanged(editor, label, tooltip):
    assert _toolbar_actions(editor)[label].toolTip() == tooltip


def test_artefacts_badge_keeps_the_text_without_emoji(editor, monkeypatch):
    broken_row = type("Row", (), {"status": "broken"})()
    monkeypatch.setattr(note_editor, "compute_note_artefact_rows", lambda *_args, **_kwargs: [broken_row])

    editor._refresh_artefacts_badge()

    assert editor.artefacts_action.text() == "Artefacts" + BADGE
    assert editor.artefacts_action.toolTip() == f"{ARTEFACTS_TOOLTIP} -- some references are unused or broken"

    monkeypatch.setattr(note_editor, "compute_note_artefact_rows", lambda *_args, **_kwargs: [])
    editor._refresh_artefacts_badge()

    assert editor.artefacts_action.text() == "Artefacts"
    assert editor.artefacts_action.toolTip() == ARTEFACTS_TOOLTIP


def test_toolbar_shows_icons_beside_text_at_16px(editor):
    toolbar: QToolBar = editor.toolbar

    assert toolbar.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    assert toolbar.iconSize() == QSize(ICON_SIZE, ICON_SIZE)


def test_icons_are_retinted_when_the_theme_changes(editor, tokens):
    action = _toolbar_actions(editor)["Save"]
    _assert_close(_strongest(action), LIGHT_TOKENS["text_primary"])

    tokens.update(DARK_TOKENS)
    editor._apply_theme()

    _assert_close(_strongest(action), DARK_TOKENS["text_primary"])
