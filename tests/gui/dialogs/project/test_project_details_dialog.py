"""Tests for ProjectDetailsDialog: population, example settings, cover image, preview and the OK result."""

from unittest.mock import Mock, patch

import pytest
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QDialog

from pandaplot.gui.dialogs.project import project_details_dialog as module
from pandaplot.gui.dialogs.project.project_details_dialog import COVER_THUMBNAIL_WIDTH, ProjectDetailsDialog, edit_project_details
from pandaplot.models.project import Project
from pandaplot.models.project.example_info import ExampleInfo, ExampleLevel, ExampleSection
from pandaplot.models.project.items import Chart, Note
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


def _png(width: int, height: int) -> bytes:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("steelblue"))
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")  # ty: ignore[no-matching-overload]
    return bytes(buffer.data().data())


@pytest.fixture
def ctx():
    context = Mock(spec=AppContext)
    context.event_bus = Mock()
    theme = ThemeManager(Mock(), Mock())
    context.get_manager.return_value = theme
    context.get_ui_controller.return_value = Mock()
    return context


@pytest.fixture
def project():
    project = Project("Pendulum", description="# Pendulum\n\nA swinging **weight**. Second sentence.")
    project.chart_a = Chart(name="Period")
    project.chart_b = Chart(name="Period")  # same name: display names must be disambiguated
    project.chart_c = Chart(name="Amplitude")
    project.note = Note(name="Read me", content="hello")
    for item in (project.chart_a, project.chart_b, project.chart_c, project.note):
        project.add_item(item)
    return project


def _dialog(qtbot, ctx, project) -> ProjectDetailsDialog:
    dialog = ProjectDetailsDialog(ctx, project)
    qtbot.addWidget(dialog)
    return dialog


def test_populates_every_field_from_the_project(qtbot, ctx, project):
    project.cover_image = _png(400, 200)
    project.example_info = ExampleInfo(
        is_example=True, summary="Short", section=ExampleSection.CHARTS, level=ExampleLevel.INTERMEDIATE,
        tag_ids=("physics", "smoothing"), featured_chart_ids=(project.chart_c.id, project.chart_a.id),
        start_note_id=project.note.id, data_credit="Lab 4")
    dialog = _dialog(qtbot, ctx, project)
    dialog.show()

    assert dialog.name_edit.text() == "Pendulum"
    assert dialog.description_edit.toPlainText() == project.description
    assert dialog.cover_label.pixmap().width() == COVER_THUMBNAIL_WIDTH
    assert dialog.example_checkbox.isChecked()
    assert dialog.example_group.isVisible()
    assert dialog.summary_edit.text() == "Short"
    assert dialog.section_combo.currentData() == ExampleSection.CHARTS.value
    assert dialog.level_combo.currentData() == ExampleLevel.INTERMEDIATE.value
    assert {tag for tag, box in dialog.tag_checkboxes.items() if box.isChecked()} == {"physics", "smoothing"}
    assert [combo.currentData() for combo in dialog.featured_combos] == [project.chart_c.id, project.chart_a.id, None]
    assert dialog.start_note_combo.currentData() == project.note.id
    assert dialog.credit_edit.text() == "Lab 4"


def test_a_regular_project_hides_the_example_group_and_shows_the_placeholder_cover_text(qtbot, ctx, project):
    dialog = _dialog(qtbot, ctx, project)
    dialog.show()
    assert not dialog.example_checkbox.isChecked()
    assert not dialog.example_group.isVisible()
    assert dialog.cover_label.text() == "No cover image. Examples show their first featured chart instead."
    assert not dialog.remove_cover_button.isEnabled()


def test_summary_placeholder_shows_the_fallback_from_the_notes(qtbot, ctx, project):
    dialog = _dialog(qtbot, ctx, project)
    assert dialog.summary_edit.placeholderText() == "A swinging weight."
    dialog.description_edit.setPlainText("")
    assert dialog.summary_edit.placeholderText() != "A swinging weight."
    assert dialog.summary_edit.text() == ""


