"""
Tests for note image path resolution and insert-image picker dialog.
"""

import os
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QImage, QTextCursor, QTextDocument
from PySide6.QtWidgets import QDialog

from pandaplot.commands.base_command import CommandResult
from pandaplot.gui.components.tabs.note.note_editor import (
    NoteEditorWidget,
    NotePreviewBrowser,
    RenderedChartSnapshot,
    compute_note_artefact_rows,
    extract_referenced_image_keys,
    find_chart_snapshot_gallery_id,
    get_project_base_dir,
    register_project_image_resources,
)
from pandaplot.gui.dialogs.image.note_image_picker_dialog import NoteImagePickerDialog
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import Chart, Folder, Image, ImageGallery, Note
from pandaplot.models.project.project import Project
from pandaplot.services.config.config_manager import ConfigManager
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


def _rendered_snapshot(width: int, height: int) -> RenderedChartSnapshot:
    return RenderedChartSnapshot(png_bytes=create_test_png_bytes(width, height), width=width, height=height)


def _make_app_context_with_synchronous_task_scheduler(project):
    """An app_context whose TaskScheduler runs tasks immediately, inline,
    instead of on a real background thread -- lets a test exercise the
    async chart-render dispatch/callback wiring without needing an actual
    QThreadPool or an event-loop wait."""
    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    def _get_manager(manager_cls):
        # ConfigManager must come back as "no config available" (None) so
        # resolve_chart_size_defaults() exercises its documented
        # fallback-default branch -- a bare MagicMock() auto-vivifies a
        # truthy `.config.chart_display` whose numeric-looking attributes
        # (dpi, default_width_cm, ...) are themselves MagicMocks, which
        # matplotlib chokes on deep inside Bbox/transforms (see
        # test_headless_and_widget_canvas_render_equivalent_output in
        # test_render_chart_to_qimage.py).
        if manager_cls is ConfigManager:
            return None
        theme_manager = MagicMock()
        theme_manager.get_surface_palette.return_value = {}
        return theme_manager

    app_context.get_manager.side_effect = _get_manager

    def _run_task_synchronously(task, task_arguments=None, on_result=None, on_error=None, **kwargs):
        task_arguments = task_arguments or {}
        try:
            result = task(None, **task_arguments)
        except Exception as e:  # noqa: BLE001 -- mirrors TaskScheduler, which routes any task failure to on_error
            if on_error:
                on_error((type(e), e, ""))
            return
        if on_result:
            on_result(result)
        return

    fake_task_scheduler = MagicMock()
    fake_task_scheduler.run_task.side_effect = _run_task_synchronously
    app_context.get_task_scheduler.return_value = fake_task_scheduler
    return app_context


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

    with (
        patch("pandaplot.gui.components.tabs.note.note_editor.NoteImagePickerDialog", return_value=mock_dialog),
        patch.object(editor, "update_preview") as mock_update,
    ):
        editor.insert_image_from_picker()
        mock_update.assert_called_once()


def test_insert_chart_from_picker_inserts_static_snapshot(qapp):
    chart = Chart(name="Sample Plot")
    project = Project(name="Test Project")
    project.add_item(chart)

    app_context = _make_app_context_with_synchronous_task_scheduler(project)
    app_context.get_ui_controller.return_value = MagicMock()
    fake_executor = MagicMock()
    fake_executor.execute_command.side_effect = lambda command, **kwargs: command.execute().name == "SUCCESS"
    app_context.get_command_executor.return_value = fake_executor

    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
    mock_dialog.get_selected_chart.return_value = chart

    with patch("pandaplot.gui.dialogs.note.NoteChartPickerDialog", return_value=mock_dialog):
        editor.insert_chart_from_picker()

    content = editor.text_edit.toPlainText()
    # Not a reference to the chart's own id -- a newly created Image's id.
    assert chart.id not in content
    assert content.startswith("![Sample Plot](")
    assert content.endswith(" =500x)")

    inserted_id = content[len("![Sample Plot]("):-len(" =500x)")]
    inserted_image = project.find_item(inserted_id)
    from pandaplot.models.project.items import Image
    assert isinstance(inserted_image, Image)
    assert inserted_image.get_bytes() is not None


