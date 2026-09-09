"""
Tests for note image path resolution and insert-image picker dialog.
"""

import os
from unittest.mock import MagicMock, patch

import pandas as pd
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QImage, QTextCursor, QTextDocument
from PySide6.QtWidgets import QDialog

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.note.note_editor import (
    NoteEditorWidget,
    NotePreviewBrowser,
    extract_referenced_image_keys,
    get_project_base_dir,
    register_project_image_resources,
)
from pandaplot.gui.dialogs.image.note_image_picker_dialog import NoteImagePickerDialog
from pandaplot.models.events.event_types import ChartEvents, ProjectEvents, ThemeEvents
from pandaplot.models.project.items import Chart, Dataset, Folder, Image, ImageGallery, Note
from pandaplot.models.project.project import Project
from pandaplot.services.qtasks import TaskScheduler


def create_test_png_bytes(width=10, height=10) -> bytes:
    """Generate valid PNG bytes in memory for testing."""
    from PySide6.QtCore import QBuffer, QIODevice

    img = QImage(width, height, QImage.Format.Format_RGB32)
    img.fill(0xFF0000)
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buf, "PNG")
    return bytes(buf.data())


def test_get_project_base_dir(tmp_path):
    app_context = MagicMock()
    project_file = str(tmp_path / "sub" / "my_project.pplot")
    project = Project(name="Test Project")
    project.project_file_path = project_file

    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    base_dir = get_project_base_dir(app_context)
    assert base_dir == os.path.dirname(os.path.abspath(project_file))


def test_register_project_image_resources(qapp, tmp_path):
    project_file = str(tmp_path / "my_project.pplot")
    project = Project(name="Test Project")
    project.project_file_path = project_file

    gallery = ImageGallery(name="Gallery 1")
    project.add_item(gallery)

    png_bytes = create_test_png_bytes()
    image = Image(name="sample.png", storage_mode="copied")
    image.set_bytes(png_bytes)
    project.add_item(image, parent_id=gallery.id)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    doc = QTextDocument()
    base_dir = register_project_image_resources(doc, app_context)

    assert base_dir == str(tmp_path)
    base_url = QUrl.fromLocalFile(str(tmp_path) + "/")

    # Registered by immutable id and by its exact gallery-relative path
    # ("Gallery 1/sample.png") -- never by bare name, which would ambiguously
    # match any other same-named image or an unrelated on-disk file.
    gallery_path = "Gallery 1/sample.png"
    res_path = doc.resource(QTextDocument.ResourceType.ImageResource, QUrl(gallery_path))
    res_resolved = doc.resource(QTextDocument.ResourceType.ImageResource, base_url.resolved(QUrl(gallery_path)))
    res_id = doc.resource(QTextDocument.ResourceType.ImageResource, QUrl(image.id))
    res_bare_name = doc.resource(QTextDocument.ResourceType.ImageResource, QUrl("sample.png"))

    assert res_path is not None and not res_path.isNull()
    assert res_resolved is not None and not res_resolved.isNull()
    assert res_id is not None and not res_id.isNull()
    assert res_bare_name is None


def test_note_preview_browser_load_resource(qapp, tmp_path):
    project = Project(name="Test Project")
    png_bytes = create_test_png_bytes()
    image = Image(name="fig1.png", storage_mode="copied")
    image.set_bytes(png_bytes)
    project.add_item(image)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    browser = NotePreviewBrowser(app_context=app_context)
    res = browser.loadResource(QTextDocument.ResourceType.ImageResource, QUrl("fig1.png"))

    assert res is not None
    assert isinstance(res, QImage)
    assert not res.isNull()


def test_extract_referenced_image_keys_handles_angle_brackets_and_percent_encoding():
    # Angle-bracket form is required by CommonMark for a target containing
    # spaces; without it, a naive "stop at whitespace" extractor would grab
    # just "<Gallery" and never match the real gallery path.
    keys = extract_referenced_image_keys("![x](<Gallery 1/sample.png>)")
    assert "Gallery 1/sample.png" in keys

    # Percent-encoded targets must also match their raw/decoded gallery key.
    keys = extract_referenced_image_keys("![x](Gallery%201/sample.png)")
    assert "Gallery 1/sample.png" in keys
    assert "Gallery%201/sample.png" in keys

    # Plain bare targets still work as before.
    keys = extract_referenced_image_keys("![x](plain.png =300x)")
    assert "plain.png" in keys


