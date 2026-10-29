"""
Note tab widget for displaying and editing notes in the main tab container.
"""
import copy
import logging
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import override
from urllib.parse import unquote

from PySide6.QtCore import QBuffer, QIODevice, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QFont, QImage, QKeySequence, QTextCursor, QTextDocument
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QSplitter,
    QStackedWidget,
    QTextBrowser,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from pandaplot.commands.project.note import EditNoteCommand
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.gui.dialogs.image.note_image_picker_dialog import NoteImagePickerDialog
from pandaplot.models.events import NoteEvents, UIEvents
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import Chart, Image, ImageGallery, ItemCollection, Note
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.note_render.latex_markdown_renderer import (
    code_region_spans,
    is_escaped_at,
    protect_code_regions,
    render_body_html,
    wrap_document,
)
from pandaplot.services.theme.theme_manager import ThemeManager
from pandaplot.utils.item_display_options import chart_display_options

# Point size used both for the editor font and for rasterising equations so
# the math visually matches the surrounding text.
_NOTE_FONT_SIZE = 11

# Matches a Markdown inline image link's target, e.g. "id" in
# "![alt](id =300x200)". Group 1 handles the angle-bracket form for a target
# containing spaces (`![alt](<my id> =300x200)`); group 2 is the bare form,
# which stops at the first whitespace so a trailing size modifier isn't
# swept in. Whether the leading "!" is itself escaped is checked separately
# via `is_escaped_at` (Markdown backslash rules need to look at an arbitrary
# run of preceding backslashes, not just one character).
_IMAGE_REF_RE = re.compile(r"!\[[^\]]*\]\(\s*(?:<([^>]*)>|([^\s)]+))")

# Same inline-image-link shape as _IMAGE_REF_RE, but the match is the
# *entire* "![alt](target)" (optionally "![alt](target =WxH)") construct,
# not just the target -- so the match span can be used to delete the whole
# reference from note text (see compute_note_artefact_rows / NoteArtefactsDialog).
# Reference-style links (![alt][label] + a separate [label]: target
# definition) aren't matched here: every insertion this app performs uses
# the inline form, so a reference-style link is only ever hand-written --
# out of scope for the artefacts-management delete action.
_IMAGE_MARKDOWN_RE = re.compile(
    r"!\[[^\]]*\]\(\s*(?:<([^>]*)>|([^\s)]+))(?:\s+=\d*x\d*)?\s*\)"
)

# Reference-style image link, e.g. "![alt][plot]" (or the collapsed
# "![alt][]", whose label is `alt` itself) paired with a definition elsewhere
# in the note like "[plot]: image-id". Both are valid Markdown that renders
# an <img>, so a note using this style must still have its target counted as
# referenced.
_IMAGE_REF_LABEL_RE = re.compile(r"!\[([^\]]*)\]\[([^\]]*)\]")
_LINK_DEFINITION_RE = re.compile(r"^[ \t]{0,3}\[([^\]]+)\]:\s*(?:<([^>]*)>|(\S+))", re.MULTILINE)

# Default cap applied to a gallery image's width when inserted via the picker,
# so a large photo doesn't blow out the note by default. The user can still
# edit/remove the `=WxH` modifier by hand.
_DEFAULT_INSERT_MAX_WIDTH = 500

logger = logging.getLogger(__name__)

# How long to wait, after the last chart/dataset change event, before
# actually re-rendering the preview -- coalesces rapid-fire edits (typing
# into a linked dataset cell fires one of these per keystroke/commit) into a
# single synchronous chart re-render instead of one per edit.
_ARTEFACTS_BADGE_REFRESH_DEBOUNCE_MS = 400


def get_project_base_dir(app_context: AppContext) -> str:
    """Get base directory for relative path resolution based on current project path."""
    try:
        app_state = app_context.get_app_state() if app_context else None
        project = app_state.current_project if app_state else None
        if project and project.project_file_path:
            return os.path.dirname(os.path.abspath(project.project_file_path))
    except Exception:
        logger.debug("Could not resolve project base dir; falling back to cwd", exc_info=True)
    return os.getcwd()


_CHART_SNAPSHOT_GALLERY_NAME = "Chart Snapshots"


def find_or_create_chart_snapshot_gallery(app_context: AppContext, folder_id: str | None) -> str | None:
    """Return the id of the "Chart Snapshots" gallery inside `folder_id`
    (the note's own parent folder, or None for project root), creating one
    if it doesn't already exist there. Returns None if there's no current
    project or the gallery couldn't be created."""
    from pandaplot.commands.project.image.create_image_gallery_command import CreateImageGalleryCommand
    from pandaplot.models.project.items import ImageGallery

    app_state = app_context.get_app_state() if app_context else None
    project = app_state.current_project if app_state else None
    if project is None:
        return None

    for item in project.get_all_items():
        if isinstance(item, ImageGallery) and item.parent_id == folder_id and item.name == _CHART_SNAPSHOT_GALLERY_NAME:
            return item.id

    command = CreateImageGalleryCommand(app_context, gallery_name=_CHART_SNAPSHOT_GALLERY_NAME, parent_id=folder_id)
    succeeded = app_context.get_command_executor().execute_command(command, track_undo=True)
    return command.created_gallery_id if succeeded else None


def _qimage_to_png_bytes(qimg: QImage) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    qimg.save(buf, "PNG")
    return bytes(buf.data())


def get_image_gallery_path(project, image_item: Image) -> str:
    """Get gallery-relative path for an Image item (e.g. 'Album/Photo.png' or 'Photo.png')."""
    if project is None or image_item is None:
        return ""
    folder_path = project.get_folder_path(image_item.id)
    if folder_path:
        return "/".join(folder_path) + "/" + image_item.name
    return image_item.name


def _resolve_chart_render_inputs(app_context: AppContext, chart_item: Chart):
    """Snapshot `chart_item`'s series data (on the GUI thread) and resolve
    its chart-size defaults, ready to hand to `render_chart_to_qimage`.

    Shared by `dispatch_headless_chart_render` (async, off the GUI thread)
    and `_render_charts_synchronously_for_export` (sync, for PDF export) so
    this resolve+copy sequence exists exactly once. Note this only resolves
    inputs -- it doesn't render, so callers decide whether that happens on
    a worker thread or inline.
    """
    from pandaplot.gui.components.tabs.chart.chart_editor import (
        resolve_chart_series_data,
        resolve_chart_size_defaults,
    )

    app_state = app_context.get_app_state() if app_context else None
    project = app_state.current_project if app_state else None
    resolved_series_data = [
        data.copy() for data in resolve_chart_series_data(project, chart_item)
    ]
    size_defaults = resolve_chart_size_defaults(app_context)
    return resolved_series_data, size_defaults