def test_save_chart_snapshot_image_stamps_note_id(qapp):
    chart = Chart(name="Sample Plot")
    project = Project(name="Test Project")
    project.add_item(chart)

    app_context = _make_app_context_with_synchronous_task_scheduler(project)
    app_context.get_ui_controller.return_value = MagicMock()
    fake_executor = MagicMock()
    fake_executor.execute_command.side_effect = lambda command, **kwargs: command.execute().name == "SUCCESS"
    app_context.get_command_executor.return_value = fake_executor

    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)

    image_id = editor._save_chart_snapshot_image(chart, _rendered_snapshot(20, 20))

    assert image_id is not None
    created_image = project.find_item(image_id)
    assert created_image.note_id == note.id


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


def test_note_editor_insert_chart_uses_shared_width_constant(qapp):
    """Chart insertion must size from the same constant image insertion uses,
    not a hardcoded duplicate, so the two stay in sync if it's ever tuned."""
    chart = Chart(name="Sample Plot")
    project = Project(name="Test Project")
    project.add_item(chart)
    app_context = _app_context_with_executing_command_executor(project)

    editor = NoteEditorWidget(app_context=app_context, note=Note(name="Note 1", content=""), parent=None)

    mock_dialog = MagicMock()
    mock_dialog.exec.return_value = QDialog.DialogCode.Accepted
    mock_dialog.get_selected_chart.return_value = chart

    with patch("pandaplot.gui.dialogs.note.NoteChartPickerDialog", return_value=mock_dialog), patch(
        "pandaplot.gui.components.tabs.note.note_editor._DEFAULT_INSERT_MAX_WIDTH", 777
    ):
        editor.insert_chart_from_picker()

    assert editor.text_edit.toPlainText().endswith(" =777x)")


def test_find_chart_snapshot_gallery_id_finds_the_gallery_in_the_notes_folder(qapp):
    project = Project(name="Test Project")
    folder = Folder(name="Notes Folder")
    project.add_item(folder)
    existing_gallery = ImageGallery(name="Chart Snapshots")
    project.add_item(existing_gallery, parent_id=folder.id)

    assert find_chart_snapshot_gallery_id(project, folder.id) == existing_gallery.id
    assert find_chart_snapshot_gallery_id(project, None) is None


def test_first_chart_snapshot_insert_creates_gallery_and_image_as_one_undo_step(qapp):
    from pandaplot.commands.composite_command import CompositeCommand

    chart = Chart(name="Plot")
    folder = Folder(name="Notes Folder")
    project = Project(name="Test Project")
    project.add_item(folder)
    project.add_item(chart)
    app_context = _app_context_with_executing_command_executor(project)
    executed = []
    real_side_effect = app_context.get_command_executor.return_value.execute_command.side_effect

    def _record(command, **kwargs):
        executed.append(command)
        return real_side_effect(command, **kwargs)

    app_context.get_command_executor.return_value.execute_command.side_effect = _record
    note = Note(name="Note 1", content="")
    note.parent_id = folder.id
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)

    image_id = editor._save_chart_snapshot_image(chart, _rendered_snapshot(2, 2))

    assert len(executed) == 1 and isinstance(executed[0], CompositeCommand)
    image = project.find_item(image_id)
    gallery = project.find_item(image.parent_id)
    assert gallery.name == "Chart Snapshots" and gallery.parent_id == folder.id

    assert executed[0].undo() is CommandResult.SUCCESS
    assert project.find_item(image_id) is None
    assert project.find_item(gallery.id) is None  # no empty gallery left behind

def test_note_editor_chart_does_not_shadow_gallery_image_with_identical_exact_path(qapp):
    """Even the chart's *exact* gallery path (not just a bare-name alias)
    can collide with an unrelated image's: item names aren't unique across
    types, so a Chart literally named "Plot.png" has the same gallery path
    as an Image named "Plot.png". The eager registration pass has no
    "first match wins" protection (addResource overwrites regardless of
    order), so charts must only be eagerly registered by id, not by path
    (see PR #383 review)."""
    image = Image(name="Plot.png")
    chart = Chart(name="Plot.png")
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

    cache = {chart.id: chart_qimg}
    with patch(
        "pandaplot.gui.components.tabs.note.note_editor.load_qimage_for_item", return_value=image_qimg
    ):
        register_project_image_resources(doc, app_context, cache)

    res = doc.resource(QTextDocument.ResourceType.ImageResource, QUrl("Plot.png"))
    assert res.width() == 10  # still the gallery image, not overwritten by the chart