def test_extract_referenced_image_keys_ignores_code_and_escaped_images():
    """Image-shaped text inside code isn't a live reference (Markdown
    renders it as literal code, not an <img>), and neither is an image
    escaped with a leading backslash -- extracting either as "referenced"
    would trigger decoding, or a synchronous network fetch, of a same-named
    external gallery image for text that never actually renders as one."""
    keys = extract_referenced_image_keys("Use `![x](inline-code-id.png)` in prose.")
    assert "inline-code-id.png" not in keys

    keys = extract_referenced_image_keys("```\n![x](fenced-code-id.png)\n```")
    assert "fenced-code-id.png" not in keys

    keys = extract_referenced_image_keys(r"\![x](escaped-id.png)")
    assert "escaped-id.png" not in keys

    # A real reference alongside the code/escaped ones is still found.
    keys = extract_referenced_image_keys("`![x](code.png)` and ![y](real.png)")
    assert "real.png" in keys
    assert "code.png" not in keys


def test_extract_referenced_image_keys_respects_backslash_parity():
    """"\\\\![x](id)" is a literal backslash followed by a *live* image (an
    even run of backslashes doesn't escape the "!"), unlike "\\![x](id)" --
    the former's target must still count as referenced."""
    keys = extract_referenced_image_keys(r"\\![x](live-id.png)")
    assert "live-id.png" in keys


def test_extract_referenced_image_keys_handles_reference_style_links():
    """"![alt][label]" plus a "[label]: target" definition elsewhere in the
    note is valid Markdown that renders an <img>, just like the inline
    "![alt](target)" form -- PDF export/preview must not skip registering
    the image just because it's referenced this way."""
    source = "![Plot][plot]\n\n[plot]: gallery-id.png"
    keys = extract_referenced_image_keys(source)
    assert "gallery-id.png" in keys

    # Collapsed form: the label defaults to the alt text.
    source = "![gallery-id.png][]\n\n[gallery-id.png]: gallery-id.png"
    keys = extract_referenced_image_keys(source)
    assert "gallery-id.png" in keys

    # Labels are case-insensitive, per CommonMark.
    source = "![Plot][Plot]\n\n[plot]: gallery-id.png"
    keys = extract_referenced_image_keys(source)
    assert "gallery-id.png" in keys

    # An undefined label resolves to nothing extra (no crash).
    keys = extract_referenced_image_keys("![Plot][undefined]")
    assert keys == set()


def test_register_project_image_resources_skips_key_matching_real_file(qapp, tmp_path):
    """A gallery image whose id/path happens to match a real on-disk file
    must not be pre-registered under that URL -- pre-registering bypasses
    NotePreviewBrowser's "real file wins" loadResource check entirely, since
    a pre-registered resource is returned without loadResource ever running."""
    project_file = str(tmp_path / "my_project.pplot")
    project = Project(name="Test Project")
    project.project_file_path = project_file

    real_file = tmp_path / "shared.png"
    real_file.write_bytes(create_test_png_bytes(width=5, height=5))

    gallery_bytes = create_test_png_bytes(width=50, height=50)
    image = Image(id="shared.png", name="shared.png", storage_mode="copied")
    image.set_bytes(gallery_bytes)
    project.add_item(image)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    doc = QTextDocument()
    base_dir = register_project_image_resources(doc, app_context)
    base_url = QUrl.fromLocalFile(base_dir + "/")

    # Not pre-registered under the id/name that coincides with the real
    # file's relative path -- QTextDocument's own default resource loading
    # then resolves it to the real 5x5 file, not the 50x50 gallery image
    # that would have shadowed it if pre-registered.
    res = doc.resource(QTextDocument.ResourceType.ImageResource, base_url.resolved(QUrl("shared.png")))
    assert res is not None
    assert res.width() == 5 and res.height() == 5


def test_note_preview_browser_does_not_fuzzy_match_by_stem(qapp, tmp_path):
    """A reference to an unrelated file must not be hijacked by a same-stem
    gallery image (PR #326 review: only exact id/gallery-path should match)."""
    project = Project(name="Test Project")
    png_bytes = create_test_png_bytes()
    image = Image(name="plot.png", storage_mode="copied")
    image.set_bytes(png_bytes)
    project.add_item(image)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    browser = NotePreviewBrowser(app_context=app_context)
    # Different extension/full name than the gallery image's exact name/id:
    # must not resolve via filename-stem or basename fuzzy matching.
    res = browser.loadResource(QTextDocument.ResourceType.ImageResource, QUrl("assets/plot.jpg"))

    assert res is None or (hasattr(res, "isNull") and res.isNull())


def test_note_preview_browser_does_not_match_by_source_file(qapp, tmp_path):
    """source_file isn't a registrable/matchable key (only id and exact
    gallery path are): a note referencing an image's former/remote source
    path -- which the image itself no longer resolves through, e.g. after
    being re-imported as "copied" -- must not be served that image's bytes
    just because the string happens to coincide."""
    project = Project(name="Test Project")
    png_bytes = create_test_png_bytes()
    image = Image(
        name="plot.png", storage_mode="copied", source_file="https://example.com/old-plot.png"
    )
    image.set_bytes(png_bytes)
    project.add_item(image)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    browser = NotePreviewBrowser(app_context=app_context)
    res = browser.loadResource(
        QTextDocument.ResourceType.ImageResource, QUrl("https://example.com/old-plot.png")
    )

    assert res is None or (hasattr(res, "isNull") and res.isNull())