def test_unticking_hides_the_group_and_ticking_restores_the_values(qtbot, ctx, project):
    project.example_info = ExampleInfo(is_example=True, summary="Keep me", tag_ids=("statistics",), featured_chart_ids=(project.chart_a.id,))
    dialog = _dialog(qtbot, ctx, project)
    dialog.show()

    dialog.example_checkbox.setChecked(False)
    assert not dialog.example_group.isVisible()
    result = dialog.get_result().example_info
    assert result.is_example is False
    assert result.summary == "Keep me"
    assert result.tag_ids == ("statistics",)

    dialog.example_checkbox.setChecked(True)
    assert dialog.example_group.isVisible()
    assert dialog.summary_edit.text() == "Keep me"
    assert dialog.tag_checkboxes["statistics"].isChecked()
    assert dialog.featured_combos[0].currentData() == project.chart_a.id


def test_ok_result_matches_the_edits(qtbot, ctx, project):
    dialog = _dialog(qtbot, ctx, project)
    dialog.name_edit.setText("  Renamed  ")
    dialog.description_edit.setPlainText("My findings")
    dialog.example_checkbox.setChecked(True)
    dialog.summary_edit.setText(" Card text ")
    dialog.section_combo.setCurrentIndex(dialog.section_combo.findData(ExampleSection.ANALYSING_DATA.value))
    dialog.level_combo.setCurrentIndex(dialog.level_combo.findData(ExampleLevel.INTERMEDIATE.value))
    dialog.tag_checkboxes["business"].setChecked(True)
    dialog.tag_checkboxes["curve_fitting"].setChecked(True)
    dialog.featured_combos[0].setCurrentIndex(dialog.featured_combos[0].findData(project.chart_b.id))
    dialog.featured_combos[1].setCurrentIndex(dialog.featured_combos[1].findData(project.chart_a.id))
    dialog.start_note_combo.setCurrentIndex(dialog.start_note_combo.findData(project.note.id))
    dialog.credit_edit.setText("Open data")

    result = dialog.get_result()

    assert result.name == "Renamed"
    assert result.description == "My findings"
    assert result.cover_image is None
    assert type(result.example_info.section) is ExampleSection
    assert type(result.example_info.level) is ExampleLevel
    assert result.example_info.to_dict()["section"] == "analysing_data"
    assert result.example_info == ExampleInfo(
        is_example=True, summary="Card text", section=ExampleSection.ANALYSING_DATA, level=ExampleLevel.INTERMEDIATE,
        tag_ids=("business", "curve_fitting"), featured_chart_ids=(project.chart_b.id, project.chart_a.id),
        start_note_id=project.note.id, data_credit="Open data")


def test_the_dialog_does_not_change_the_project(qtbot, ctx, project):
    dialog = _dialog(qtbot, ctx, project)
    dialog.name_edit.setText("Other")
    dialog.example_checkbox.setChecked(True)
    dialog.get_result()
    assert project.name == "Pendulum"
    assert project.example_info == ExampleInfo()


def test_empty_name_disables_ok_with_a_tooltip_and_blocks_accept(qtbot, ctx, project):
    dialog = _dialog(qtbot, ctx, project)
    assert dialog.ok_button.isEnabled()
    dialog.name_edit.setText("   ")
    assert not dialog.ok_button.isEnabled()
    assert dialog.ok_button.toolTip()
    dialog.accept()
    assert dialog.result() != QDialog.DialogCode.Accepted
    dialog.name_edit.setText("Back")
    assert dialog.ok_button.isEnabled()
    assert dialog.ok_button.toolTip() == ""


def test_featured_chart_combos_do_not_offer_a_chart_picked_elsewhere(qtbot, ctx, project):
    dialog = _dialog(qtbot, ctx, project)
    first, second, _third = dialog.featured_combos
    first.setCurrentIndex(first.findData(project.chart_a.id))

    row = second.findData(project.chart_a.id)
    assert not second.model().item(row).isEnabled()
    assert second.model().item(second.findData(project.chart_b.id)).isEnabled()
    assert first.model().item(first.findData(project.chart_a.id)).isEnabled()

    first.setCurrentIndex(0)
    assert second.model().item(row).isEnabled()