def test_insert_chart_snapshot_noops_if_note_editor_deleted_before_render_completes(qapp):
    """If the note tab is closed while a chart-snapshot render is still in
    flight, the result callback must not create an orphaned gallery/image
    (nothing would reference it -- the insertion point is gone too), and
    must not raise touching the deleted text_edit."""
    import shiboken6

    chart = Chart(name="Chart A")
    project = Project(name="Test Project")
    project.add_item(chart)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    captured = {}

    def fake_run_task(task, task_arguments=None, on_result=None, on_error=None, **kwargs):
        captured["on_result"] = on_result

    fake_task_scheduler = MagicMock()
    fake_task_scheduler.run_task.side_effect = fake_run_task
    app_context.get_task_scheduler.return_value = fake_task_scheduler

    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)

    editor._insert_chart_snapshot(chart)
    assert "on_result" in captured

    with patch.object(editor, "_save_chart_snapshot_image") as mock_save:
        shiboken6.delete(editor)
        captured["on_result"](_rendered_snapshot(5, 5))  # must not raise
        mock_save.assert_not_called()


def test_compute_note_artefact_rows_classifies_snapshot_image_reference(qapp):
    project = Project(name="Test Project")
    gallery = ImageGallery(name="Chart Snapshots")
    project.add_item(gallery)
    image = Image(name="Snapshot", note_id="note-1")
    project.add_item(image, parent_id=gallery.id)
    note = Note(id="note-1", name="Note 1", content=f"![Snapshot]({image.id} =500x)")

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    rows = compute_note_artefact_rows(app_context, note, note.content)

    assert len(rows) == 1
    row = rows[0]
    assert row.kind == "image"
    assert row.status == "ok"
    assert row.is_snapshot is True
    assert row.item_id == image.id


def test_compute_note_artefact_rows_flags_broken_reference(qapp):
    project = Project(name="Test Project")
    note = Note(name="Note 1", content="![Gone](missing-id =500x)")

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    rows = compute_note_artefact_rows(app_context, note, note.content)

    assert len(rows) == 1
    row = rows[0]
    assert row.kind == "unknown"
    assert row.status == "broken"
    assert row.item_id is None
    assert row.is_snapshot is False


def test_compute_note_artefact_rows_flags_unused_snapshot_not_in_text(qapp):
    project = Project(name="Test Project")
    gallery = ImageGallery(name="Chart Snapshots")
    project.add_item(gallery)
    image = Image(name="Orphan Snapshot", note_id="note-1")
    project.add_item(image, parent_id=gallery.id)
    note = Note(id="note-1", name="Note 1", content="No references here.")

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    rows = compute_note_artefact_rows(app_context, note, note.content)

    assert len(rows) == 1
    row = rows[0]
    assert row.kind == "image"
    assert row.status == "unused"
    assert row.is_snapshot is True
    assert row.item_id == image.id
    assert row.match_start is None
    assert row.match_end is None


def test_compute_note_artefact_rows_excludes_snapshot_owned_by_a_different_note(qapp):
    project = Project(name="Test Project")
    gallery = ImageGallery(name="Chart Snapshots")
    project.add_item(gallery)
    image = Image(name="Someone Else's Snapshot", note_id="other-note")
    project.add_item(image, parent_id=gallery.id)
    note = Note(id="note-1", name="Note 1", content="No references here.")

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    rows = compute_note_artefact_rows(app_context, note, note.content)

    assert rows == []


def test_compute_note_artefact_rows_marks_referenced_plain_gallery_image_as_not_a_snapshot(qapp):
    project = Project(name="Test Project")
    gallery = ImageGallery(name="My Photos")
    project.add_item(gallery)
    image = Image(name="Photo")  # note_id stays None -- an ordinary gallery image
    project.add_item(image, parent_id=gallery.id)
    note = Note(name="Note 1", content=f"![Photo]({image.id} =500x)")

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    rows = compute_note_artefact_rows(app_context, note, note.content)

    assert len(rows) == 1
    assert rows[0].is_snapshot is False


def test_compute_note_artefact_rows_match_offsets_survive_a_preceding_code_span(qapp):
    chart = Chart(name="Line Plot")
    project = Project(name="Test Project")
    project.add_item(chart)
    content = f"Here is `inline code` then\n\n![Line Plot]({chart.id} =500x)"
    note = Note(name="Note 1", content=content)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    rows = compute_note_artefact_rows(app_context, note, content)

    assert len(rows) == 1
    row = rows[0]
    assert content[row.match_start:row.match_end] == f"![Line Plot]({chart.id} =500x)"