def test_note_preview_browser_prefers_real_file_over_gallery_match(qapp, tmp_path):
    """An existing on-disk file wins over a same-name/id gallery image."""
    real_file = tmp_path / "shared.png"
    real_bytes = create_test_png_bytes(width=5, height=5)
    real_file.write_bytes(real_bytes)

    project = Project(name="Test Project")
    gallery_bytes = create_test_png_bytes(width=50, height=50)
    image = Image(id="shared.png", name="shared.png", storage_mode="copied")
    image.set_bytes(gallery_bytes)
    project.add_item(image)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    browser = NotePreviewBrowser(app_context=app_context)
    res = browser.loadResource(QTextDocument.ResourceType.ImageResource, QUrl.fromLocalFile(str(real_file)))

    # Qt's default loadResource() may hand back either a decoded QImage or
    # the raw file bytes (which QTextDocument decodes itself); either way it
    # must be the 5x5 real file, not the 50x50 gallery image.
    if isinstance(res, QImage):
        loaded = res
    else:
        loaded = QImage()
        loaded.loadFromData(bytes(res))
    assert not loaded.isNull()
    assert loaded.width() == 5 and loaded.height() == 5


def test_note_editor_update_preview_discards_stale_document_resources(qapp, tmp_path):
    """QTextDocument has no API to remove a resource once added, and
    setHtml() on the same document doesn't clear that cache either. If a
    gallery image is removed and a *new, unrelated* image happens to reuse
    its id, re-rendering the same document object would still answer with
    the old image's bytes. update_preview() must give the preview a fresh
    document each render instead of reusing/mutating the same one forever."""
    project = Project(name="Test Project")
    old_bytes = create_test_png_bytes(width=5, height=5)
    old_image = Image(id="reused-id", name="old.png", storage_mode="copied")
    old_image.set_bytes(old_bytes)
    project.add_item(old_image)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="My Note", content="![Old](reused-id)")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    editor.set_mode("preview")

    old_res = editor.preview.document().resource(QTextDocument.ResourceType.ImageResource, QUrl("reused-id"))
    assert old_res.width() == 5

    # Simulate the old image being removed and a new, unrelated image
    # reusing the same id, with different pixel content.
    project.remove_item(old_image)
    new_bytes = create_test_png_bytes(width=9, height=9)
    new_image = Image(id="reused-id", name="new.png", storage_mode="copied")
    new_image.set_bytes(new_bytes)
    project.add_item(new_image)

    editor.preview.image_cache.clear()  # what on_project_item_changed_event does
    editor.update_preview()

    new_res = editor.preview.document().resource(QTextDocument.ResourceType.ImageResource, QUrl("reused-id"))
    assert new_res.width() == 9  # not the stale 5x5 old image


def test_note_editor_update_preview_and_event_refresh(qapp, tmp_path):
    project = Project(name="Test Project")
    png_bytes = create_test_png_bytes()
    image = Image(name="plot.png", storage_mode="copied")
    image.set_bytes(png_bytes)
    project.add_item(image)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="My Note", content="![Plot](plot.png)")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)

    # Switch to preview mode
    editor.set_mode("preview")
    assert editor.stack.currentIndex() == 1

    # Check preview document contains image resource
    doc = editor.preview.document()
    res = doc.resource(QTextDocument.ResourceType.ImageResource, QUrl("plot.png"))
    assert res is not None and not res.isNull()

    # Trigger project item changed event for an image (only image/gallery
    # changes should refresh the preview -- see the "unrelated event" test
    # below).
    with patch.object(editor, "update_preview") as mock_update:
        editor.on_project_item_changed_event(
            {"event": ProjectEvents.PROJECT_ITEM_ADDED, "image_id": image.id}
        )
        mock_update.assert_called_once()


def test_note_editor_ignores_unrelated_project_item_events(qapp, tmp_path):
    """Adding/renaming an unrelated note/dataset must not clear the image
    cache or rerender the preview -- these are generic project-item events,
    not necessarily about images at all."""
    project = Project(name="Test Project")
    png_bytes = create_test_png_bytes()
    image = Image(name="plot.png", storage_mode="copied")
    image.set_bytes(png_bytes)
    project.add_item(image)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="My Note", content="![Plot](plot.png)")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    editor.set_mode("preview")

    with patch.object(editor, "update_preview") as mock_update:
        # A generic item event with no image/gallery id and an id that
        # doesn't resolve to an Image/ImageGallery (e.g. an unrelated note
        # being renamed) must be ignored.
        editor.on_project_item_changed_event(
            {"event": ProjectEvents.PROJECT_ITEM_RENAMED, "item_id": "some-other-note-id"}
        )
        mock_update.assert_not_called()


