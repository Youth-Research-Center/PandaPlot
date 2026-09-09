"""
Note tab widget for displaying and editing notes in the main tab container.
"""
import os
import re
from typing import Dict, Optional, Set, override
from urllib.parse import unquote

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
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

from pandaplot.commands.project.note import EditNoteCommand
from pandaplot.gui.core.widget_extension import PWidget
from pandaplot.gui.dialogs.image.note_image_picker_dialog import NoteImagePickerDialog
from pandaplot.models.events import ChartEvents, DatasetEvents, NoteEvents, UIEvents
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import Chart, Image, ImageGallery, ItemCollection, Note
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.note_render.latex_markdown_renderer import (
    is_escaped_at,
    protect_code_regions,
    render_body_html,
    wrap_document,
)
from pandaplot.services.theme.theme_manager import ThemeManager

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


def get_project_base_dir(app_context: AppContext) -> str:
    """Get base directory for relative path resolution based on current project path."""
    try:
        app_state = app_context.get_app_state() if app_context else None
        project = app_state.current_project if app_state else None
        if project and project.project_file_path:
            return os.path.dirname(os.path.abspath(project.project_file_path))
    except Exception:
        pass
    return os.getcwd()


def get_image_gallery_path(project, image_item: Image) -> str:
    """Get gallery-relative path for an Image item (e.g. 'Album/Photo.png' or 'Photo.png')."""
    if project is None or image_item is None:
        return ""
    folder_path = project.get_folder_path(image_item.id)
    if folder_path:
        return "/".join(folder_path) + "/" + image_item.name
    return image_item.name


def get_chart_gallery_path(project, chart_item: Chart) -> str:
    """Get folder-relative path for a Chart item (e.g. 'Folder/Chart' or 'Chart')."""
    if project is None or chart_item is None:
        return ""
    folder_path = project.get_folder_path(chart_item.id)
    if folder_path:
        return "/".join(folder_path) + "/" + chart_item.name
    return chart_item.name


def load_qimage_for_chart(app_context: AppContext, chart_item: Chart) -> Optional[QImage]:
    """Render a Chart item to a QImage using ChartEditorWidget/matplotlib.

    Rendering happens on the GUI thread and can't move to a worker thread
    (unlike image thumbnail decoding) because ChartEditorWidget is a QWidget
    -- Qt widgets can only be constructed on the GUI thread. The widget is
    throwaway (never shown/parented), but as a PWidget it still subscribes to
    the event bus in __init__; unsubscribe_widget_tree() must run before
    deleteLater() so that subscription doesn't stay live until Qt's deferred
    destruction actually happens (see tests/gui/core/test_unsubscribe_widget_tree.py
    for the same leak previously found on this exact widget).
    """
    try:
        import io

        from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget
        from pandaplot.gui.core.widget_extension import unsubscribe_widget_tree
        editor = ChartEditorWidget(app_context=app_context, chart=chart_item, parent=None)
        try:
            editor.update_chart()
            buf = io.BytesIO()
            editor.chart_canvas.fig.savefig(buf, format="png", dpi=100, bbox_inches="tight")
            qimg = QImage()
            if qimg.loadFromData(buf.getvalue()):
                return qimg
        finally:
            unsubscribe_widget_tree(editor)
            editor.deleteLater()
    except Exception as e:
        import logging
        logging.getLogger(__name__).debug("Failed to load QImage for chart %s: %s", chart_item.id, e)
    return None


def get_cached_qimage_for_chart(
    app_context: AppContext, chart_item: Chart, cache: Dict[str, Optional[QImage]]
) -> Optional[QImage]:
    """Load a Chart item's QImage, memoised by id in cache."""
    if chart_item.id in cache:
        return cache[chart_item.id]
    qimg = load_qimage_for_chart(app_context, chart_item)
    cache[chart_item.id] = qimg
    return qimg


def load_qimage_for_item(image_item: Image) -> Optional[QImage]:
    """Load QImage from Image item bytes or source file.

    Hits the network/disk for "external" images, so callers on a hot path
    (every keystroke) should go through `get_cached_qimage` instead.
    """
    try:
        data = image_item.get_bytes()
        if data is None and image_item.source_file:
            source = image_item.source_file
            if source.startswith("http://") or source.startswith("https://"):
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
        pass
    return None


def get_cached_qimage(image_item: Image, cache: Dict[str, Optional[QImage]]) -> Optional[QImage]:
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


def _add_key_and_decoded(keys: Set[str], target: Optional[str]) -> None:
    if not target:
        return
    keys.add(target)
    decoded = unquote(target)
    if decoded != target:
        keys.add(decoded)


def extract_referenced_image_keys(source: str) -> Set[str]:
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
    keys: Set[str] = set()

    for match in _IMAGE_REF_RE.finditer(protected_source):
        if is_escaped_at(protected_source, match.start()):
            continue
        target = match.group(1) if match.group(1) is not None else match.group(2)
        _add_key_and_decoded(keys, target)

    definitions: Dict[str, str] = {}
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