def test_compute_note_artefact_rows_resolves_real_on_disk_file_as_ok(qapp, tmp_path):
    project = Project(name="Test Project")
    project.project_file_path = str(tmp_path / "project.ppf")
    image_path = tmp_path / "local.png"
    image_path.write_bytes(create_test_png_bytes())
    note = Note(name="Note 1", content="![Local](local.png)")

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    rows = compute_note_artefact_rows(app_context, note, note.content)

    assert len(rows) == 1
    row = rows[0]
    assert row.kind == "file"
    assert row.status == "ok"
    assert row.is_snapshot is False
    assert row.item_id is None


def test_compute_note_artefact_rows_does_not_flag_reference_style_snapshot_as_unused(qapp):
    project = Project(name="Test Project")
    gallery = ImageGallery(name="Chart Snapshots")
    project.add_item(gallery)
    image = Image(name="Snapshot", note_id="note-1")
    project.add_item(image, parent_id=gallery.id)
    content = f"![alt][plot]\n\n[plot]: <{image.id}>"
    note = Note(id="note-1", name="Note 1", content=content)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    rows = compute_note_artefact_rows(app_context, note, content)

    assert rows == []


def test_toolbar_has_artefacts_action_instead_of_separate_insert_actions(qapp):
    project = Project(name="Test Project")
    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)

    action_texts = [action.text() for action in editor.toolbar.actions()]
    assert not any("Insert Chart" in text for text in action_texts)
    assert not any("Insert Table" in text for text in action_texts)
    assert any("Artefacts" in text for text in action_texts)


def test_artefacts_badge_shows_no_marker_when_no_issues(qapp, qtbot):
    gallery = ImageGallery(name="Gallery")
    image = Image(name="Line Plot")
    project = Project(name="Test Project")
    project.add_item(gallery)
    project.add_item(image, parent_id=gallery.id)
    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="Note 1", content=f"![Line Plot]({image.id} =500x)")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    qtbot.wait(600)  # past the debounce delay

    assert "•" not in editor.artefacts_action.text()


def test_artefacts_badge_shows_marker_when_reference_is_broken(qapp, qtbot):
    project = Project(name="Test Project")
    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="Note 1", content="![Gone](missing-id =500x)")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    qtbot.wait(600)  # past the debounce delay

    assert "•" in editor.artefacts_action.text()


def test_artefacts_badge_updates_as_content_changes(qapp, qtbot):
    project = Project(name="Test Project")
    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    qtbot.wait(600)  # past the debounce delay
    assert "•" not in editor.artefacts_action.text()

    editor.text_edit.setPlainText("![Gone](missing-id =500x)")
    qtbot.wait(600)  # past the debounce delay

    assert "•" in editor.artefacts_action.text()


def test_content_changed_debounces_artefacts_badge_refresh(qapp, qtbot):
    """on_content_changed fires on every keystroke via textChanged;
    _refresh_artefacts_badge does real filesystem checks and an
    O(references x project items) scan, so it must be debounced rather
    than run synchronously on every edit (mirrors
    test_chart_or_dataset_change_debounces_preview_refresh above)."""
    project = Project(name="Test Project")
    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}

    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    qtbot.wait(600)  # let the initial-load debounce settle before measuring

    with patch.object(editor, "_refresh_artefacts_badge") as mock_refresh:
        for _ in range(5):
            editor.text_edit.insertPlainText("x")
        mock_refresh.assert_not_called()  # debounced, not synchronous
        qtbot.wait(600)  # past the debounce delay
        mock_refresh.assert_called_once()


def test_dispatch_headless_chart_render_hands_worker_a_snapshot_not_the_live_chart():
    """The worker thread must not read a Chart the GUI thread can keep
    editing while the render is in flight."""
    from pandaplot.gui.components.tabs.note.note_editor import dispatch_headless_chart_render

    chart = Chart(name="Chart A")
    chart.config.title = "Before"
    project = Project(name="Test Project")
    project.add_item(chart)

    app_context = MagicMock()
    app_context.get_app_state.return_value.current_project = project
    app_context.get_manager.return_value = None
    captured = {}
    app_context.get_task_scheduler.return_value.run_task.side_effect = (
        lambda task, task_arguments=None, **_kwargs: captured.update(task_arguments))

    dispatch_headless_chart_render(app_context, chart, on_result=lambda _qimg: None)
    chart.config.title = "After"

    assert captured["chart"] is not chart
    assert captured["chart"].id == chart.id
    assert captured["chart"].config.title == "Before"