def test_note_editor_subscribes_to_project_item_content_changed(qapp, tmp_path):
    """EditImageCommand emits PROJECT_ITEM_CONTENT_CHANGED (not
    PROJECT_ITEM_RENAMED) for a content edit -- the editor must subscribe to
    it too, or a note's preview goes stale after the user edits (crop/
    rotate/resize) a gallery image it references."""
    project = Project(name="Test Project")
    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="My Note", content="")
    NoteEditorWidget(app_context=app_context, note=note, parent=None)

    subscribed_events = [
        call.args[0] for call in app_context.event_bus.subscribe.call_args_list
    ]
    assert ProjectEvents.PROJECT_ITEM_CONTENT_CHANGED in subscribed_events


def test_note_editor_subscribes_to_chart_data_updated(qapp):
    """Series dataset/column/axis edits publish CHART_DATA_UPDATED, not
    CHART_UPDATED (see ChartPropertiesPanel._on_dirty_only) -- the editor
    must subscribe to it too, or a note's cached chart render goes stale
    until the user clicks Apply in the chart properties panel."""
    project = Project(name="Test Project")
    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="My Note", content="")
    NoteEditorWidget(app_context=app_context, note=note, parent=None)

    subscribed_events = [
        call.args[0] for call in app_context.event_bus.subscribe.call_args_list
    ]
    assert ChartEvents.CHART_DATA_UPDATED in subscribed_events


def test_note_editor_refreshes_for_folder_containing_gallery(qapp, tmp_path):
    """A generic Folder isn't itself an image, but renaming/moving one that
    contains an ImageGallery (galleries can be created beneath ordinary
    folders) changes every descendant image's gallery-relative path just as
    surely as touching the gallery directly -- it must not be ignored just
    because the folder itself isn't an Image/ImageGallery."""
    project = Project(name="Test Project")
    folder = Folder(name="My Folder")
    project.add_item(folder)
    gallery = ImageGallery(name="Gallery 1")
    project.add_item(gallery, parent_id=folder.id)
    png_bytes = create_test_png_bytes()
    image = Image(name="plot.png", storage_mode="copied")
    image.set_bytes(png_bytes)
    project.add_item(image, parent_id=gallery.id)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="My Note", content=f"![Plot]({image.id})")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    editor.set_mode("preview")

    with patch.object(editor, "update_preview") as mock_update:
        editor.on_project_item_changed_event(
            {"event": ProjectEvents.PROJECT_ITEM_RENAMED, "item_id": folder.id}
        )
        mock_update.assert_called_once()


def test_note_editor_refreshes_for_deleted_folder_snapshot_containing_image(qapp, tmp_path):
    """Once a folder is deleted it's gone from the project, so the only
    place left to tell whether its subtree held any images is the deleted
    snapshot delete_item_command attaches to the event."""
    project = Project(name="Test Project")
    png_bytes = create_test_png_bytes()

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="My Note", content="Just text, no images.")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    editor.set_mode("preview")

    deleted_image = Image(name="plot.png", storage_mode="copied")
    deleted_image.set_bytes(png_bytes)
    deleted_snapshot = {
        "id": "deleted-folder",
        "name": "Deleted Folder",
        "items": [deleted_image.to_dict()],
    }

    with patch.object(editor, "update_preview") as mock_update:
        editor.on_project_item_changed_event(
            {
                "event": ProjectEvents.PROJECT_ITEM_REMOVED,
                "item_id": "deleted-folder",
                "item_type": "folder",
                "item_data": deleted_snapshot,
            }
        )
        mock_update.assert_called_once()

    # A deleted folder confirmed to hold no images is correctly ignored.
    with patch.object(editor, "update_preview") as mock_update:
        editor.on_project_item_changed_event(
            {
                "event": ProjectEvents.PROJECT_ITEM_REMOVED,
                "item_id": "deleted-empty-folder",
                "item_type": "folder",
                "item_data": {"id": "deleted-empty-folder", "name": "Empty", "items": []},
            }
        )
        mock_update.assert_not_called()


def test_note_editor_invalidates_cache_for_chart_deletion(qapp):
    """Deleting a chart referenced by the note must drop its cached render,
    not leave the note showing the deleted chart's stale image forever
    (see PR #383 review)."""
    chart = Chart(name="Doomed Chart")
    project = Project(name="Test Project")
    # The chart is already gone from the project by the time the REMOVED
    # event arrives, matching how delete_item_command actually behaves.

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="My Note", content=f"![Doomed Chart]({chart.id})")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    editor.set_mode("preview")
    editor.preview.image_cache[chart.id] = QImage(5, 5, QImage.Format.Format_RGB32)

    with patch.object(editor, "update_preview") as mock_update:
        editor.on_project_item_changed_event(
            {
                "event": ProjectEvents.PROJECT_ITEM_REMOVED,
                "item_id": chart.id,
                "item_type": "chart",
                "item_data": chart.to_dict(),
            }
        )
        mock_update.assert_called_once()

    assert chart.id not in editor.preview.image_cache