def test_duplicate_featured_charts_collapse_keeping_the_first(qtbot, ctx, project):
    dialog = _dialog(qtbot, ctx, project)
    # A combo can be forced past the disabled entries (for example by code), so accept must still collapse.
    for combo, chart in zip(dialog.featured_combos, (project.chart_a, project.chart_a, project.chart_c), strict=True):
        combo.setCurrentIndex(combo.findData(chart.id))
    assert dialog.get_result().example_info.featured_chart_ids == (project.chart_a.id, project.chart_c.id)


def test_chart_names_are_disambiguated_in_the_combos(qtbot, ctx, project):
    dialog = _dialog(qtbot, ctx, project)
    labels = [dialog.featured_combos[0].itemText(row) for row in range(dialog.featured_combos[0].count())]
    assert labels[0] == "None"
    assert "Period" not in labels
    assert sum(label.startswith("Period") for label in labels) == 2
    assert "Amplitude" in labels
    assert [dialog.start_note_combo.itemText(row) for row in range(dialog.start_note_combo.count())] == ["None", "Read me"]


def test_stale_ids_are_not_shown_and_are_dropped_once_the_user_edits(qtbot, ctx, project):
    project.example_info = ExampleInfo(
        is_example=True, featured_chart_ids=("deleted-chart", project.chart_a.id), start_note_id="deleted-note")
    dialog = _dialog(qtbot, ctx, project)

    assert [combo.currentData() for combo in dialog.featured_combos] == [project.chart_a.id, None, None]
    assert dialog.start_note_combo.currentData() is None
    dialog.credit_edit.setText("Edited")
    info = dialog.get_result().example_info
    assert info.featured_chart_ids == (project.chart_a.id,)
    assert info.start_note_id is None


def test_untouched_dialog_returns_the_project_values_verbatim_and_the_command_is_a_noop(qtbot, ctx, project):
    from pandaplot.commands.base_command import CommandResult
    from pandaplot.commands.project.project import UpdateProjectDetailsCommand

    project.description = "line one\r\nline two\u00a0end  \r\n"
    project.example_info = ExampleInfo(
        is_example=True, summary="  padded summary  ", tag_ids=("smoothing", "physics"),
        featured_chart_ids=("deleted-chart", project.chart_a.id), start_note_id="deleted-note", data_credit=" credit ")
    dialog = _dialog(qtbot, ctx, project)

    result = dialog.get_result()

    assert result.name == project.name
    assert result.description == project.description
    assert result.cover_image == project.cover_image
    assert result.example_info == project.example_info
    app_state = Mock()
    app_state.has_project = True
    app_state.current_project = project
    ctx.get_app_state.return_value = app_state
    command = UpdateProjectDetailsCommand(
        ctx, name=result.name, description=result.description, cover_image=result.cover_image, example_info=result.example_info)
    assert command.execute() is CommandResult.NOOP


def test_untouched_fields_keep_their_stored_form_when_another_field_is_edited(qtbot, ctx, project):
    project.description = "a\r\nb  "
    project.example_info = ExampleInfo(is_example=True, summary=" spaced ", tag_ids=("smoothing", "physics"), data_credit=" c ")
    dialog = _dialog(qtbot, ctx, project)
    dialog.level_combo.setCurrentIndex(dialog.level_combo.findData(ExampleLevel.INTERMEDIATE.value))

    result = dialog.get_result()

    assert result.description == project.description
    assert result.example_info.summary == " spaced "
    assert result.example_info.data_credit == " c "
    assert result.example_info.tag_ids == ("smoothing", "physics")
    assert result.example_info.level is ExampleLevel.INTERMEDIATE

    dialog.tag_checkboxes["business"].setChecked(True)
    assert dialog.get_result().example_info.tag_ids != ("smoothing", "physics")