def register_project_image_resources(
    document: QTextDocument,
    app_context: AppContext,
    cache: Optional[Dict[str, Optional[QImage]]] = None,
    referenced_keys: Optional[Set[str]] = None,
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

        all_charts = [item for item in project.get_all_items() if isinstance(item, Chart)]
        for chart_item in all_charts:
            chart_path = get_chart_gallery_path(project, chart_item)
            # Only the immutable id and exact gallery path are registrable
            # keys, matching the image policy above: a bare name or
            # synthetic ".png" alias could collide with an unrelated
            # same-named gallery image's own registered key and silently
            # overwrite it (see PR #383 review).
            keys = {chart_item.id, chart_path}

            if referenced_keys is not None and keys.isdisjoint(referenced_keys):
                continue

            qimg = get_cached_qimage_for_chart(app_context, chart_item, cache)
            if qimg is None or qimg.isNull():
                continue

            for key in keys:
                if not key:
                    continue
                raw_url = QUrl(key)
                resolved_url = base_url.resolved(raw_url)
                for url in (raw_url, resolved_url):
                    local_path = url.toLocalFile()
                    if local_path and os.path.isfile(local_path):
                        continue
                    document.addResource(QTextDocument.ResourceType.ImageResource, url, qimg)
    except Exception:
        pass

    return base_dir


class NotePreviewBrowser(QTextBrowser):
    """
    Subclass of QTextBrowser that dynamically resolves relative file paths and
    project gallery images for note preview rendering.
    """

    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.app_context = app_context
        self.setOpenExternalLinks(True)
        # Memoises decoded gallery images by id; cleared by the owning editor
        # when project images actually change (see NoteEditorWidget).
        self.image_cache: Dict[str, Optional[QImage]] = {}

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

    def _resolve_gallery_image(self, name: QUrl) -> Optional[QImage]:
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

            all_charts = [item for item in project.get_all_items() if isinstance(item, Chart)]
            for chart_item in all_charts:
                chart_path = get_chart_gallery_path(project, chart_item)
                match = chart_item.id == ref_str or (chart_path and chart_path in (ref_str, rel_path))
                if match:
                    qimg = get_cached_qimage_for_chart(self.app_context, chart_item, self.image_cache)
                    if qimg is not None and not qimg.isNull():
                        return qimg
        except Exception:
            pass
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
            QTimer.singleShot(2000, lambda: self.update_status("Ready"))
        except Exception as e:
            self.logger.error("Failed to export note to PDF: %s", e, exc_info=True)
            self.update_status(f"Error: {str(e)}")

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

        # Insert Chart action
        insert_chart_action = QAction("📊 Insert Chart", self)
        insert_chart_action.setToolTip("Insert a chart from the project")
        insert_chart_action.triggered.connect(self.insert_chart_from_picker)
        toolbar.addAction(insert_chart_action)

        # Insert Table action
        insert_table_action = QAction("📋 Insert Table", self)
        insert_table_action.setToolTip("Insert a table or dataset into the note")
        insert_table_action.triggered.connect(self.insert_table_from_picker)
        toolbar.addAction(insert_table_action)

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

    def insert_chart_from_picker(self):
        """Open the chart picker dialog and insert markdown for the selected chart."""
        from pandaplot.gui.dialogs.note import NoteChartPickerDialog
        app_state = self.app_context.get_app_state() if self.app_context else None
        project = app_state.current_project if app_state else None
        dialog = NoteChartPickerDialog(self.app_context, project, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            chart = dialog.get_selected_chart()
            if chart is not None:
                cursor = self.text_edit.textCursor()
                alt_text = chart.name.replace("[", "(").replace("]", ")")
                chart_ref = chart.id
                markdown_ref = f"![{alt_text}]({chart_ref} ={_DEFAULT_INSERT_MAX_WIDTH}x)"
                cursor.insertText(markdown_ref)
                self.text_edit.setTextCursor(cursor)
                self.text_edit.setFocus()
                if self.stack.currentIndex() == 1:
                    self.update_preview()

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
                cursor.insertText("\n" + table_md + "\n")
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

        # Subscribe to chart and dataset events to update chart/table previews
        self.subscribe_to_event(
            ChartEvents.CHART_UPDATED, self.on_chart_or_dataset_changed_event)
        self.subscribe_to_event(
            DatasetEvents.DATASET_CHANGED, self.on_chart_or_dataset_changed_event)

    def on_chart_or_dataset_changed_event(self, event_data: dict):
        """Invalidate only the cached chart image(s) affected by this change.

        Chart rendering is synchronous (a full ChartEditorWidget is built and
        rasterised via matplotlib -- see load_qimage_for_chart) so clearing
        the whole cache on every change anywhere in the project would force
        every chart referenced by the currently open note to re-render on the
        next preview tick. Instead, drop only the specific chart's entry
        (CHART_UPDATED) or the entries for charts that actually use the
        changed dataset (DATASET_CHANGED).
        """
        chart_id = event_data.get("chart_id")
        if chart_id is not None:
            self.preview.image_cache.pop(chart_id, None)

        dataset_id = event_data.get("dataset_id")
        if dataset_id is not None:
            app_state = self.app_context.get_app_state() if self.app_context else None
            project = app_state.current_project if app_state else None
            if project is not None:
                for item in project.get_all_items():
                    if isinstance(item, Chart) and dataset_id in item.get_all_datasets():
                        self.preview.image_cache.pop(item.id, None)

        if self.stack.currentIndex() != 0:
            self.update_preview()

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
    def _snapshot_has_image_descendant(item_data: Optional[dict]) -> bool:
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
            QTimer.singleShot(2000, lambda: self.update_status("Ready"))
            return True

        except Exception as e:
            self.update_status(f"Error: {str(e)}")
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