def test_note_editor_invalidates_cache_for_deleted_chart_snapshot_without_item_type(qapp):
    """Same as above, but exercising the deleted-snapshot fallback path (no
    "item_type" in the payload, matching a generic delete_item_command)."""
    chart = Chart(name="Doomed Chart")
    project = Project(name="Test Project")

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="My Note", content=f"![Doomed Chart]({chart.id})")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    editor.set_mode("preview")
    editor.preview.image_cache[chart.id] = QImage(5, 5, QImage.Format.Format_RGB32)

    with patch.object(editor, "update_preview") as mock_update:
        editor.on_project_item_changed_event(
            {
                "event": ProjectEvents.PROJECT_ITEM_REMOVED,
                "item_id": chart.id,
                "item_data": chart.to_dict(),
            }
        )
        mock_update.assert_called_once()

    assert chart.id not in editor.preview.image_cache


def test_note_editor_export_pdf_registers_resources(qapp, tmp_path):
    project = Project(name="Test Project")
    png_bytes = create_test_png_bytes()
    image = Image(name="chart.png", storage_mode="copied")
    image.set_bytes(png_bytes)
    project.add_item(image)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    pdf_file = str(tmp_path / "output.pdf")
    note = Note(name="PDF Note", content="![Chart](chart.png)")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)

    with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=(pdf_file, "PDF Files (*.pdf)")):
        editor.export_pdf()

    assert os.path.exists(pdf_file)


def test_note_image_picker_dialog_tree_and_selection(qapp):
    project = Project(name="Test Project")
    gallery = ImageGallery(name="Album 1")
    project.add_item(gallery)

    png_bytes = create_test_png_bytes()
    image = Image(name="photo1.png", storage_mode="copied")
    image.set_bytes(png_bytes)
    project.add_item(image, parent_id=gallery.id)

    app_context = MagicMock()
    app_context.get_manager.return_value.get_design_tokens.return_value = {}

    dialog = NoteImagePickerDialog(app_context=app_context, project=project)
    dialog.show()

    assert not dialog.tree.isHidden()
    assert dialog.empty_label.isHidden()

    # Select image item
    items = dialog.tree.findItems(
        "photo1.png",
        Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive,
    )
    assert len(items) == 1
    items[0].setSelected(True)

    assert dialog.ok_button.isEnabled()
    dialog._on_ok_clicked()
    assert dialog.get_selected_image() == image


def test_note_image_picker_dialog_preserves_folder_hierarchy_for_same_named_galleries(qapp):
    """Two different galleries that happen to share a name (duplicates are
    allowed) must not collapse into indistinguishable top-level entries just
    because their Folder ancestor isn't itself an ImageGallery -- the real
    hierarchy must be shown so each image's actual source is identifiable."""
    project = Project(name="Test Project")

    folder_a = Folder(name="Folder A")
    project.add_item(folder_a)
    gallery_a = ImageGallery(name="Gallery 1")
    project.add_item(gallery_a, parent_id=folder_a.id)
    image_a = Image(name="photo.png", storage_mode="copied")
    image_a.set_bytes(create_test_png_bytes())
    project.add_item(image_a, parent_id=gallery_a.id)

    folder_b = Folder(name="Folder B")
    project.add_item(folder_b)
    gallery_b = ImageGallery(name="Gallery 1")  # same name as gallery_a
    project.add_item(gallery_b, parent_id=folder_b.id)
    image_b = Image(name="photo.png", storage_mode="copied")  # same name as image_a
    image_b.set_bytes(create_test_png_bytes())
    project.add_item(image_b, parent_id=gallery_b.id)

    app_context = MagicMock()
    app_context.get_manager.return_value.get_design_tokens.return_value = {}

    dialog = NoteImagePickerDialog(app_context=app_context, project=project)
    dialog.show()

    # Both "Gallery 1" nodes must be nested under their distinct folder, not
    # sitting as two identical top-level items.
    assert dialog.tree.topLevelItemCount() == 2
    top_level_names = {dialog.tree.topLevelItem(i).text(0) for i in range(dialog.tree.topLevelItemCount())}
    assert top_level_names == {"Folder A", "Folder B"}

    gallery_items = dialog.tree.findItems(
        "Gallery 1", Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive
    )
    assert len(gallery_items) == 2
    parent_names = {item.parent().text(0) for item in gallery_items}
    assert parent_names == {"Folder A", "Folder B"}