def test_insert_chart_snapshot_warns_when_render_fails(qapp):
    chart = Chart(name="Sample Plot")
    project = Project(name="Test Project")
    project.add_item(chart)

    app_context = _make_app_context_with_synchronous_task_scheduler(project)
    ui_controller = MagicMock()
    app_context.get_ui_controller.return_value = ui_controller

    editor = NoteEditorWidget(app_context=app_context, note=Note(name="Note 1", content=""), parent=None)

    with patch("pandaplot.gui.components.tabs.chart.chart_editor.render_chart_to_png", return_value=None):
        editor._insert_chart_snapshot(chart)

    ui_controller.show_warning_message.assert_called_once()
    assert editor.text_edit.toPlainText() == ""


def test_chart_snapshot_image_name_disambiguates_same_named_charts(qapp):
    folder_a = Folder(name="A")
    folder_b = Folder(name="B")
    chart_a = Chart(name="Plot")
    chart_b = Chart(name="Plot")
    project = Project(name="Test Project")
    project.add_item(folder_a)
    project.add_item(folder_b)
    project.add_item(chart_a, parent_id=folder_a.id)
    project.add_item(chart_b, parent_id=folder_b.id)

    app_context = _make_app_context_with_synchronous_task_scheduler(project)
    captured = []
    fake_executor = MagicMock()
    fake_executor.execute_command.side_effect = lambda command, **kwargs: captured.append(command) or True
    app_context.get_command_executor.return_value = fake_executor
    editor = NoteEditorWidget(app_context=app_context, note=Note(name="Note 1", content=""), parent=None)

    with patch("pandaplot.gui.components.tabs.note.note_editor.find_chart_snapshot_gallery_id", return_value="gallery-id"):
        editor._save_chart_snapshot_image(chart_a, _rendered_snapshot(2, 2))
        editor._save_chart_snapshot_image(chart_b, _rendered_snapshot(2, 2))

    assert captured[0].name != captured[1].name


def _app_context_with_executing_command_executor(project):
    app_context = _make_app_context_with_synchronous_task_scheduler(project)
    app_context.get_ui_controller.return_value = MagicMock()
    fake_executor = MagicMock()
    fake_executor.execute_command.side_effect = lambda command, **kwargs: command.execute() is CommandResult.SUCCESS
    app_context.get_command_executor.return_value = fake_executor
    return app_context


def test_refresh_chart_snapshot_replaces_the_image_contents_from_the_source_chart(qapp):
    chart = Chart(name="Sample Plot")
    gallery = ImageGallery(name="Chart Snapshots")
    image = Image(name="Sample Plot", note_id="note-1", source_chart_id=chart.id, width=1, height=1)
    image.set_bytes(b"stale")
    project = Project(name="Test Project")
    for item in (chart, gallery):
        project.add_item(item)
    project.add_item(image, parent_id=gallery.id)
    app_context = _app_context_with_executing_command_executor(project)
    editor = NoteEditorWidget(app_context=app_context, note=Note(id="note-1", name="Note 1", content=""), parent=None)

    rendered = create_test_png_bytes(width=30, height=20)
    with patch("pandaplot.gui.components.tabs.chart.chart_editor.render_chart_to_png", return_value=rendered):
        editor.refresh_chart_snapshot(image.id)

    assert image.get_bytes() != b"stale"
    assert (image.width, image.height) == (30, 20)


def test_refresh_chart_snapshot_warns_when_the_source_chart_is_gone(qapp):
    gallery = ImageGallery(name="Chart Snapshots")
    image = Image(name="Orphan", note_id="note-1", source_chart_id="deleted-chart")
    image.set_bytes(b"stale")
    project = Project(name="Test Project")
    project.add_item(gallery)
    project.add_item(image, parent_id=gallery.id)
    app_context = _app_context_with_executing_command_executor(project)
    editor = NoteEditorWidget(app_context=app_context, note=Note(id="note-1", name="Note 1", content=""), parent=None)

    editor.refresh_chart_snapshot(image.id)

    app_context.get_ui_controller().show_warning_message.assert_called_once()
    assert image.get_bytes() == b"stale"