def test_choose_image_downscales_the_picked_file(qtbot, ctx, project, tmp_path):
    path = tmp_path / "big.png"
    path.write_bytes(_png(2000, 1000))
    dialog = _dialog(qtbot, ctx, project)

    with patch.object(module.QFileDialog, "getOpenFileName", return_value=(str(path), "")):
        dialog.choose_cover_button.click()

    cover = dialog.get_result().cover_image
    image = QImage.fromData(cover)
    assert max(image.width(), image.height()) == 800
    assert dialog.cover_label.pixmap().width() == COVER_THUMBNAIL_WIDTH
    assert dialog.remove_cover_button.isEnabled()


def test_cancelling_the_picker_keeps_the_cover(qtbot, ctx, project):
    project.cover_image = _png(10, 10)
    dialog = _dialog(qtbot, ctx, project)
    with patch.object(module.QFileDialog, "getOpenFileName", return_value=("", "")):
        dialog.choose_cover_button.click()
    assert dialog.get_result().cover_image == project.cover_image


def test_choosing_a_non_image_reports_an_error_and_keeps_the_cover(qtbot, ctx, project, tmp_path):
    project.cover_image = _png(10, 10)
    path = tmp_path / "notes.txt"
    path.write_text("not an image")
    dialog = _dialog(qtbot, ctx, project)

    with patch.object(module.QFileDialog, "getOpenFileName", return_value=(str(path), "")):
        dialog.choose_cover_button.click()

    show_error = ctx.get_ui_controller.return_value.show_error_message
    show_error.assert_called_once()
    args, kwargs = show_error.call_args
    assert args == ("Cover Image", "Couldn't use this image.")
    assert kwargs["error"] is not None
    assert dialog.get_result().cover_image == project.cover_image


def test_choosing_an_unreadable_file_reports_an_error(qtbot, ctx, project, tmp_path):
    dialog = _dialog(qtbot, ctx, project)
    with patch.object(module.QFileDialog, "getOpenFileName", return_value=(str(tmp_path / "missing.png"), "")):
        dialog.choose_cover_button.click()
    ctx.get_ui_controller.return_value.show_error_message.assert_called_once()


def test_choosing_a_file_over_the_size_limit_reports_the_size_message(qtbot, ctx, project, tmp_path):
    from pandaplot.services.project import cover_image

    project.cover_image = _png(10, 10)
    path = tmp_path / "big.png"
    path.write_bytes(_png(20, 20))
    dialog = _dialog(qtbot, ctx, project)

    with patch.object(cover_image, "MAX_COVER_FILE_BYTES", 5), patch.object(module.QFileDialog, "getOpenFileName", return_value=(str(path), "")):
        dialog.choose_cover_button.click()

    args, kwargs = ctx.get_ui_controller.return_value.show_error_message.call_args
    assert args == ("Cover Image", "Couldn't use this image.")
    assert "under 25 MB" in str(kwargs["error"])
    assert dialog.get_result().cover_image == project.cover_image


def test_remove_clears_the_cover(qtbot, ctx, project):
    project.cover_image = _png(50, 50)
    dialog = _dialog(qtbot, ctx, project)
    dialog.remove_cover_button.click()
    assert dialog.get_result().cover_image is None
    assert dialog.cover_label.text().startswith("No cover image")
    assert not dialog.remove_cover_button.isEnabled()


def test_preview_toggle_renders_markdown_and_toggles_back(qtbot, ctx, project):
    dialog = _dialog(qtbot, ctx, project)
    dialog.show()
    dialog.description_edit.setPlainText("# Title\n\nSome **bold** text")

    dialog.preview_button.setChecked(True)
    assert dialog.preview_browser.isVisible()
    assert not dialog.description_edit.isVisible()
    assert dialog.preview_browser.isReadOnly()
    html = dialog.preview_browser.toHtml()
    assert "Title" in html
    assert "font-weight" in html  # bold run
    assert "**bold**" not in dialog.preview_browser.toPlainText()

    dialog.preview_button.setChecked(False)
    assert dialog.description_edit.isVisible()
    assert not dialog.preview_browser.isVisible()