def test_note_image_picker_dialog_scales_thumbnail_to_icon_size(qapp):
    """A full-resolution gallery photo must be scaled down, not drawn at
    native size and clipped/cropped inside the small tree icon."""
    project = Project(name="Test Project")
    png_bytes = create_test_png_bytes(width=1200, height=800)
    image = Image(name="big_photo.png", storage_mode="copied")
    image.set_bytes(png_bytes)
    project.add_item(image)

    app_context = MagicMock()
    app_context.get_manager.return_value.get_design_tokens.return_value = {}

    dialog = NoteImagePickerDialog(app_context=app_context, project=project)
    pix = dialog._load_pixmap_for_image(image)

    assert pix is not None
    assert pix.width() <= 24 and pix.height() <= 24


def test_note_image_picker_dialog_falls_back_to_source_file_when_copied(qapp, tmp_path):
    """Matches note_editor.load_qimage_for_item's fallback: a "copied" image
    with no in-memory bytes yet but a leftover source_file should still load,
    not show as broken, for consistency between the preview and the picker."""
    real_file = tmp_path / "leftover.png"
    real_file.write_bytes(create_test_png_bytes())

    project = Project(name="Test Project")
    image = Image(name="leftover.png", source_file=str(real_file), storage_mode="copied")
    project.add_item(image)

    app_context = MagicMock()
    app_context.get_manager.return_value.get_design_tokens.return_value = {}

    dialog = NoteImagePickerDialog(app_context=app_context, project=project)
    pix = dialog._load_pixmap_for_image(image)

    assert pix is not None and not pix.isNull()


def test_note_image_picker_dialog_loads_thumbnails_via_task_scheduler(qapp, qtbot):
    """Thumbnails decode on a TaskScheduler worker thread and land back on
    the tree icon via the GUI-thread result callback, instead of blocking
    __init__ synchronously for every image."""
    project = Project(name="Test Project")
    png_bytes = create_test_png_bytes()
    image = Image(name="photo1.png", storage_mode="copied")
    image.set_bytes(png_bytes)
    project.add_item(image)

    app_context = MagicMock()
    app_context.get_manager.return_value.get_design_tokens.return_value = {}
    app_context.get_task_scheduler.return_value = TaskScheduler()

    dialog = NoteImagePickerDialog(app_context=app_context, project=project)

    # The decode is dispatched to a worker thread and hasn't necessarily
    # completed yet -- but it must have been dispatched, not done inline.
    assert image.id not in dialog._pixmap_cache or dialog._pixmap_cache[image.id] is None

    dialog.task_scheduler.threadpool.waitForDone(2000)
    qtbot.waitUntil(lambda: dialog._pixmap_cache.get(image.id) is not None, timeout=2000)

    pix = dialog._pixmap_cache[image.id]
    assert pix is not None and not pix.isNull()


def test_note_image_picker_dialog_empty_state(qapp):
    project = Project(name="Empty Project")
    app_context = MagicMock()

    dialog = NoteImagePickerDialog(app_context=app_context, project=project)
    dialog.show()

    assert dialog.tree.isHidden()
    assert not dialog.empty_label.isHidden()
    assert not dialog.ok_button.isEnabled()


def test_note_editor_insert_image_action(qapp):
    project = Project(name="Test Project")
    png_bytes = create_test_png_bytes()
    image = Image(name="my_diagram.png", storage_mode="copied")
    image.set_bytes(png_bytes)
    project.add_item(image)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
    mock_dialog.get_selected_image.return_value = image

    with patch("pandaplot.gui.components.tabs.note.note_editor.NoteImagePickerDialog", return_value=mock_dialog):
        editor.insert_image_from_picker()

    # References by immutable id (not the mutable/duplicatable name), with
    # the name kept as alt text.
    assert editor.text_edit.toPlainText() == f"![my_diagram.png]({image.id})"


def test_note_editor_insert_image_applies_default_width_cap(qapp):
    """A gallery image wider than the default cap gets a `=WIDTHx` modifier."""
    project = Project(name="Test Project")
    png_bytes = create_test_png_bytes()
    image = Image(name="wide.png", storage_mode="copied", width=1200, height=800)
    image.set_bytes(png_bytes)
    project.add_item(image)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
    mock_dialog.get_selected_image.return_value = image

    with patch("pandaplot.gui.components.tabs.note.note_editor.NoteImagePickerDialog", return_value=mock_dialog):
        editor.insert_image_from_picker()

    assert editor.text_edit.toPlainText() == f"![wide.png]({image.id} =500x)"


