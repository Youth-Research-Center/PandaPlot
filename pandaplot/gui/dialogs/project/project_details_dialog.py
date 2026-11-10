"""Dialog for editing a project's name, notes, cover image and example settings (#597, #598, #613)."""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import override

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap, QStandardItemModel
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.drop_down_combo_box import DropDownComboBox
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.models.project.example_info import (
    EXAMPLE_TAGS,
    MAX_FEATURED_CHARTS,
    ExampleInfo,
    ExampleLevel,
    ExampleSection,
    TagGroup,
    summary_from_description,
)
from pandaplot.models.project.items import Item, Note
from pandaplot.models.project.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.note_render.latex_markdown_renderer import render_body_html, wrap_document
from pandaplot.services.project.cover_image import prepare_cover_image
from pandaplot.services.theme.theme_manager import ThemeManager
from pandaplot.utils.errors import UserFacingError
from pandaplot.utils.item_display_options import chart_display_options, disambiguated_display_options

logger = logging.getLogger(__name__)

COVER_THUMBNAIL_WIDTH = 160
_PREVIEW_FONT_SIZE = 11.0
_IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tif *.tiff);;All Files (*)"
_NO_COVER_TEXT = "No cover image. Examples show their first featured chart instead."
_NAME_REQUIRED_TOOLTIP = "Enter a project name to continue."
_DEFAULT_SUMMARY_PLACEHOLDER = "A one or two line summary shown on the example's card"
_NONE_LABEL = "None"


@dataclass(frozen=True)
class ProjectDetailsResult:
    """The values the user chose in `ProjectDetailsDialog`."""

    name: str
    description: str
    cover_image: bytes | None
    example_info: ExampleInfo