def _snapshot_project():
    chart = Chart(name="Sample Plot")
    gallery = ImageGallery(name="Chart Snapshots")
    image = Image(name="Sample Plot", note_id="note-1", source_chart_id=chart.id, width=1, height=1)
    image.set_bytes(b"stale")
    project = Project(name="Test Project")
    project.add_item(chart)
    project.add_item(gallery)
    project.add_item(image, parent_id=gallery.id)
    return project, image


def test_refresh_chart_snapshot_ignores_a_second_request_while_one_is_pending(qapp):
    project, image = _snapshot_project()
    app_context = _app_context_with_executing_command_executor(project)
    pending = []
    app_context.get_task_scheduler.return_value.run_task.side_effect = (
        lambda task, task_arguments=None, on_result=None, on_error=None, **_kw: pending.append(on_result))
    editor = NoteEditorWidget(app_context=app_context, note=Note(id="note-1", name="Note 1", content=""), parent=None)
    finished = []

    editor.refresh_chart_snapshot(image.id, on_done=lambda: finished.append(True))
    editor.refresh_chart_snapshot(image.id)

    assert len(pending) == 1  # the duplicate request never dispatched a second render
    pending[0](_rendered_snapshot(8, 8))
    assert finished == [True]
    assert image.get_bytes() != b"stale"
    editor.refresh_chart_snapshot(image.id)
    assert len(pending) == 2  # allowed again once the first one finished


def test_refresh_chart_snapshot_warns_when_the_snapshot_is_deleted_while_rendering(qapp):
    project, image = _snapshot_project()
    app_context = _app_context_with_executing_command_executor(project)
    pending = []
    app_context.get_task_scheduler.return_value.run_task.side_effect = (
        lambda task, task_arguments=None, on_result=None, on_error=None, **_kw: pending.append(on_result))
    editor = NoteEditorWidget(app_context=app_context, note=Note(id="note-1", name="Note 1", content=""), parent=None)

    editor.refresh_chart_snapshot(image.id)
    project.remove_item(image)
    pending[0](_rendered_snapshot(8, 8))

    app_context.get_ui_controller().show_warning_message.assert_called_once()


def test_refresh_chart_snapshot_warns_when_the_replace_command_fails(qapp):
    project, image = _snapshot_project()
    app_context = _app_context_with_executing_command_executor(project)
    app_context.get_command_executor.return_value.execute_command.side_effect = lambda command, **kwargs: False
    editor = NoteEditorWidget(app_context=app_context, note=Note(id="note-1", name="Note 1", content=""), parent=None)

    with patch(
        "pandaplot.gui.components.tabs.chart.chart_editor.render_chart_to_png",
        return_value=create_test_png_bytes(width=8, height=8),
    ):
        editor.refresh_chart_snapshot(image.id)

    app_context.get_ui_controller().show_warning_message.assert_called_once()


def test_refresh_chart_snapshot_calls_on_done_for_a_dropped_duplicate_request(qapp):
    """A caller that disabled its trigger must get it back even when its
    request is ignored because the same snapshot is already refreshing."""
    project, image = _snapshot_project()
    app_context = _app_context_with_executing_command_executor(project)
    app_context.get_task_scheduler.return_value.run_task.side_effect = lambda *args, **kwargs: None
    editor = NoteEditorWidget(app_context=app_context, note=Note(id="note-1", name="Note 1", content=""), parent=None)
    finished = []

    editor.refresh_chart_snapshot(image.id)
    editor.refresh_chart_snapshot(image.id, on_done=lambda: finished.append(True))

    assert finished == [True]


def test_refresh_chart_snapshot_render_failure_says_refresh_not_insert(qapp):
    project, image = _snapshot_project()
    app_context = _app_context_with_executing_command_executor(project)
    editor = NoteEditorWidget(app_context=app_context, note=Note(id="note-1", name="Note 1", content=""), parent=None)

    with patch("pandaplot.gui.components.tabs.chart.chart_editor.render_chart_to_png", return_value=None):
        editor.refresh_chart_snapshot(image.id)

    title, _message = app_context.get_ui_controller().show_warning_message.call_args.args
    assert title == "Refresh Chart Snapshot"
    assert image.get_bytes() == b"stale"