def test_note_editor_insert_image_sanitizes_bracket_in_alt_text(qapp):
    """A name containing "]" would otherwise close the Markdown alt-text span
    early, breaking the whole image reference (there's no escape for it in
    bare link syntax)."""
    project = Project(name="Test Project")
    png_bytes = create_test_png_bytes()
    image = Image(name="Screenshot [final].png", storage_mode="copied")
    image.set_bytes(png_bytes)
    project.add_item(image)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
    mock_dialog.get_selected_image.return_value = image

    with patch("pandaplot.gui.components.tabs.note.note_editor.NoteImagePickerDialog", return_value=mock_dialog):
        editor.insert_image_from_picker()

    content = editor.text_edit.toPlainText()
    assert content == f"![Screenshot (final).png]({image.id})"

    # And it must actually render as an image, not fall back to plain text.
    from pandaplot.services.note_render.latex_markdown_renderer import render_body_html
    html = render_body_html(content)
    assert "<img" in html


def test_note_editor_insert_image_refreshes_preview_only_mode(qapp):
    """Inserting while preview-only (no live textChanged connection) still refreshes."""
    project = Project(name="Test Project")
    png_bytes = create_test_png_bytes()
    image = Image(name="my_diagram.png", storage_mode="copied")
    image.set_bytes(png_bytes)
    project.add_item(image)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    editor.set_mode("preview")

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
    mock_dialog.get_selected_image.return_value = image

    with patch("pandaplot.gui.components.tabs.note.note_editor.NoteImagePickerDialog", return_value=mock_dialog):
        with patch.object(editor, "update_preview") as mock_update:
            editor.insert_image_from_picker()
            mock_update.assert_called_once()


def test_note_editor_insert_chart_action(qapp):
    """Test inserting markdown for a selected chart via NoteChartPickerDialog."""
    chart = Chart(name="Sample Plot")
    project = Project(name="Test Project")
    project.add_item(chart)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
    mock_dialog.get_selected_chart.return_value = chart

    with patch("pandaplot.gui.dialogs.note.NoteChartPickerDialog", return_value=mock_dialog):
        editor.insert_chart_from_picker()

    content = editor.text_edit.toPlainText()
    assert content == f"![Sample Plot]({chart.id} =500x)"


def test_note_editor_insert_table_action(qapp):
    """Test inserting markdown table via NoteTablePickerDialog."""
    project = Project(name="Test Project")

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)

    table_md = "| A | B |\n| --- | --- |\n| 1 | 2 |"
    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
    mock_dialog.get_markdown_table.return_value = table_md

    with patch("pandaplot.gui.dialogs.note.NoteTablePickerDialog", return_value=mock_dialog):
        editor.insert_table_from_picker()

    content = editor.text_edit.toPlainText()
    assert "| A | B |" in content


def test_note_editor_insert_table_mid_paragraph_still_renders_as_table(qapp):
    """A single newline doesn't isolate the table from surrounding Markdown
    (Python-Markdown's tables extension needs a blank line on each side, or
    the table lines get absorbed into the preceding/following paragraph
    block instead of becoming a <table>). Inserting at the end of existing
    text, followed by more typed text, must still render as a real table."""
    from markdown import markdown

    project = Project(name="Test Project")

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="Note 1", content="Some paragraph text")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    cursor = editor.text_edit.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    editor.text_edit.setTextCursor(cursor)

    table_md = "| A | B |\n| --- | --- |\n| 1 | 2 |"
    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
    mock_dialog.get_markdown_table.return_value = table_md

    with patch("pandaplot.gui.dialogs.note.NoteTablePickerDialog", return_value=mock_dialog):
        editor.insert_table_from_picker()
    editor.text_edit.insertPlainText("Following text")

    content = editor.text_edit.toPlainText()
    html = markdown(content, extensions=["tables"])
    assert "<table>" in html
    assert "<p>Following text</p>" in html


def test_load_qimage_for_chart_renders_real_chart(qapp):
    """load_qimage_for_chart must actually rasterize a real chart, and must
    not leave the throwaway ChartEditorWidget's event-bus subscription live
    past the call (see tests/gui/core/test_unsubscribe_widget_tree.py for the
    documented historical bug this guards against)."""
    from pandaplot.gui.components.tabs.note.note_editor import load_qimage_for_chart

    project = Project(name="Test Project")
    df = pd.DataFrame({"x": [1, 2, 3], "y": [10, 20, 30]})
    dataset = Dataset(name="Data 1", data=df)
    project.add_item(dataset)

    chart = Chart(name="Line Chart", chart_type="line")
    chart.add_data_series(
        dataset.id, x_column_id=dataset.column_id("x"), y_column_id=dataset.column_id("y"),
    )
    project.add_item(chart)

    app_context = build_app_context()
    app_context.app_state.load_project(project)
    theme_subscribers_before = list(app_context.event_bus._subscribers.get(ThemeEvents.THEME_CHANGED, []))

    qimg = load_qimage_for_chart(app_context, chart)

    assert qimg is not None
    assert not qimg.isNull()
    assert qimg.width() > 0
    assert qimg.height() > 0

    qapp.processEvents()  # let the deferred deleteLater() actually run
    theme_subscribers_after = app_context.event_bus._subscribers.get(ThemeEvents.THEME_CHANGED, [])
    assert theme_subscribers_after == theme_subscribers_before