def dispatch_headless_chart_render(
    app_context: AppContext, chart_item: Chart,
    *, on_result: Callable[[QImage | None], None], on_error: Callable | None = None,
) -> None:
    """Snapshot `chart_item`'s series data on the GUI thread, then render
    it to a QImage on a TaskScheduler worker thread, delivering the result
    (or a failure) back via `on_result`/`on_error` on the GUI thread.

    Shared by every headless-chart-render call site (snapshot insertion and
    snapshot refresh) so the resolve/copy/dispatch boilerplate exists
    exactly once. Callers own whatever they do with the result (create or
    update an Image) -- this function only handles getting a QImage off the
    GUI thread and back.
    """
    from pandaplot.gui.components.tabs.chart.chart_editor import render_chart_to_qimage

    resolved_series_data, size_defaults = _resolve_chart_render_inputs(app_context, chart_item)
    # The worker reads the chart's config/style/series while the GUI thread
    # may keep editing the live one, so it gets a copy taken now.
    chart_snapshot = copy.copy(chart_item)
    chart_snapshot.config = copy.deepcopy(chart_item.config)
    chart_snapshot.style = copy.deepcopy(chart_item.style)
    chart_snapshot.data_series = [copy.deepcopy(series) for series in chart_item.data_series]

    def _render_task(progress_callback, chart, resolved_data, size_defs):
        del progress_callback  # unused; required by the Worker call signature
        return render_chart_to_qimage(chart, resolved_data, size_defs)

    app_context.get_task_scheduler().run_task(
        task=_render_task,
        task_arguments={"chart": chart_snapshot, "resolved_data": resolved_series_data, "size_defs": size_defaults},
        on_result=on_result,
        on_error=on_error,
    )


def load_qimage_for_item(image_item: Image) -> QImage | None:
    """Load QImage from Image item bytes or source file.

    Hits the network/disk for "external" images, so callers on a hot path
    (every keystroke) should go through `get_cached_qimage` instead.
    """
    try:
        data = image_item.get_bytes()
        if data is None and image_item.source_file:
            source = image_item.source_file
            if source.startswith(("http://", "https://")):
                import requests
                resp = requests.get(source, timeout=5)
                resp.raise_for_status()
                data = resp.content
            elif os.path.isfile(source):
                with open(source, "rb") as f:
                    data = f.read()
        if data:
            qimg = QImage()
            if qimg.loadFromData(data):
                return qimg
    except Exception:
        logger.debug("Could not load image bytes for note preview", exc_info=True)
    return None


def get_cached_qimage(image_item: Image, cache: dict[str, QImage | None]) -> QImage | None:
    """Load an Image item's QImage, memoised by id in `cache`.

    Avoids re-decoding bytes (and re-fetching external URLs/files) on every
    call -- `register_project_image_resources` runs on every keystroke while
    editing in split/preview mode. Failed loads are cached too (as None) so a
    broken external reference doesn't retry the network on every render;
    callers clear the cache when project images actually change.
    """
    if image_item.id in cache:
        return cache[image_item.id]
    qimg = load_qimage_for_item(image_item)
    cache[image_item.id] = qimg
    return qimg


def _add_key_and_decoded(keys: set[str], target: str | None) -> None:
    if not target:
        return
    keys.add(target)
    decoded = unquote(target)
    if decoded != target:
        keys.add(decoded)


def extract_referenced_image_keys(source: str) -> set[str]:
    """Return the set of image link targets referenced in note `source`.

    Used to skip loading/registering gallery images that the note doesn't
    actually reference, rather than eagerly resolving every image in the
    project on each render. Handles inline links (bare and angle-bracket
    (`<target with spaces>`) target forms) and reference-style links
    (`![alt][label]` / `![alt][]` plus a `[label]: target` definition
    elsewhere in the note) -- both are valid Markdown that renders an
    <img>. Each target's percent-decoded form is included too (gallery keys
    like "Album/Photo.png" are stored unencoded, so a note written as
    "Album%2FPhoto.png" would otherwise never match).

    Image-shaped text inside a fenced/inline code span, or escaped with a
    leading "\\!", is not a real reference (Markdown renders neither as an
    <img>), so both are excluded the same way the renderer excludes them
    from size-modifier handling -- otherwise an unrelated code example or
    escaped image could trigger decoding, or a synchronous network fetch, of
    a same-named external gallery image.
    """
    protected_source, _, _ = protect_code_regions(source)
    keys: set[str] = set()

    for match in _IMAGE_REF_RE.finditer(protected_source):
        if is_escaped_at(protected_source, match.start()):
            continue
        target = match.group(1) if match.group(1) is not None else match.group(2)
        _add_key_and_decoded(keys, target)

    definitions: dict[str, str] = {}
    for def_match in _LINK_DEFINITION_RE.finditer(protected_source):
        target = def_match.group(2) if def_match.group(2) is not None else def_match.group(3)
        if target:
            definitions[def_match.group(1).lower()] = target

    for ref_match in _IMAGE_REF_LABEL_RE.finditer(protected_source):
        if is_escaped_at(protected_source, ref_match.start()):
            continue
        alt, label = ref_match.groups()
        target = definitions.get((label or alt).lower())
        _add_key_and_decoded(keys, target)

    return keys


@dataclass
class NoteArtefactRow:
    """One row for NoteArtefactsDialog / the toolbar badge: either an image
    reference found in the note's current markdown text, or an orphaned
    snapshot Image this note created that's no longer referenced there."""
    name: str
    kind: str  # "image", "file" (a real on-disk file), or "unknown" (couldn't resolve the target)
    status: str  # "ok", "unused", or "broken"
    is_snapshot: bool  # True only for an Image with note_id == this note's id
    match_start: int | None  # start offset of the full markdown reference in `source`, or None (unused row)
    match_end: int | None  # end offset, or None (unused row)
    item_id: str | None  # resolved Image id, or None (broken row)
    refreshable: bool = False  # True for a chart snapshot whose source chart still exists


def _snapshot_source_chart(project, image: Image) -> Chart | None:
    """The Chart `image` (a chart snapshot) was rendered from, or None if it
    isn't a snapshot or the chart is gone."""
    if not image.source_chart_id:
        return None
    chart = project.find_item(image.source_chart_id)
    return chart if isinstance(chart, Chart) else None


def _resolve_note_reference_target(app_context: AppContext, project, target: str):
    """Return (kind, resolved_item) for a raw markdown reference target:
    ("file", None) if it resolves to a real file on disk (mirrors
    NotePreviewBrowser's own local-file-wins-over-gallery precedent);
    ("image", Image) if it matches an Image's id or exact gallery path (checking both the raw and
    percent-decoded form, mirroring register_project_image_resources);
    otherwise ("unknown", None)."""
    base_dir = get_project_base_dir(app_context)
    local_path = os.path.join(base_dir, target) if base_dir else target
    if os.path.isfile(local_path):
        return "file", None
    if project is None:
        return "unknown", None
    decoded = unquote(target)
    for item in project.get_all_items():
        if isinstance(item, Image):
            gallery_path = get_image_gallery_path(project, item)
            if target in (item.id, gallery_path) or decoded in (item.id, gallery_path):
                return "image", item
    return "unknown", None