def test_insert_chart_snapshot_discards_the_render_if_the_project_changed(qapp):
    """The snapshot belongs to the project the insert started in; saving it
    into whichever project is current when the render lands would put it in
    the wrong one."""
    chart = Chart(name="Chart A")
    project = Project(name="Test Project")
    project.add_item(chart)
    app_context = _app_context_with_executing_command_executor(project)
    captured = {}
    app_context.get_task_scheduler.return_value.run_task.side_effect = (
        lambda task, task_arguments=None, on_result=None, on_error=None, **_kw: captured.update(on_result=on_result))
    editor = NoteEditorWidget(app_context=app_context, note=Note(name="Note 1", content=""), parent=None)

    editor._insert_chart_snapshot(chart)
    other_project = Project(name="Other Project")
    app_context.get_app_state.return_value.current_project = other_project
    with patch.object(editor, "_save_chart_snapshot_image") as mock_save:
        captured["on_result"](_rendered_snapshot(5, 5))

    mock_save.assert_not_called()
    assert other_project.get_all_items() == []
    assert editor.text_edit.toPlainText() == ""
    app_context.get_ui_controller().show_warning_message.assert_called_once()


def test_dispatch_headless_chart_render_delivers_png_bytes_and_their_size(qapp):
    from pandaplot.gui.components.tabs.note.note_editor import dispatch_headless_chart_render

    chart = Chart(name="Chart A")
    project = Project(name="Test Project")
    project.add_item(chart)
    app_context = _make_app_context_with_synchronous_task_scheduler(project)
    png_bytes = create_test_png_bytes(width=30, height=20)
    results = []

    with patch("pandaplot.gui.components.tabs.chart.chart_editor.render_chart_to_png", return_value=png_bytes):
        dispatch_headless_chart_render(app_context, chart, on_result=results.append)

    assert results == [RenderedChartSnapshot(png_bytes=png_bytes, width=30, height=20)]


def test_artefacts_badge_updates_after_an_external_content_change(qapp, qtbot):
    """Undo/redo of a note edit replaces the editor text with signals
    blocked, so on_content_changed never runs; the badge must still follow."""
    project = Project(name="Test Project")
    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state
    app_context.get_manager.return_value.get_surface_palette.return_value = {}
    note = Note(name="Note 1", content="")
    editor = NoteEditorWidget(app_context=app_context, note=note, parent=None)
    qtbot.wait(600)  # past the debounce delay
    assert "•" not in editor.artefacts_action.text()

    editor.on_note_content_changed_event({"note_id": note.id, "new_content": "![Gone](missing-id =500x)"})
    qtbot.wait(600)  # past the debounce delay

    assert "•" in editor.artefacts_action.text()


def test_compute_note_artefact_rows_does_not_offer_deleting_a_snapshot_another_note_uses(qapp):
    """Deleting an "unused" snapshot removes the Image project-wide, so one
    still referenced from a different note must not be listed as unused."""
    project = Project(name="Test Project")
    gallery = ImageGallery(name="Chart Snapshots")
    project.add_item(gallery)
    image = Image(name="Snapshot", note_id="note-1")
    project.add_item(image, parent_id=gallery.id)
    note = Note(id="note-1", name="Note 1", content="Reference removed here.")
    other_note = Note(id="note-2", name="Note 2", content=f"Copied: ![Snapshot]({image.id} =500x)")
    project.add_item(note)
    project.add_item(other_note)

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    assert compute_note_artefact_rows(app_context, note, note.content) == []


def test_compute_note_artefact_rows_resolves_local_files_the_way_the_preview_does(qapp, tmp_path):
    """Percent-encoded and file:// references to a real file render in the
    preview, so they must not be flagged as broken."""
    project = Project(name="Test Project")
    project.project_file_path = str(tmp_path / "project.ppf")
    image_path = tmp_path / "my plot.png"
    image_path.write_bytes(create_test_png_bytes())
    file_url = QUrl.fromLocalFile(str(image_path)).toString(QUrl.ComponentFormattingOption.FullyEncoded)
    note = Note(name="Note 1", content=f"![A](my%20plot.png)\n![B]({file_url})")

    app_context = MagicMock()
    app_state = MagicMock()
    app_state.current_project = project
    app_context.get_app_state.return_value = app_state

    rows = compute_note_artefact_rows(app_context, note, note.content)

    assert [(row.kind, row.status) for row in rows] == [("file", "ok"), ("file", "ok")]