def test_note_editor_insert_chart_uses_shared_width_constant(qapp):
    """Chart insertion must size from the same constant image insertion uses,
    not a hardcoded duplicate, so the two stay in sync if it's ever tuned."""
    chart = Chart(name="Sample Plot")
    project = Project(name="Test Project")
    project.add_item(chart)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
    mock_dialog.get_selected_chart.return_value = chart

    with patch("pandaplot.gui.dialogs.note.NoteChartPickerDialog", return_value=mock_dialog):
        with patch(
            "pandaplot.gui.components.tabs.note.note_editor._DEFAULT_INSERT_MAX_WIDTH", 777
        ):
            editor.insert_chart_from_picker()

    content = editor.text_edit.toPlainText()
    assert content == f"![Sample Plot]({chart.id} =777x)"


def test_chart_update_event_only_invalidates_that_chart(qapp):
    """A CHART_UPDATED event for one chart must not evict other cached entries."""
    chart_a = Chart(name="Chart A")
    chart_b = Chart(name="Chart B")
    project = Project(name="Test Project")
    project.add_item(chart_a)
    project.add_item(chart_b)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    editor.preview.image_cache = {
        chart_a.id: QImage(5, 5, QImage.Format.Format_RGB32),
        chart_b.id: QImage(5, 5, QImage.Format.Format_RGB32),
        "some-gallery-image-id": QImage(5, 5, QImage.Format.Format_RGB32),
    }

    with patch.object(editor, "update_preview"):
        editor.on_chart_or_dataset_changed_event({"chart_id": chart_a.id, "chart": chart_a})

    assert chart_a.id not in editor.preview.image_cache
    assert chart_b.id in editor.preview.image_cache
    assert "some-gallery-image-id" in editor.preview.image_cache


def test_dataset_change_event_only_invalidates_charts_using_that_dataset(qapp):
    """A DATASET_CHANGED event must only evict charts that reference that dataset."""
    chart_using_ds = Chart(name="Uses Dataset")
    chart_using_ds.add_data_series(dataset_id="ds-1", x_column_id="x", y_column_id="y")
    chart_unrelated = Chart(name="Unrelated")
    chart_unrelated.add_data_series(dataset_id="ds-2", x_column_id="x", y_column_id="y")
    project = Project(name="Test Project")
    project.add_item(chart_using_ds)
    project.add_item(chart_unrelated)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    editor.preview.image_cache = {
        chart_using_ds.id: QImage(5, 5, QImage.Format.Format_RGB32),
        chart_unrelated.id: QImage(5, 5, QImage.Format.Format_RGB32),
    }

    with patch.object(editor, "update_preview"):
        editor.on_chart_or_dataset_changed_event({"dataset_id": "ds-1"})

    assert chart_using_ds.id not in editor.preview.image_cache
    assert chart_unrelated.id in editor.preview.image_cache


def test_note_editor_registers_chart_resources(qapp):
    """Test registering chart images as resources for note documents."""
    chart = Chart(name="Chart 1")
    project = Project(name="Test Project")
    project.add_item(chart)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    doc = QTextDocument()
    mock_qimg = QImage(20, 20, QImage.Format.Format_RGB32)

    with patch("pandaplot.gui.components.tabs.note.note_editor.load_qimage_for_chart", return_value=mock_qimg):
        register_project_image_resources(
            doc, app_context, referenced_keys={chart.id}
        )

    res = doc.resource(QTextDocument.ResourceType.ImageResource, QUrl(chart.id))
    assert res is not None


def test_note_editor_chart_does_not_shadow_same_named_gallery_image(qapp):
    """A chart must not register a bare-name/".png" alias: it would silently
    overwrite an unrelated gallery image resource registered under the exact
    same key (e.g. a gallery image literally named "Plot.png" vs. a chart
    named "Plot")."""
    image = Image(name="Plot.png")
    chart = Chart(name="Plot")
    project = Project(name="Test Project")
    project.add_item(image)
    project.add_item(chart)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    doc = QTextDocument()
    image_qimg = QImage(10, 10, QImage.Format.Format_RGB32)
    image_qimg.fill(0xFF0000FF)
    chart_qimg = QImage(20, 20, QImage.Format.Format_RGB32)
    chart_qimg.fill(0xFF00FF00)

    with patch(
        "pandaplot.gui.components.tabs.note.note_editor.load_qimage_for_item", return_value=image_qimg
    ), patch(
        "pandaplot.gui.components.tabs.note.note_editor.load_qimage_for_chart", return_value=chart_qimg
    ):
        register_project_image_resources(doc, app_context)

    res = doc.resource(QTextDocument.ResourceType.ImageResource, QUrl("Plot.png"))
    assert res.width() == 10  # still the gallery image, not overwritten by the chart