def test_clicking_a_preview_link_opens_external_urls_and_keeps_the_document(qtbot, ctx, project):
    from PySide6.QtCore import QUrl

    dialog = _dialog(qtbot, ctx, project)
    dialog.show()
    dialog.description_edit.setPlainText("See [site](https://example.com) and [local](other.md)")
    dialog.preview_button.setChecked(True)
    before = dialog.preview_browser.toHtml()
    assert dialog.preview_browser.openLinks() is False

    with patch.object(module.QDesktopServices, "openUrl") as open_url:
        dialog.preview_browser.anchorClicked.emit(QUrl("https://example.com"))
        dialog.preview_browser.anchorClicked.emit(QUrl("mailto:a@example.com"))
        dialog.preview_browser.anchorClicked.emit(QUrl("file:///etc/passwd"))
        dialog.preview_browser.anchorClicked.emit(QUrl("other.md"))

    assert [call.args[0].toString() for call in open_url.call_args_list] == ["https://example.com", "mailto:a@example.com"]
    assert dialog.preview_browser.toHtml() == before


def test_every_control_has_an_accessible_name_and_labels_have_buddies(qtbot, ctx, project):
    dialog = _dialog(qtbot, ctx, project)
    controls = [
        dialog.name_edit, dialog.description_edit, dialog.preview_button, dialog.choose_cover_button, dialog.remove_cover_button,
        dialog.example_checkbox, dialog.summary_edit, dialog.section_combo, dialog.level_combo, dialog.start_note_combo,
        dialog.credit_edit, *dialog.featured_combos, *dialog.tag_checkboxes.values(),
    ]
    assert all(control.accessibleName() for control in controls)
    assert [combo.accessibleName() for combo in dialog.featured_combos] == ["Featured chart 1", "Featured chart 2", "Featured chart 3"]
    assert all(control.focusPolicy() != Qt.FocusPolicy.NoFocus for control in controls)
    labels = [label for label in dialog.findChildren(module.QLabel) if label.buddy() is not None]
    assert {label.text() for label in labels} >= {"Name", "About this project", "Section", "Level", "Short description", "Start here note"}


def test_dialog_follows_the_theme_tokens(qtbot, ctx, project):
    dialog = _dialog(qtbot, ctx, project)
    tokens = ctx.get_manager.return_value.get_design_tokens()
    assert tokens["surface_white"] in dialog.styleSheet()


class TestEditProjectDetails:
    """The entry-point helper shared by the File menu and the project tree."""

    @pytest.fixture
    def wired(self, ctx, project):
        app_state = Mock()
        app_state.has_project = True
        app_state.current_project = project
        ctx.get_app_state.return_value = app_state
        executor = Mock()
        executor.execute_command.return_value = True
        ctx.get_command_executor.return_value = executor
        return ctx, executor

    def test_accepted_dialog_executes_the_command_with_the_chosen_values(self, qapp, wired, project):
        ctx, executor = wired
        with patch.object(ProjectDetailsDialog, "exec", return_value=QDialog.DialogCode.Accepted):
            assert edit_project_details(ctx) is True

        command = executor.execute_command.call_args.args[0]
        assert command.__class__.__name__ == "UpdateProjectDetailsCommand"
        assert command._new.name == "Pendulum"
        assert command._new.description == project.description

    def test_rejected_dialog_executes_nothing(self, qapp, wired):
        ctx, executor = wired
        with patch.object(ProjectDetailsDialog, "exec", return_value=QDialog.DialogCode.Rejected):
            assert edit_project_details(ctx) is False
        executor.execute_command.assert_not_called()

    def test_no_project_opens_no_dialog(self, qapp, wired):
        ctx, _executor = wired
        ctx.get_app_state.return_value.has_project = False
        with patch.object(ProjectDetailsDialog, "exec") as exec_mock:
            assert edit_project_details(ctx) is False
        exec_mock.assert_not_called()