def compute_note_artefact_rows(app_context: AppContext, note: Note, source: str) -> list[NoteArtefactRow]:
    """Build every row for the Artefacts dialog / toolbar badge: one row per
    chart/image reference found in `source` (status "ok" if it resolves,
    "broken" if it doesn't), plus one row per snapshot Image this note
    created (note_id == note.id) that ISN'T covered by one of those
    references anymore (status "unused").

    `source` is the note's *current* text (e.g. text_edit.toPlainText()),
    not necessarily note.content -- callers must pass the live editor text
    so unsaved edits are reflected.
    """
    app_state = app_context.get_app_state() if app_context else None
    project = app_state.current_project if app_state else None
    rows: list[NoteArtefactRow] = []
    if project is None:
        return rows

    referenced_item_ids: set[str] = set()
    code_spans = code_region_spans(source)
    for match in _IMAGE_MARKDOWN_RE.finditer(source):
        if is_escaped_at(source, match.start()):
            continue
        if any(start <= match.start() < end for start, end in code_spans):
            continue
        target = match.group(1) if match.group(1) is not None else match.group(2)
        if not target:
            continue
        kind, resolved = _resolve_note_reference_target(app_context, project, target)
        if kind == "file":
            rows.append(NoteArtefactRow(
                name=target, kind="file", status="ok", is_snapshot=False,
                match_start=match.start(), match_end=match.end(), item_id=None,
            ))
        elif resolved is not None:
            referenced_item_ids.add(resolved.id)
            is_snapshot = isinstance(resolved, Image) and resolved.note_id == note.id
            rows.append(NoteArtefactRow(
                name=resolved.name, kind=kind, status="ok", is_snapshot=is_snapshot,
                match_start=match.start(), match_end=match.end(), item_id=resolved.id,
                refreshable=is_snapshot and _snapshot_source_chart(project, resolved) is not None,
            ))
        else:
            rows.append(NoteArtefactRow(
                name=target, kind="unknown", status="broken", is_snapshot=False,
                match_start=match.start(), match_end=match.end(), item_id=None,
            ))

    # extract_referenced_image_keys also recognizes reference-style links
    # (![alt][label] + a separate [label]: target definition elsewhere in
    # the note), which don't have one contiguous span to delete -- so they
    # don't get their own row -- but they DO count as "this item is
    # referenced": without this, a snapshot Image referenced only that way
    # would wrongly show up as "unused" below.
    all_referenced_keys = extract_referenced_image_keys(source)
    for key in all_referenced_keys:
        _, resolved = _resolve_note_reference_target(app_context, project, key)
        if resolved is not None:
            referenced_item_ids.add(resolved.id)

    for item in project.get_all_items():
        if isinstance(item, Image) and item.note_id == note.id and item.id not in referenced_item_ids:
            rows.append(NoteArtefactRow(
                name=item.name, kind="image", status="unused", is_snapshot=True,
                match_start=None, match_end=None, item_id=item.id,
                refreshable=_snapshot_source_chart(project, item) is not None,
            ))

    return rows


def register_project_image_resources(
    document: QTextDocument,
    app_context: AppContext,
    cache: dict[str, QImage | None] | None = None,
    referenced_keys: set[str] | None = None,
) -> str:
    """Configure document base URL and register referenced gallery images as resources.

    Each image is registered only under its immutable id and its exact
    gallery-relative path (e.g. "Album/Photo.png") -- never by bare name or
    filename stem, which could ambiguously match an unrelated same-named
    image or an on-disk file the note also references by relative path.

    If `referenced_keys` is given, only images matching one of those keys are
    resolved/registered (see `extract_referenced_image_keys`); pass None to
    register every gallery image regardless of whether the note uses it.

    """
    if cache is None:
        cache = {}
    base_dir = get_project_base_dir(app_context)
    base_url = QUrl.fromLocalFile(os.path.join(base_dir, ""))
    document.setBaseUrl(base_url)

    try:
        app_state = app_context.get_app_state() if app_context else None
        project = app_state.current_project if app_state else None
        if not project:
            return base_dir

        all_images = [item for item in project.get_all_items() if isinstance(item, Image)]
        for img_item in all_images:
            gallery_path = get_image_gallery_path(project, img_item)
            # Only the immutable id and exact gallery path are registrable
            # keys -- notably not source_file, which for a moved/renamed
            # external source could match a note's now-unrelated reference
            # to that same former/remote path.
            keys = {img_item.id, gallery_path}

            if referenced_keys is not None and keys.isdisjoint(referenced_keys):
                continue

            qimg = get_cached_qimage(img_item, cache)
            if qimg is None or qimg.isNull():
                continue

            for key in keys:
                if not key:
                    continue
                raw_url = QUrl(key)
                resolved_url = base_url.resolved(raw_url)
                for url in (raw_url, resolved_url):
                    # An existing on-disk file always wins over a gallery
                    # match (see NotePreviewBrowser.loadResource): pre-
                    # registering it here would shadow that check entirely,
                    # since a pre-registered resource is returned without
                    # ever calling loadResource at all.
                    local_path = url.toLocalFile()
                    if local_path and os.path.isfile(local_path):
                        continue
                    document.addResource(QTextDocument.ResourceType.ImageResource, url, qimg)

    except Exception:
        logger.debug("Could not register gallery images as note document resources", exc_info=True)

    return base_dir


class NotePreviewBrowser(QTextBrowser):
    """
    Subclass of QTextBrowser that dynamically resolves relative file paths and
    project gallery images for note preview rendering.
    """

    def __init__(self, app_context: AppContext, parent: QWidget | None = None):
        super().__init__(parent)
        self.app_context = app_context
        self.setOpenExternalLinks(True)
        # Memoises decoded gallery images by id; cleared by the owning editor
        # when project images actually change (see NoteEditorWidget).
        self.image_cache: dict[str, QImage | None] = {}

    @override
    def loadResource(self, type_: int, name: QUrl):
        if type_ == QTextDocument.ResourceType.ImageResource:
            # An existing on-disk file always wins over a gallery match, so a
            # relative-file reference is never hijacked by a same-named/same-id
            # gallery image (see PR #326 review).
            local_path = name.toLocalFile()
            is_real_file = bool(local_path) and os.path.isfile(local_path)
            if not is_real_file:
                qimg = self._resolve_gallery_image(name)
                if qimg is not None and not qimg.isNull():
                    self.document().addResource(QTextDocument.ResourceType.ImageResource, name, qimg)
                    return qimg

        return super().loadResource(type_, name)

    def _resolve_gallery_image(self, name: QUrl) -> QImage | None:
        """Resolve `name` to a gallery image by exact id or exact gallery path only.

        No fuzzy filename/stem matching, and no match against source_file:
        either could match an unrelated same-named/same-stem image, or a
        note's now-unrelated reference to an image's former/remote source
        path, instead of (or before) a real relative file path is even
        attempted.
        """
        try:
            app_state = self.app_context.get_app_state() if self.app_context else None
            project = app_state.current_project if app_state else None
            if not project:
                return None

            ref_str = name.toString()
            local_path = name.toLocalFile()
            base_dir = get_project_base_dir(self.app_context)
            rel_path = os.path.relpath(local_path, base_dir) if local_path and base_dir else ""

            all_images = [item for item in project.get_all_items() if isinstance(item, Image)]
            for img_item in all_images:
                gallery_path = get_image_gallery_path(project, img_item)
                match = img_item.id == ref_str or (gallery_path and gallery_path in (ref_str, rel_path))
                if match:
                    qimg = get_cached_qimage(img_item, self.image_cache)
                    if qimg is not None and not qimg.isNull():
                        return qimg

        except Exception:
            logger.debug("Could not resolve note image resource %r", name.toString(), exc_info=True)
        return None