class ProjectDetailsDialog(PDialog):
    """Modal editor for the details of ``project``.

    The dialog never changes the project: after it is accepted, `get_result` returns the chosen values and
    the caller applies them (see `UpdateProjectDetailsCommand`).

    Attributes:
        name_edit: Project name; the OK button is disabled while it is empty.
        description_edit: Markdown notes stored in the project's description.
        preview_button: Checkable button that swaps the editor for a rendered preview.
        choose_cover_button: Opens a file picker for the cover image.
        remove_cover_button: Clears the cover image.
        example_checkbox: Marks the project as an example and reveals ``example_group``.
        ok_button: Accepts the dialog.
        cancel_button: Rejects the dialog.
    """

    def __init__(self, app_context: AppContext, project: Project, parent: QWidget | None = None) -> None:
        """Create the dialog and fill it from ``project``.

        Args:
            app_context: Application context.
            project: The project to edit. It is only read.
            parent: Parent widget.
        """
        super().__init__(app_context=app_context, parent=parent)
        self._project = project
        self._cover_image: bytes | None = project.cover_image
        self._chart_options = chart_display_options(project)
        notes: list[Item] = [item for item in project.get_all_items() if isinstance(item, Note)]
        self._note_options = disambiguated_display_options(notes, project)
        self._updating_featured = False
        self._initialize()
        self._load(project)

    @override
    def _init_ui(self) -> None:
        self.setWindowTitle("Project Details")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.resize(640, 720)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 16)
        outer.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._content_layout = QVBoxLayout(content)
        self._content_layout.setContentsMargins(0, 0, 8, 0)
        self._content_layout.setSpacing(14)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        self._build_name_section()
        self._build_notes_section()
        self._build_cover_section()
        self._build_example_section()
        self._content_layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_button = PButton("Cancel", role="secondary", on_click=self.reject)
        self.ok_button = PButton("OK", role="primary", on_click=self.accept)
        self.ok_button.setDefault(True)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.ok_button)
        outer.addLayout(buttons)

        self.setTabOrder(self.name_edit, self.description_edit)

    def _add_label(self, text: str, buddy: QWidget, layout: QVBoxLayout | QFormLayout | None = None) -> QLabel:
        label = QLabel(text)
        label.setBuddy(buddy)
        if isinstance(layout, QVBoxLayout):
            layout.addWidget(label)
        return label

    def _muted_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("detailsMuted")
        label.setWordWrap(True)
        return label

    def _build_name_section(self) -> None:
        self.name_edit = QLineEdit()
        self.name_edit.setAccessibleName("Project name")
        self.name_edit.textChanged.connect(self._update_ok_state)
        section = QVBoxLayout()
        section.setSpacing(4)
        self._add_label("Name", self.name_edit, section)
        section.addWidget(self.name_edit)
        self._content_layout.addLayout(section)

    def _build_notes_section(self) -> None:
        self.description_edit = QPlainTextEdit()
        self.description_edit.setAccessibleName("About this project")
        self.description_edit.setAccessibleDescription("Notes about the project in Markdown")
        self.description_edit.setTabChangesFocus(True)
        self.description_edit.setMinimumHeight(140)
        self.description_edit.textChanged.connect(self._update_summary_placeholder)

        self.preview_browser = QTextBrowser()
        self.preview_browser.setAccessibleName("About this project preview")
        self.preview_browser.setOpenExternalLinks(False)
        self.preview_browser.setMinimumHeight(140)
        self.preview_browser.hide()

        self.preview_button = QPushButton("Preview")
        self.preview_button.setCheckable(True)
        self.preview_button.setAccessibleName("Preview")
        self.preview_button.setAccessibleDescription("Show the notes as they will be rendered instead of the Markdown source")
        self.preview_button.toggled.connect(self._on_preview_toggled)

        header = QHBoxLayout()
        header_label = self._add_label("About this project", self.description_edit)
        header.addWidget(header_label)
        header.addStretch()
        header.addWidget(self.preview_button)

        section = QVBoxLayout()
        section.setSpacing(4)
        section.addLayout(header)
        section.addWidget(self.description_edit)
        section.addWidget(self.preview_browser)
        section.addWidget(self._muted_label("Notes about the project, such as background and findings. Markdown is supported."))
        self._content_layout.addLayout(section)

    def _build_cover_section(self) -> None:
        self.cover_label = QLabel()
        self.cover_label.setObjectName("detailsCover")
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setWordWrap(True)
        self.cover_label.setMinimumWidth(COVER_THUMBNAIL_WIDTH)
        self.cover_label.setMaximumWidth(COVER_THUMBNAIL_WIDTH)
        self.cover_label.setAccessibleName("Cover image preview")

        self.choose_cover_button = PButton("Choose image...", role="secondary", on_click=self._choose_cover)
        self.choose_cover_button.setAccessibleName("Choose cover image")
        self.remove_cover_button = PButton("Remove", role="secondary", on_click=self._remove_cover)
        self.remove_cover_button.setAccessibleName("Remove cover image")

        buttons = QVBoxLayout()
        buttons.addWidget(self.choose_cover_button)
        buttons.addWidget(self.remove_cover_button)
        buttons.addStretch()

        row = QHBoxLayout()
        row.setSpacing(12)
        row.addWidget(self.cover_label)
        row.addLayout(buttons)
        row.addStretch()

        title = QLabel("Cover image")
        title.setBuddy(self.choose_cover_button)
        section = QVBoxLayout()
        section.setSpacing(4)
        section.addWidget(title)
        section.addLayout(row)
        self._content_layout.addLayout(section)

    def _build_example_section(self) -> None:
        self.example_checkbox = QCheckBox("Use this project as an example")
        self.example_checkbox.setAccessibleName("Use this project as an example")
        self.example_checkbox.toggled.connect(self._on_example_toggled)
        self._content_layout.addWidget(self.example_checkbox)

        self.example_group = QGroupBox("Example settings")
        form = QFormLayout(self.example_group)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self.summary_edit = QLineEdit()
        self.summary_edit.setAccessibleName("Short description")
        form.addRow(self._form_label("Short description", self.summary_edit), self.summary_edit)

        self.section_combo = DropDownComboBox()
        self.section_combo.setAccessibleName("Section")
        for section in ExampleSection:
            self.section_combo.addItem(section.label, section.value)
        form.addRow(self._form_label("Section", self.section_combo), self.section_combo)

        self.level_combo = DropDownComboBox()
        self.level_combo.setAccessibleName("Level")
        for level in ExampleLevel:
            self.level_combo.addItem(level.label, level.value)
        form.addRow(self._form_label("Level", self.level_combo), self.level_combo)

        self.tag_checkboxes: dict[str, QCheckBox] = {}
        for group, title in ((TagGroup.TOPIC, "Topic"), (TagGroup.TECHNIQUE, "Technique")):
            box = QGroupBox(f"Tags: {title}")
            box_layout = QVBoxLayout(box)
            box_layout.setSpacing(2)
            for tag in EXAMPLE_TAGS:
                if tag.group is not group:
                    continue
                checkbox = QCheckBox(tag.label)
                checkbox.setAccessibleName(f"{title} tag: {tag.label}")
                self.tag_checkboxes[tag.id] = checkbox
                box_layout.addWidget(checkbox)
            form.addRow(box)

        self.featured_combos: list[DropDownComboBox] = []
        for index in range(MAX_FEATURED_CHARTS):
            combo = DropDownComboBox()
            combo.setAccessibleName(f"Featured chart {index + 1}")
            combo.addItem(_NONE_LABEL, None)
            for chart_id, display_name in self._chart_options:
                combo.addItem(display_name, chart_id)
            combo.currentIndexChanged.connect(self._refresh_featured_choices)
            self.featured_combos.append(combo)
            form.addRow(self._form_label(f"Featured chart {index + 1}", combo), combo)

        self.start_note_combo = DropDownComboBox()
        self.start_note_combo.setAccessibleName("Start here note")
        self.start_note_combo.addItem(_NONE_LABEL, None)
        for note_id, display_name in self._note_options:
            self.start_note_combo.addItem(display_name, note_id)
        form.addRow(self._form_label("Start here note", self.start_note_combo), self.start_note_combo)

        self.credit_edit = QLineEdit()
        self.credit_edit.setAccessibleName("Data source and credit")
        form.addRow(self._form_label("Data source and credit", self.credit_edit), self.credit_edit)

        self._content_layout.addWidget(self.example_group)

    def _form_label(self, text: str, buddy: QWidget) -> QLabel:
        label = QLabel(text)
        label.setBuddy(buddy)
        return label

    @override
    def _apply_theme(self) -> None:
        tokens = self.app_context.get_manager(ThemeManager).get_design_tokens()
        self.setStyleSheet(f"""
            QDialog {{
                background-color: {tokens['surface_white']};
                color: {tokens['text_primary']};
            }}
            QLabel, QCheckBox {{
                color: {tokens['text_primary']};
            }}
            QLabel#detailsMuted {{
                color: {tokens['text_muted']};
            }}
            QLabel#detailsCover {{
                color: {tokens['text_muted']};
                background-color: {tokens['surface_inset']};
                border: 1px dashed {tokens['border_control']};
                border-radius: {tokens['radius_card']}px;
                padding: 6px;
            }}
            QGroupBox {{
                border: 1px solid {tokens['border_control']};
                border-radius: {tokens['radius_card']}px;
                margin-top: 10px;
                padding-top: 10px;
                color: {tokens['text_secondary']};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 8px;
                color: {tokens['text_secondary']};
            }}
        """)
        self._refresh_cover()

    def _load(self, project: Project) -> None:
        """Fill every control from ``project``."""
        info = project.example_info
        self.name_edit.setText(project.name)
        self.description_edit.setPlainText(project.description)
        self._refresh_cover()

        self.example_checkbox.setChecked(info.is_example)
        self.example_group.setVisible(info.is_example)
        self.summary_edit.setText(info.summary)
        # Show the start of a long summary, not its end (setText leaves the cursor at the end).
        self.summary_edit.setCursorPosition(0)
        self.section_combo.setCurrentIndex(max(0, self.section_combo.findData(info.section.value)))
        self.level_combo.setCurrentIndex(max(0, self.level_combo.findData(info.level.value)))
        for tag_id, checkbox in self.tag_checkboxes.items():
            checkbox.setChecked(tag_id in info.tag_ids)

        # Ids of deleted charts and notes are skipped here, so accepting the dialog saves them away.
        known_charts = {chart_id for chart_id, _name in self._chart_options}
        present = [chart_id for chart_id in info.featured_chart_ids if chart_id in known_charts]
        self._updating_featured = True
        try:
            for index, combo in enumerate(self.featured_combos):
                chart_id = present[index] if index < len(present) else None
                combo.setCurrentIndex(max(0, combo.findData(chart_id)))
        finally:
            self._updating_featured = False
        self._refresh_featured_choices()
        self.start_note_combo.setCurrentIndex(max(0, self.start_note_combo.findData(info.start_note_id)))
        self.credit_edit.setText(info.data_credit)

        self._update_summary_placeholder()
        self._update_ok_state()

    def _update_ok_state(self, _text: str = "") -> None:
        has_name = bool(self.name_edit.text().strip())
        self.ok_button.setEnabled(has_name)
        self.ok_button.setToolTip("" if has_name else _NAME_REQUIRED_TOOLTIP)
        self.ok_button.setAccessibleDescription("" if has_name else _NAME_REQUIRED_TOOLTIP)

    def _update_summary_placeholder(self) -> None:
        fallback = summary_from_description(self.description_edit.toPlainText())
        self.summary_edit.setPlaceholderText(fallback or _DEFAULT_SUMMARY_PLACEHOLDER)

    def _on_example_toggled(self, checked: bool) -> None:  # noqa: FBT001 - connected directly to a Qt signal
        # Hiding keeps every control's value, so ticking the box again restores the settings.
        self.example_group.setVisible(checked)

    def _on_preview_toggled(self, checked: bool) -> None:  # noqa: FBT001 - connected directly to a Qt signal
        if checked:
            self._render_preview()
        self.description_edit.setVisible(not checked)
        self.preview_browser.setVisible(checked)

    def _render_preview(self) -> None:
        tokens = self.app_context.get_manager(ThemeManager).get_design_tokens()
        color = tokens["text_primary"]
        body = render_body_html(self.description_edit.toPlainText(), color=color, fontsize=_PREVIEW_FONT_SIZE)
        html = wrap_document(
            body, color=color, background=tokens["surface_white"], border=tokens["border_control"], fontsize=_PREVIEW_FONT_SIZE
        )
        self.preview_browser.setHtml(html)

    def _refresh_cover(self) -> None:
        pixmap = QPixmap()
        if self._cover_image is not None and pixmap.loadFromData(self._cover_image):
            self.cover_label.setPixmap(pixmap.scaledToWidth(COVER_THUMBNAIL_WIDTH, Qt.TransformationMode.SmoothTransformation))
            self.cover_label.setAccessibleDescription("The current cover image")
        else:
            self.cover_label.clear()
            self.cover_label.setText(_NO_COVER_TEXT)
            self.cover_label.setAccessibleDescription(_NO_COVER_TEXT)
        self.remove_cover_button.setEnabled(self._cover_image is not None)

    def _choose_cover(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(self, "Choose Cover Image", "", _IMAGE_FILTER)
        if not path:
            return
        try:
            self._cover_image = prepare_cover_image(Path(path).read_bytes())
        except (UserFacingError, OSError) as e:
            logger.exception("Failed to use %s as a cover image", path)
            self.app_context.get_ui_controller().show_error_message("Cover Image", "Couldn't use this image.", error=e)
            return
        self._refresh_cover()

    def _remove_cover(self) -> None:
        self._cover_image = None
        self._refresh_cover()

    def _refresh_featured_choices(self, _index: int = 0) -> None:
        """Disable, in each featured-chart combo, the charts picked in the others."""
        if self._updating_featured:
            return
        chosen = [combo.currentData() for combo in self.featured_combos]
        for position, combo in enumerate(self.featured_combos):
            taken = {value for other, value in enumerate(chosen) if other != position and value is not None}
            model = combo.model()
            if not isinstance(model, QStandardItemModel):
                continue
            for row in range(combo.count()):
                item = model.item(row)
                if item is None:
                    continue
                item.setEnabled(combo.itemData(row) not in taken)

    def get_result(self) -> ProjectDetailsResult:
        """Return the values currently chosen in the dialog.

        Duplicate featured charts are dropped, keeping the first, and the combo order is the chart order.
        """
        featured: list[str] = []
        for combo in self.featured_combos:
            chart_id = combo.currentData()
            if chart_id is not None and chart_id not in featured:
                featured.append(chart_id)
        info = ExampleInfo(
            is_example=self.example_checkbox.isChecked(),
            summary=self.summary_edit.text().strip(),
            section=ExampleSection(self.section_combo.currentData()),
            level=ExampleLevel(self.level_combo.currentData()),
            tag_ids=tuple(tag.id for tag in EXAMPLE_TAGS if self.tag_checkboxes[tag.id].isChecked()),
            featured_chart_ids=tuple(featured),
            start_note_id=self.start_note_combo.currentData(),
            data_credit=self.credit_edit.text().strip(),
        )
        return ProjectDetailsResult(
            name=self.name_edit.text().strip(),
            description=self.description_edit.toPlainText(),
            cover_image=self._cover_image,
            example_info=info,
        )

    @override
    def accept(self) -> None:
        if not self.name_edit.text().strip():
            self.name_edit.setFocus()
            return
        super().accept()


def edit_project_details(app_context: AppContext, parent: QWidget | None = None) -> bool:
    """Open the Project Details dialog for the current project and apply what the user accepts.

    Args:
        app_context: Application context.
        parent: Parent widget for the dialog.

    Returns:
        True if the project was changed.
    """
    from pandaplot.commands.project.current_project import get_current_project
    from pandaplot.commands.project.project import UpdateProjectDetailsCommand

    project = get_current_project(app_context)
    if project is None:
        return False
    dialog = ProjectDetailsDialog(app_context, project, parent)
    try:
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        chosen = dialog.get_result()
    finally:
        dialog.deleteLater()
    command = UpdateProjectDetailsCommand(
        app_context,
        name=chosen.name,
        description=chosen.description,
        cover_image=chosen.cover_image,
        example_info=chosen.example_info,
    )
    return app_context.get_command_executor().execute_command(command)