class NoteEditorWidget(PWidget):
    """
    A modern note editor widget with text editing capabilities.
    """

    # Local signal for immediate editor reactions
    content_changed = Signal(str)

    def __init__(self, app_context: AppContext, note: Note, parent: QWidget):
        super().__init__(app_context=app_context, parent=parent)
        self.note = note
        self.is_modified = False
        self.auto_save_timer = QTimer()
        self.auto_save_timer.timeout.connect(self.auto_save)
        self.auto_save_timer.setSingleShot(True)

        # Debounces _refresh_artefacts_badge(), since
        # compute_note_artefact_rows does real filesystem checks and an
        # O(references x project items) scan -- too expensive to run
        # synchronously on every keystroke/content-changed event (see
        # final-branch-review finding on Task 7).
        self._artefacts_badge_refresh_timer = QTimer()
        self._artefacts_badge_refresh_timer.setSingleShot(True)
        self._artefacts_badge_refresh_timer.timeout.connect(self._refresh_artefacts_badge)

        # Since we can't check if the preview is connected, track it with a flag
        self.preview_connected = False

        # Re-entrancy guard so proportional scroll syncing between the source
        # and preview panes doesn't ping-pong into an infinite loop.
        self._syncing_scroll = False
        # Whether split-view scroll positions track each other.
        self.scroll_sync_enabled = True

        self._initialize()
        self.setup_connections()
        self.load_note_content()

    @override
    def _init_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Main content area
        self.create_content_section(layout)

        # Status bar
        self.create_status_section(layout)

    @override
    def _apply_theme(self):
        """Apply theme-specific styling to all components."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()

        # Get theme-appropriate colors
        card_bg = palette.get("card_bg", "#f8f9fa")
        card_hover = palette.get("card_hover", "#e9ecef")
        card_border = palette.get("card_border", "#dee2e6")
        base_fg = palette.get("base_fg", "#000000")
        secondary_fg = palette.get("secondary_fg", "#555555")

        # Apply styling to content frame
        self.content_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 6px;
            }}
        """)

        # Apply styling to toolbar
        self.toolbar.setStyleSheet(f"""
            QToolBar {{
                    background-color: {card_bg};
                    border-bottom: 1px solid {card_border};
                    padding: 4px;
                    color: {base_fg};
                }}
                QToolBar QToolButton {{
                    color: {base_fg};
                    background-color: transparent;
                    border: none;
                    padding: 6px 10px;
                    margin: 1px;
                    border-radius: 3px;
                    font-weight: 500;
                }}
                QToolBar QToolButton:hover {{
                    background-color: {card_hover};
                    color: {base_fg};
                }}
                QToolBar QToolButton:pressed {{
                    background-color: {card_hover};
                    color: {base_fg};
                }}
                QToolBar::separator {{
                    background-color: {card_border};
                    width: 1px;
                    margin: 4px 2px;
                }}
            """)

        # Apply styling to status frame
        self.status_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {card_bg};
                border: 1px solid {card_border};
                border-radius: 6px;
                padding: 4px;
                }}
            """)

        # Apply styling to status labels
        self.word_count_label.setStyleSheet(f"color: {secondary_fg}; font-size: 12px;")
        self.char_count_label.setStyleSheet(f"color: {secondary_fg}; font-size: 12px;")

        # Update status label with current status
        self._update_status_label_style()

        # Re-render the preview so equation image colours track the new theme
        # (equations are rasterised with the foreground colour baked in).
        if getattr(self, "preview", None) is not None and self.stack.currentIndex() != 0:
            self.update_preview()

    def create_content_section(self, layout: QLayout):
        """Create the main content editing section."""
        # Content frame
        self.content_frame = QFrame()
        content_layout = QVBoxLayout(self.content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        self.toolbar = QToolBar()

        # Add formatting actions
        self.create_toolbar_actions(self.toolbar)
        content_layout.addWidget(self.toolbar)

        # Create main editor and preview widgets
        self.text_edit = QTextEdit()
        font = QFont("Segoe UI", _NOTE_FONT_SIZE)
        self.text_edit.setFont(font)

        self.preview = NotePreviewBrowser(app_context=self.app_context)

        # Create container widgets for each mode

        # Edit mode container - just the text editor
        self.edit_container = QWidget()
        self.edit_layout = QVBoxLayout(self.edit_container)
        self.edit_layout.setContentsMargins(0, 0, 0, 0)
        self.edit_layout.addWidget(self.text_edit)

        # Preview mode container - just the preview
        self.preview_container = QWidget()
        self.preview_layout = QVBoxLayout(self.preview_container)
        self.preview_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_layout.addWidget(self.preview)

        # Split mode container - splitter with both widgets
        self.splitter = QSplitter(orientation=Qt.Orientation.Horizontal)

        # Stack for mode switching
        self.stack = QStackedWidget()
        self.stack.addWidget(self.edit_container)     # index 0
        self.stack.addWidget(self.preview_container)  # index 1
        self.stack.addWidget(self.splitter)    # index 2

        content_layout.addWidget(self.stack)
        layout.addWidget(self.content_frame)

        # Default mode
        self.set_mode("edit")

    def set_mode(self, mode: str):
        """Switch between edit, preview, and split modes."""
        if mode not in ["edit", "preview", "split"]:
            self.logger.warning(f"Unknown mode: {mode}")
            return

        if mode == "edit":
            self.text_edit.setParent(self.edit_container)
            self.edit_layout.addWidget(self.text_edit)
            self.stack.setCurrentIndex(0)
            self._changePreviewConnection(shouldBeConnected=False)

        elif mode == "preview":
            self.preview.setParent(self.preview_container)
            self.preview_layout.addWidget(self.preview)
            self.update_preview()
            self.stack.setCurrentIndex(1)
            self._changePreviewConnection(shouldBeConnected=False)

        elif mode == "split":
            self.text_edit.setParent(self.splitter)
            self.preview.setParent(self.splitter)
            self._changePreviewConnection(shouldBeConnected=True)
            self.update_preview()
            self.stack.setCurrentIndex(2)
            # Align the freshly rendered preview to where the editor is scrolled.
            # Deferred so the preview has laid out and its scrollbar range is set.
            if self.scroll_sync_enabled:
                QTimer.singleShot(
                    0, lambda: self._sync_scroll(self.text_edit, self.preview))

    def _changePreviewConnection(self, *, shouldBeConnected: bool):
        """Change the connection state of the preview."""
        self.logger.debug(
            f"Changing preview connection from {self.preview_connected} to {shouldBeConnected}")
        if shouldBeConnected and not self.preview_connected:
            self.text_edit.textChanged.connect(self.update_preview)
            self.preview_connected = True
        elif not shouldBeConnected and self.preview_connected:
            self.text_edit.textChanged.disconnect(self.update_preview)
            self.preview_connected = False

    def update_preview(self):
        """Render Markdown + LaTeX into the preview panel using theme colours."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        color = palette.get("base_fg", "#000000")
        background = palette.get("card_bg", "#ffffff")
        border = palette.get("card_border", "#dddddd")

        source = self.text_edit.toPlainText()
        referenced_keys = extract_referenced_image_keys(source)

        # A fresh QTextDocument every render, rather than reusing/mutating
        # self.preview.document(): QTextDocument has no API to remove a
        # resource once added with addResource(), and setHtml() doesn't
        # clear that cache either. Reusing the same document would let a
        # removed/renamed image's now-stale bytes keep answering under its
        # old id/path forever (e.g. a later image that happens to reuse that
        # id or gallery path would render the old, wrong image).
        document = QTextDocument()
        base_dir = register_project_image_resources(
            document, self.app_context, self.preview.image_cache, referenced_keys
        )
        self.preview.setSearchPaths([base_dir])

        body = render_body_html(source, color=color, fontsize=_NOTE_FONT_SIZE)
        html = wrap_document(
            body, color=color, background=background, border=border, fontsize=_NOTE_FONT_SIZE
        )
        document.setHtml(html)
        self.preview.setDocument(document)

    def export_pdf(self):
        """Export the rendered note (Markdown + LaTeX) to a PDF file."""
        from PySide6.QtCore import QMarginsF
        from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter

        default_name = f"{self.note.name or 'note'}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Note to PDF", default_name, "PDF Files (*.pdf)"
        )
        if not file_path:
            return
        if not file_path.lower().endswith(".pdf"):
            file_path += ".pdf"

        try:
            # Render for print: black text on a white page, independent of the
            # current UI theme.
            source = self.text_edit.toPlainText()
            body = render_body_html(source, color="#000000", fontsize=_NOTE_FONT_SIZE)
            html = wrap_document(
                body,
                color="#000000",
                background="#ffffff",
                border="#cccccc",
                fontsize=_NOTE_FONT_SIZE,
            )

            document = QTextDocument()
            referenced_keys = extract_referenced_image_keys(source)
            register_project_image_resources(document, self.app_context, referenced_keys=referenced_keys)
            document.setHtml(html)

            writer = QPdfWriter(file_path)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            writer.setPageMargins(QMarginsF(15, 15, 15, 15), QPageLayout.Unit.Millimeter)
            document.print_(writer)

            self.update_status("PDF exported ✓")
            QTimer.singleShot(2000, self._reset_status)
        except Exception as e:
            self.logger.exception("Failed to export note to PDF")
            self.update_status(f"Error: {e!s}")

    def create_toolbar_actions(self, toolbar: QToolBar):
        """Create toolbar actions for text formatting."""

        # Save action
        save_action = QAction("💾 Save", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self.save_content)
        toolbar.addAction(save_action)

        # Clear action
        clear_action = QAction("🗑 Clear", self)
        clear_action.triggered.connect(self.clear_content)
        toolbar.addAction(clear_action)

        # Export to PDF action (renders the same HTML shown in preview).
        export_pdf_action = QAction("📄 Export PDF", self)
        export_pdf_action.triggered.connect(self.export_pdf)
        toolbar.addAction(export_pdf_action)

        # Insert Gallery Image action
        insert_image_action = QAction("🖼️ Insert Image", self)
        insert_image_action.setToolTip("Insert an image from the project gallery")
        insert_image_action.triggered.connect(self.insert_image_from_picker)
        toolbar.addAction(insert_image_action)

        # Artefacts action -- replaces the separate Insert Chart / Insert Table
        # actions with one dialog that lists, inserts, and cleans up a
        # note's chart/image references (see NoteArtefactsDialog). Badge text
        # (a trailing " •") is applied by _refresh_artefacts_badge().
        self.artefacts_action = QAction("📎 Artefacts", self)
        self.artefacts_action.setToolTip("Manage the charts and images in this note")
        self.artefacts_action.triggered.connect(self.open_artefacts_dialog)
        toolbar.addAction(self.artefacts_action)

        toolbar.addSeparator()
        self.edit_mode_action = QAction("✍ Edit", self)
        self.edit_mode_action.triggered.connect(lambda: self.set_mode("edit"))
        toolbar.addAction(self.edit_mode_action)

        self.preview_mode_action = QAction("👁 Preview", self)
        self.preview_mode_action.triggered.connect(
            lambda: self.set_mode("preview"))
        toolbar.addAction(self.preview_mode_action)

        self.split_mode_action = QAction("⇔ Split", self)
        self.split_mode_action.triggered.connect(
            lambda: self.set_mode("split"))
        toolbar.addAction(self.split_mode_action)

        # Toggle for synced scrolling between the two split-view panes.
        self.scroll_sync_action = QAction("🔗 Sync Scroll", self)
        self.scroll_sync_action.setCheckable(True)
        self.scroll_sync_action.setChecked(self.scroll_sync_enabled)
        self.scroll_sync_action.setToolTip(
            "Keep the source and preview scrolled to the same place in split view")
        self.scroll_sync_action.toggled.connect(self._on_scroll_sync_toggled)
        toolbar.addAction(self.scroll_sync_action)

    def open_artefacts_dialog(self):
        """Open the Artefacts dialog for managing this note's charts, tables and images."""
        from pandaplot.gui.dialogs.note import NoteArtefactsDialog
        dialog = NoteArtefactsDialog(self.app_context, self.note, self.text_edit, parent=self)
        dialog.exec()
        self._refresh_artefacts_badge()
        if self.stack.currentIndex() == 1:
            self.update_preview()

    def _refresh_artefacts_badge(self) -> None:
        """Update the Artefacts toolbar action's text/tooltip to flag unused or
        broken references, computed the same way NoteArtefactsDialog itself
        does (see compute_note_artefact_rows)."""
        if not hasattr(self, "artefacts_action"):
            return
        rows = compute_note_artefact_rows(self.app_context, self.note, self.text_edit.toPlainText())
        has_issues = any(row.status in ("unused", "broken") for row in rows)
        self.artefacts_action.setText("📎 Artefacts" + (" •" if has_issues else ""))
        tooltip = "Manage the charts and images in this note"
        if has_issues:
            tooltip += " -- some references are unused or broken"
        self.artefacts_action.setToolTip(tooltip)

    def _schedule_artefacts_badge_refresh(self) -> None:
        """Debounced _refresh_artefacts_badge(), restarting the wait on every
        call -- compute_note_artefact_rows does real filesystem checks and an
        O(references x project items) scan, so it must not run on every
        keystroke (see final-branch-review finding on Task 7)."""
        self._artefacts_badge_refresh_timer.start(_ARTEFACTS_BADGE_REFRESH_DEBOUNCE_MS)

    def insert_chart_from_picker(self):
        """Open the chart picker dialog and insert markdown for the selected chart."""
        from pandaplot.gui.dialogs.note import NoteChartPickerDialog
        app_state = self.app_context.get_app_state() if self.app_context else None
        project = app_state.current_project if app_state else None
        dialog = NoteChartPickerDialog(self.app_context, project, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            chart = dialog.get_selected_chart()
            if chart is not None:
                self._insert_chart_snapshot(chart)

    def _insert_chart_snapshot(self, chart: Chart) -> None:
        """Render `chart` once, in the background, and insert a static
        gallery-image reference once ready -- unlike the live reference,
        this never changes again even if the chart's data/style does.

        `cursor` is captured now and reused when the render completes:
        a live QTextCursor tracks its position through any edits made via
        other cursors in between (e.g. the user continuing to type while
        the render runs), so the reference lands where "Insert" was
        clicked rather than wherever the caret happens to be later.
        """
        cursor = self.text_edit.textCursor()
        alt_text = chart.name.replace("[", "(").replace("]", ")")

        def _on_result(qimg: QImage | None) -> None:
            if not isValid(self):
                return
            if qimg is None:
                self._warn_chart_snapshot_failed(chart)
                return
            # The note tab (and this widget) may have been closed while the
            # render was in flight. Checked BEFORE _save_chart_snapshot_image
            # -- which creates a gallery + image and pushes them onto the
            # undo stack -- so a closed tab doesn't leave an orphaned
            # gallery/image behind with nothing left to reference it (the
            # insertion point below is gone too).
            if not isValid(self):
                return
            image_id = self._save_chart_snapshot_image(chart, qimg)
            if image_id is None:
                self._warn_chart_snapshot_failed(chart)
                return
            markdown_ref = f"![{alt_text}]({image_id} ={_DEFAULT_INSERT_MAX_WIDTH}x)"
            cursor.insertText(markdown_ref)
            self.text_edit.setTextCursor(cursor)
            if self.stack.currentIndex() == 1:
                self.update_preview()

        def _on_error(_err) -> None:
            if isValid(self):
                self._warn_chart_snapshot_failed(chart)

        dispatch_headless_chart_render(self.app_context, chart, on_result=_on_result, on_error=_on_error)

    def _warn_chart_snapshot_failed(self, chart: Chart) -> None:
        """Tell the user a static chart insertion produced nothing, rather
        than leaving them wondering why no reference appeared."""
        self.app_context.get_ui_controller().show_warning_message(
            "Insert Chart", f"Could not insert a snapshot of chart '{chart.name}'.")

    def _save_chart_snapshot_image(self, chart: Chart, qimg: QImage) -> str | None:
        """Add `qimg` to the project as a plain gallery Image (in the
        note's "Chart Snapshots" gallery), returning its new id, or None
        on failure."""
        from pandaplot.commands.project.image.create_image_from_bytes_command import CreateImageFromBytesCommand

        png_bytes = _qimage_to_png_bytes(qimg)

        gallery_id = find_or_create_chart_snapshot_gallery(self.app_context, self.note.parent_id)
        if gallery_id is None:
            return None
        app_state = self.app_context.get_app_state()
        project = app_state.current_project if app_state else None
        # Names aren't unique, so two same-named charts must not produce
        # indistinguishable snapshots in the shared gallery.
        image_name = dict(chart_display_options(project)).get(chart.id, chart.name) if project else chart.name
        command = CreateImageFromBytesCommand(
            self.app_context, gallery_id=gallery_id, name=image_name,
            png_bytes=png_bytes, width=qimg.width(), height=qimg.height(),
            note_id=self.note.id, source_chart_id=chart.id,
        )
        succeeded = self.app_context.get_command_executor().execute_command(command, track_undo=True)
        return command.created_image_id if succeeded else None

    def refresh_chart_snapshot(self, image_id: str) -> None:
        """Re-render the chart a snapshot image came from and replace the
        image's contents in place (undoable), so every reference to it shows
        the chart's current data and style."""
        from pandaplot.commands.project.image.edit_image_command import EditImageCommand

        app_state = self.app_context.get_app_state()
        project = app_state.current_project if app_state else None
        image = project.find_item(image_id) if project else None
        chart = _snapshot_source_chart(project, image) if isinstance(image, Image) else None
        if chart is None:
            self.app_context.get_ui_controller().show_warning_message(
                "Refresh Chart Snapshot", "The chart this snapshot was made from no longer exists.")
            return

        def _on_result(qimg: QImage | None) -> None:
            if not isValid(self):
                return
            if qimg is None:
                self._warn_chart_snapshot_failed(chart)
                return
            png_bytes = _qimage_to_png_bytes(qimg)
            command = EditImageCommand(
                self.app_context, image_id, png_bytes, qimg.width(), qimg.height(), new_ext="png")
            if self.app_context.get_command_executor().execute_command(command, track_undo=True):
                self.update_status(f"Refreshed snapshot of '{chart.name}'")

        def _on_error(_err) -> None:
            if isValid(self):
                self._warn_chart_snapshot_failed(chart)

        dispatch_headless_chart_render(self.app_context, chart, on_result=_on_result, on_error=_on_error)

    def insert_table_from_picker(self):
        """Open the table picker dialog and insert markdown for the table."""
        from pandaplot.gui.dialogs.note import NoteTablePickerDialog
        app_state = self.app_context.get_app_state() if self.app_context else None
        project = app_state.current_project if app_state else None
        dialog = NoteTablePickerDialog(self.app_context, project, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            table_md = dialog.get_markdown_table()
            if table_md:
                cursor = self.text_edit.textCursor()
                # A single newline doesn't isolate the table block from
                # surrounding Markdown -- inserting at the end of a
                # paragraph without a blank line on each side gets the
                # table lines absorbed into that paragraph (or trailing
                # text absorbed into the table) instead of rendering as an
                # actual <table>.
                cursor.insertText("\n\n" + table_md + "\n\n")
                self.text_edit.setTextCursor(cursor)
                self.text_edit.setFocus()
                if self.stack.currentIndex() == 1:
                    self.update_preview()

    def insert_image_from_picker(self):
        """Open the image picker dialog and insert markdown for the selected gallery image."""
        app_state = self.app_context.get_app_state() if self.app_context else None
        project = app_state.current_project if app_state else None
        dialog = NoteImagePickerDialog(self.app_context, project, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            image = dialog.get_selected_image()
            if image is not None:
                cursor = self.text_edit.textCursor()
                # "[" / "]" in the name would prematurely close the Markdown
                # alt-text span (there's no escape for it in bare link
                # syntax), breaking the whole image reference.
                alt_text = image.name.replace("[", "(").replace("]", ")")
                # Reference by immutable id: names are mutable and can be
                # duplicated across galleries, so a name-based reference could
                # later resolve to the wrong (renamed/duplicate) image.
                image_ref = image.id
                size_suffix = ""
                if image.width and image.width > _DEFAULT_INSERT_MAX_WIDTH:
                    size_suffix = f" ={_DEFAULT_INSERT_MAX_WIDTH}x"
                markdown_ref = f"![{alt_text}]({image_ref}{size_suffix})"
                cursor.insertText(markdown_ref)
                self.text_edit.setTextCursor(cursor)
                self.text_edit.setFocus()
                if self.stack.currentIndex() == 1:  # preview-only mode
                    # textChanged->update_preview is disconnected in this mode,
                    # so the (hidden) source changed but the preview wouldn't
                    # otherwise refresh until the mode is switched.
                    self.update_preview()

    def _on_scroll_sync_toggled(self, enabled: bool):  # noqa: FBT001 - Qt-invoked callback (signal.connect)
        """Enable/disable split-view scroll syncing and align immediately."""
        self.scroll_sync_enabled = enabled
        if enabled and self.stack.currentIndex() == 2:
            self._sync_scroll(self.text_edit, self.preview)

    def create_status_section(self, layout: QLayout):
        """Create the status section with statistics."""
        self.status_frame = QFrame()
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(12, 4, 12, 4)

        self.word_count_label = QLabel("Words: 0")
        status_layout.addWidget(self.word_count_label)

        self.char_count_label = QLabel("Characters: 0")
        status_layout.addWidget(self.char_count_label)

        status_layout.addStretch()

        self.status_label = QLabel("Ready")
        status_layout.addWidget(self.status_label)

        layout.addWidget(self.status_frame)

    def setup_connections(self):
        """Set up signal connections and event subscriptions."""
        self.text_edit.textChanged.connect(self.on_content_changed)

        # Keep the two panes' scroll positions in sync while in split mode, so
        # the same part of the note is visible on both sides while editing.
        self.text_edit.verticalScrollBar().valueChanged.connect(
            self._on_editor_scrolled)
        self.preview.verticalScrollBar().valueChanged.connect(
            self._on_preview_scrolled)

        # Subscribe to external rename/content change events for this note
        self.subscribe_to_event(
            NoteEvents.NOTE_CONTENT_CHANGED, self.on_note_content_changed_event)
        # Jump to a match when note search asks to reveal one in this note.
        self.subscribe_to_event(
            UIEvents.NOTE_REVEAL_MATCH, self.on_reveal_match_event)

        # Subscribe to project item changes to refresh preview when gallery images change
        self.subscribe_to_event(
            ProjectEvents.PROJECT_ITEM_ADDED, self.on_project_item_changed_event)
        self.subscribe_to_event(
            ProjectEvents.PROJECT_ITEM_REMOVED, self.on_project_item_changed_event)
        self.subscribe_to_event(
            ProjectEvents.PROJECT_ITEM_RENAMED, self.on_project_item_changed_event)
        self.subscribe_to_event(
            ProjectEvents.PROJECT_ITEM_CONTENT_CHANGED, self.on_project_item_changed_event)
        self.subscribe_to_event(
            ProjectEvents.PROJECT_ITEM_MOVED, self.on_project_item_changed_event)

    def on_project_item_changed_event(self, event_data: dict):
        """Refresh preview if images in the project change.

        These add/remove/rename/move events are generic to every project
        item type, so without filtering, adding or renaming an unrelated
        note/dataset/chart would also clear every decoded image and
        immediately rerender -- for a note with a visible external gallery
        URL, that means a synchronous network fetch on the UI thread for a
        change that has nothing to do with images at all.
        """
        if not self._event_affects_images(event_data):
            return
        # A snapshot image added, removed or moved can change which of the
        # note's artefacts are unused or broken.
        self._schedule_artefacts_badge_refresh()
        # Added/removed/renamed/moved images invalidate cached decodes (an id
        # could be reused by a new item, a rename changes its gallery path).
        self.preview.image_cache.clear()
        if self.stack.currentIndex() != 0:  # preview or split mode visible
            self.update_preview()

    def _event_affects_images(self, event_data: dict) -> bool:
        """Whether a PROJECT_ITEM_* event concerns an Image/ImageGallery.

        Payload shape differs per emitting command (image commands use
        "image_id"/"gallery_id"; generic add/remove/rename/move commands use
        "item_id" [+ "item_type" for remove/move, but not rename]), so no
        single field reliably identifies the item type across all of them.
        Falls back to looking the item up in the project when only a generic
        "item_id" is given and no type is present.

        A generic Folder isn't itself an image, but one can contain an
        ImageGallery (or nested Folder containing one) -- gallery-relative
        paths include every ancestor folder name, so renaming/moving/
        deleting such a folder changes or removes descendant images' paths
        just as surely as touching the gallery directly.
        """
        if "image_id" in event_data or "gallery_id" in event_data:
            return True

        item_type = str(event_data.get("item_type", "")).lower()
        if item_type in ("image", "imagegallery", "image_gallery", "gallery"):
            return True

        item_id = event_data.get("item_id")
        if not item_id:
            return False
        app_state = self.app_context.get_app_state() if self.app_context else None
        project = app_state.current_project if app_state else None
        if project is None:
            return False

        item = project.find_item(item_id)
        if item is not None:
            if isinstance(item, (Image, ImageGallery)):
                return True
            if isinstance(item, ItemCollection):
                return self._collection_has_image_descendant(project, item)
            return False

        # The item no longer exists (a REMOVED event) -- fall back to the
        # deleted snapshot delete_item_command attaches, since it's the only
        # place left to check whether the removed subtree held any images.
        return self._snapshot_has_image_descendant(event_data.get("item_data"))

    @staticmethod
    def _collection_has_image_descendant(project, collection: ItemCollection) -> bool:
        """Whether `collection` (a Folder/ImageGallery still in the project)
        contains an Image/ImageGallery anywhere in its subtree."""
        collection_ids = {collection.id}
        # A second pass catches grandchildren etc.: collection_ids grows
        # every time a new descendant collection is found, so items whose
        # parent was only just added get picked up on a later iteration.
        changed = True
        while changed:
            changed = False
            for item in project.get_all_items():
                if item.parent_id in collection_ids and item.id not in collection_ids:
                    if isinstance(item, (Image, ImageGallery)):
                        return True
                    if isinstance(item, ItemCollection):
                        collection_ids.add(item.id)
                        changed = True
        return False

    @staticmethod
    def _snapshot_has_image_descendant(item_data: dict | None) -> bool:
        """Best-effort check of a deleted item's serialized snapshot
        (Item.to_dict()) for an embedded Image.

        There's no explicit "type" field in the serialized form, so this
        looks for Image-specific keys (present only on Image.to_dict()).
        """
        if not isinstance(item_data, dict):
            return False
        if "storage_mode" in item_data and "image_ext" in item_data:
            return True
        return any(
            NoteEditorWidget._snapshot_has_image_descendant(child)
            for child in item_data.get("items", [])
        )

    def on_reveal_match_event(self, event_data: dict):
        """Move the cursor to (and select) a match requested by note search."""
        if event_data.get("note_id") != self.note.id:
            return

        line_number = event_data.get("line_number")
        match_start = event_data.get("match_start")
        match_end = event_data.get("match_end")
        if line_number is None or match_start is None or match_end is None:
            return

        # The match must be visible in the source editor, so ensure the text
        # pane is showing (split keeps the preview too).
        if self.stack.currentIndex() == 1:  # preview-only
            self.set_mode("split")

        document = self.text_edit.document()
        block = document.findBlockByLineNumber(max(0, line_number - 1))
        if not block.isValid():
            return

        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + match_start)
        cursor.setPosition(
            block.position() + match_end, QTextCursor.MoveMode.KeepAnchor
        )
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()
        self.text_edit.setFocus()

    def _on_editor_scrolled(self, _value: int):
        """Mirror the source editor's scroll position onto the preview."""
        if self.scroll_sync_enabled and self.stack.currentIndex() == 2:
            self._sync_scroll(self.text_edit, self.preview)

    def _on_preview_scrolled(self, _value: int):
        """Mirror the preview's scroll position onto the source editor."""
        if self.scroll_sync_enabled and self.stack.currentIndex() == 2:
            self._sync_scroll(self.preview, self.text_edit)

    def _sync_scroll(self, source: QWidget, target: QWidget):
        """Scroll ``target`` to the same relative position as ``source``.

        Uses proportional (percentage-of-scrollable-range) mapping: the two
        panes have different heights because Markdown/LaTeX renders differently
        from its source, so an exact line mapping isn't available, but keeping
        the same fraction scrolled lines them up closely enough to navigate.
        """
        if self._syncing_scroll:
            return
        source_bar = source.verticalScrollBar()
        target_bar = target.verticalScrollBar()

        source_range = source_bar.maximum() - source_bar.minimum()
        ratio = (source_bar.value() - source_bar.minimum()) / source_range if source_range else 0.0

        target_range = target_bar.maximum() - target_bar.minimum()
        new_value = round(target_bar.minimum() + ratio * target_range)

        # Setting the target's value re-emits valueChanged; the guard stops that
        # from bouncing straight back and fighting the user's scroll.
        self._syncing_scroll = True
        try:
            target_bar.setValue(new_value)
        finally:
            self._syncing_scroll = False

    def load_note_content(self):
        """Load the note content into the editor."""
        self.text_edit.setPlainText(self.note.content)
        self.update_statistics()
        self.is_modified = False
        self.update_status("Ready")

    def on_content_changed(self):
        """Handle content changes."""
        self.is_modified = True
        self.update_status("Modified *")
        self.update_statistics()

        # Start auto-save timer (save after 2 seconds of inactivity)
        self.auto_save_timer.start(2000)

        # Emit content changed signal
        content = self.text_edit.toPlainText()
        self.content_changed.emit(content)

        self._schedule_artefacts_badge_refresh()

    def update_statistics(self):
        """Update word and character count."""
        content = self.text_edit.toPlainText()
        word_count = len(content.split()) if content.strip() else 0
        char_count = len(content)

        self.word_count_label.setText(f"Words: {word_count}")
        self.char_count_label.setText(f"Characters: {char_count}")

    def _update_status_label_style(self):
        """Update status label styling based on current status and theme."""
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        secondary_fg = palette.get("secondary_fg", "#555555")

        status_text = self.status_label.text()

        # Determine color based on status
        if "Modified" in status_text:
            color = "#ffc107"  # Warning yellow
        elif "Saved" in status_text or "Synced" in status_text:
            color = "#28a745"  # Success green
        elif "Error" in status_text:
            color = "#dc3545"  # Error red
        else:
            color = secondary_fg  # Default theme color

        self.status_label.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: bold;")

    def update_status(self, status: str):
        """Update the status label."""
        self.status_label.setText(status)
        self._update_status_label_style()

    def _reset_status(self) -> None:
        """Reset the status label to "Ready" once a transient message has been shown.

        Runs from a timer, so the editor may have been closed (and its Qt widgets
        deleted) in the meantime.
        """
        try:
            self.update_status("Ready")
        except RuntimeError:
            self.logger.debug("Note editor closed before the status reset timer fired")

    def save_content(self, *, track_undo: bool = True) -> bool:
        """Save the note content. Returns whether the save actually
        committed -- callers (e.g. flush_pending_edits) must not treat
        a failed save as "no longer dirty", or an edit that EditNoteCommand
        rejected (or that raised) would be silently discarded as if it had
        been persisted.

        track_undo=False (used by NoteTab.save(), the flush path invoked by
        UnsavedChangesRegistry) commits the edit without occupying an undo
        slot. A flush can run while another command (e.g. LoadProjectCommand)
        already occupies a stack slot for an operation that hasn't finished
        yet -- pushing a new, undo-tracked EditNoteCommand onto the shared
        stack there would interleave it with that command, so a later Undo
        could pop the note edit first and apply it against whatever project
        is current by then, not the one the edit was actually made in (see
        PR #352 review). The toolbar Save action and the 2s auto-save timer
        both still call this with the default True, unaffected."""
        try:
            content = self.text_edit.toPlainText()

            # Execute save command
            command = EditNoteCommand(self.app_context, self.note.id, content)
            succeeded = self.app_context.get_command_executor().execute_command(command, track_undo=track_undo)
            if not succeeded:
                self.update_status("Error: save failed")
                return False

            # Local model already updated by command; avoid duplicate mutation

            # Update UI
            self.is_modified = False
            self.update_status("Saved ✓")

            # Reset status after 2 seconds
            QTimer.singleShot(2000, self._reset_status)
            return True

        except Exception as e:  # noqa: BLE001 -- GUI event-handler safety net -- an unexpected error here must not crash the UI
            self.update_status(f"Error: {e!s}")
            return False

    def auto_save(self):
        """Auto-save the content."""
        if self.is_modified:
            self.save_content()

    def on_note_content_changed_event(self, event_data: dict):
        """Handle external note content changes (undo/redo or other editors)."""
        if event_data.get("note_id") != self.note.id:
            return
        new_content = event_data.get("new_content")
        if new_content is not None and self.text_edit.toPlainText() != new_content:
            self.text_edit.blockSignals(True)  # noqa: FBT003 - Qt method rejects keyword args
            self.text_edit.setPlainText(new_content)
            self.update_preview()
            self.text_edit.blockSignals(False)  # noqa: FBT003 - Qt method rejects keyword args
            self.update_statistics()
            self.is_modified = False
            self.update_status("Synced ✓")

    def clear_content(self):
        """Clear all content."""
        self.text_edit.clear()

    def get_note(self) -> Note:
        """Get the current note object."""
        return self.note

    def has_unsaved_changes(self) -> bool:
        """Check if there are unsaved changes."""
        return self.is_modified
