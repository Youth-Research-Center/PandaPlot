"""Smoke tests for TransformPanel construction.

TransformPanel moved its `apply_btn`/`clear_btn`/`preview_btn` `.clicked.connect(...)`
calls into the constructor via PButton's `on_click=` param. Nothing previously
constructed TransformPanel in tests, so a future construction-order regression would
go unnoticed. These tests just build the panel and check the buttons exist.
"""
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.common.status_message import StatusKind
from pandaplot.gui.components.sidebar.transform.transform_panel import TransformPanel
from pandaplot.models.state.app_context import AppContext
from tests.gui.icon_testing import ICON_TOKENS, assert_tinted, strongest_pixel


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    ctx.get_manager.return_value.get_design_tokens.return_value = {"font_size_group_title": 9, **ICON_TOKENS}
    return ctx


@pytest.fixture
def transform_panel(app_context):
    return TransformPanel(app_context)


def test_transform_panel_constructs_with_expected_buttons(transform_panel):
    assert isinstance(transform_panel.apply_btn, PButton)
    assert isinstance(transform_panel.clear_btn, PButton)
    assert isinstance(transform_panel.preview_btn, PButton)


def test_preview_button_click_invokes_update_preview(transform_panel):
    transform_panel.preview_text.setPlainText("stale")

    transform_panel.preview_btn.click()

    assert transform_panel.preview_text.toPlainText() == "No data available for preview"


def test_controller_transform_failed_surfaces_message_in_preview(transform_panel):
    transform_panel.on_controller_transform_failed(
        "dataset-1", "Column 'a_x2' already exists. Choose a different name or enable replace option."
    )

    assert transform_panel.status_message.message() == (
        "Transform failed: Column 'a_x2' already exists. Choose a different name or enable replace option."
    )
    assert transform_panel.status_message.kind() is StatusKind.ERROR
    assert transform_panel.preview_text.toPlainText() == ""


def test_on_dataset_renamed_refreshes_label_for_active_dataset(transform_panel):
    """Regression: the dataset name label only refreshed on UIEvents.TAB_CHANGED,
    so renaming the dataset while its Transform panel stayed open (no tab
    switch) left the label showing the old name."""
    dataset = Mock(id="dataset-1", data=None)
    dataset.name = "Renamed Dataset"
    transform_panel.current_dataset = dataset

    transform_panel.on_dataset_renamed({"item_id": "dataset-1", "new_name": "Renamed Dataset"})

    assert transform_panel.dataset_label.text() == "Renamed Dataset"


def test_on_dataset_renamed_ignores_other_items(transform_panel):
    dataset = Mock(id="dataset-1", data=None)
    dataset.name = "Original"
    transform_panel.current_dataset = dataset
    transform_panel.dataset_label.setText("Original")

    transform_panel.on_dataset_renamed({"item_id": "other-id", "new_name": "Should Not Apply"})

    assert transform_panel.dataset_label.text() == "Original"


def test_apply_transform_generic_failure_surfaces_message_when_no_signal_fired(transform_panel, app_context):
    transform_panel.current_dataset = Mock(id="dataset-1", data=Mock(columns=["a"]))
    transform_panel._populate_column_list(["a"])
    transform_panel.source_column_list.item(0).setSelected(True)
    transform_panel.new_column_name.setText("b")
    transform_panel.function_text.setPlainText("x * 2")
    transform_panel.transform_controller.apply_transformation = Mock(return_value=False)

    transform_panel.apply_transform()

    assert transform_panel.status_message.message() == "Transform failed - see logs for details"

    assert transform_panel.status_message.kind() is StatusKind.ERROR

    assert transform_panel.preview_text.toPlainText() == ""


class TestApplyValidationFeedback:
    """Regression (#227): clicking Apply without first clicking Preview
    used to silently do nothing on a validation failure -- only a
    logger.warning(), no visible feedback at all."""

    def test_no_dataset_at_all_writes_a_dataset_specific_message(self, transform_panel):
        """Regression: this used to share the "select a source column"
        message with the no-column case below, which was misleading when
        there was no dataset active to select a column from at all."""
        transform_panel.current_dataset = None

        transform_panel.apply_transform()

        assert transform_panel.status_message.message() == "No dataset selected."

        assert transform_panel.status_message.kind() is StatusKind.ERROR

        assert transform_panel.preview_text.toPlainText() == ""

    def test_no_source_column_selected_writes_a_visible_message(self, transform_panel):
        transform_panel.current_dataset = Mock(id="dataset-1", data=Mock(columns=["a"]))
        transform_panel._populate_column_list(["a"])
        # No item selected.

        transform_panel.apply_transform()

        assert transform_panel.status_message.message() == "Select a source column before applying."

        assert transform_panel.status_message.kind() is StatusKind.ERROR

        assert transform_panel.preview_text.toPlainText() == ""

    def test_empty_new_column_name_writes_a_visible_message(self, transform_panel):
        transform_panel.current_dataset = Mock(id="dataset-1", data=Mock(columns=["a"]))
        transform_panel._populate_column_list(["a"])
        transform_panel.source_column_list.item(0).setSelected(True)
        transform_panel.function_text.setPlainText("x * 2")
        # Selecting a column auto-suggests a name; clear it back out to
        # exercise the "no name" branch specifically.
        transform_panel.new_column_name.clear()

        transform_panel.apply_transform()

        assert transform_panel.status_message.message() == "Enter a name for the new column before applying."

        assert transform_panel.status_message.kind() is StatusKind.ERROR

        assert transform_panel.preview_text.toPlainText() == ""

    def test_empty_function_writes_a_visible_message(self, transform_panel):
        transform_panel.current_dataset = Mock(id="dataset-1", data=Mock(columns=["a"]))
        transform_panel._populate_column_list(["a"])
        transform_panel.source_column_list.item(0).setSelected(True)
        transform_panel.new_column_name.setText("b")
        # function_text left empty.

        transform_panel.apply_transform()

        assert transform_panel.status_message.message() == "Enter a function before applying."

        assert transform_panel.status_message.kind() is StatusKind.ERROR

        assert transform_panel.preview_text.toPlainText() == ""

    def test_missing_dataset_id_writes_a_visible_message(self, transform_panel):
        transform_panel.current_dataset = Mock(id=None, data=Mock(columns=["a"]))
        transform_panel._populate_column_list(["a"])
        transform_panel.source_column_list.item(0).setSelected(True)
        transform_panel.new_column_name.setText("b")
        transform_panel.function_text.setPlainText("x * 2")

        transform_panel.apply_transform()

        assert transform_panel.status_message.message() == "Selected dataset is unavailable. Try reselecting it."

        assert transform_panel.status_message.kind() is StatusKind.ERROR

        assert transform_panel.preview_text.toPlainText() == ""

    def test_preview_with_missing_dataset_id_writes_the_same_message(self, transform_panel):
        transform_panel.current_dataset = Mock(id=None, data=Mock(columns=["a"]))
        transform_panel._populate_column_list(["a"])
        transform_panel.source_column_list.item(0).setSelected(True)
        transform_panel.function_text.setPlainText("x * 2")

        transform_panel.update_preview()

        assert transform_panel.status_message.message() == "Selected dataset is unavailable. Try reselecting it."

        assert transform_panel.status_message.kind() is StatusKind.ERROR

        assert transform_panel.preview_text.toPlainText() == ""
        assert transform_panel._preview_has_error is True


class TestPreviewErrorStyling:
    """An error message in preview_text should be visually distinct (#227
    review follow-up) rather than reading like any other preview text --
    it gets a red-ish stylesheet, cleared once the offending field changes."""

    def test_validation_error_marks_preview_text_as_errored(self, transform_panel):
        transform_panel.current_dataset = Mock(id="dataset-1", data=Mock(columns=["a"]))
        transform_panel._populate_column_list(["a"])
        # No item selected -- triggers the "select a source column" error.

        transform_panel.apply_transform()

        assert transform_panel._preview_has_error is True

    def test_error_styling_keeps_the_base_theme_qss(self, transform_panel):
        """Regression: setting an error color used to replace preview_text's
        whole stylesheet, dropping the background/border/padding _apply_theme()
        installs -- not just the foreground color."""
        transform_panel.current_dataset = Mock(id="dataset-1", data=Mock(columns=["a"]))
        transform_panel._populate_column_list(["a"])

        transform_panel.apply_transform()

        style = transform_panel.preview_text.styleSheet()
        assert "border" in style
        assert "background-color" in style

    def test_successful_preview_clears_any_error_styling(self, transform_panel):
        transform_panel.current_dataset = Mock(id="dataset-1", data=Mock(columns=["a"]))
        transform_panel._populate_column_list(["a"])
        transform_panel.apply_transform()  # No column selected -- leaves an error style behind.
        assert transform_panel._preview_has_error is True

        transform_panel.source_column_list.item(0).setSelected(True)

        assert transform_panel._preview_has_error is False
        # Regression: only the red styling used to clear, leaving the stale
        # (and now wrong) "select a source column" text still displayed
        # after a column had actually just been selected.
        assert transform_panel.preview_text.toPlainText() == ""

    def test_editing_a_field_after_an_error_clears_the_error_styling(self, transform_panel):
        transform_panel.current_dataset = Mock(id="dataset-1", data=Mock(columns=["a"]))
        transform_panel._populate_column_list(["a"])
        transform_panel.source_column_list.item(0).setSelected(True)
        transform_panel.new_column_name.setText("b")
        # function_text left empty -- triggers the "enter a function" error.
        transform_panel.apply_transform()
        assert transform_panel._preview_has_error is True

        transform_panel.function_text.setPlainText("x * 2")

        assert transform_panel._preview_has_error is False
        assert transform_panel.preview_text.toPlainText() == ""

    def test_toggling_replace_after_an_error_clears_the_error_styling(self, transform_panel):
        """Regression: a duplicate-column failure tells the user to enable
        Replace, but toggling that checkbox didn't invoke
        _update_apply_enabled -- only selection/text signals did -- so the
        stale red failure stayed displayed even after following its own
        suggested fix."""
        transform_panel.current_dataset = Mock(id="dataset-1", data=Mock(columns=["a"]))
        transform_panel._set_preview_message("Column 'a_x2' already exists.", is_error=True)
        assert transform_panel._preview_has_error is True

        transform_panel.replace_column_check.setChecked(True)

        assert transform_panel._preview_has_error is False
        assert transform_panel.preview_text.toPlainText() == ""
        assert transform_panel.status_message.message() == ""


class TestPreviewStatusMessage:
    """Errors show through the panel's status_message (icon + text); ordinary previews stay in the text area."""

    def test_status_message_sits_directly_above_the_preview_text(self, transform_panel):
        layout = transform_panel.preview_text.parentWidget().layout()

        assert layout.indexOf(transform_panel.status_message) == layout.indexOf(transform_panel.preview_text) - 1

    def test_an_error_message_replaces_the_preview_text(self, transform_panel):
        transform_panel.preview_text.setPlainText("old preview")

        transform_panel._set_preview_message("Something broke", is_error=True)

        assert transform_panel.status_message.message() == "Something broke"
        assert transform_panel.status_message.kind() is StatusKind.ERROR
        assert transform_panel.preview_text.toPlainText() == ""

    def test_an_ordinary_message_goes_to_the_text_area_and_clears_the_status(self, transform_panel):
        transform_panel._set_preview_message("Something broke", is_error=True)

        transform_panel._set_preview_message("Enter a function to preview")

        assert transform_panel.status_message.message() == ""
        assert transform_panel.status_message.kind() is None
        assert transform_panel.preview_text.toPlainText() == "Enter a function to preview"
        assert transform_panel._preview_has_error is False

    def test_error_text_is_not_recoloured(self, transform_panel):
        transform_panel._set_preview_message("Something broke", is_error=True)

        assert "status_danger" not in transform_panel.preview_text.styleSheet()
        assert "#DC3545" not in transform_panel.preview_text.styleSheet()

    def test_clear_panel_clears_the_status_message(self, transform_panel):
        transform_panel._set_preview_message("Something broke", is_error=True)

        transform_panel.clear_panel()

        assert transform_panel.status_message.message() == ""

    def test_theme_change_retints_the_status_icon(self, transform_panel, app_context):
        transform_panel._set_preview_message("Something broke", is_error=True)
        app_context.get_manager.return_value.get_design_tokens.return_value["status_danger"] = "#00AA00"

        transform_panel._apply_theme()

        icon = transform_panel.status_message.findChild(IconLabel)
        assert_tinted(strongest_pixel(icon.pixmap()), "#00AA00")


class TestApplyButtonEnablement:
    """Regression (#227 broader UX ask): disable Apply until the fields it
    needs are actually filled in, instead of leaving it clickable for a
    guaranteed-to-fail click."""

    def test_apply_disabled_with_no_dataset(self, transform_panel):
        assert transform_panel.apply_btn.isEnabled() is False

    def test_apply_stays_disabled_until_every_field_is_filled(self, transform_panel):
        transform_panel.current_dataset = Mock(id="dataset-1")
        transform_panel.enable_controls(enabled=True)
        assert transform_panel.apply_btn.isEnabled() is False

        transform_panel._populate_column_list(["a"])
        transform_panel.source_column_list.item(0).setSelected(True)
        assert transform_panel.apply_btn.isEnabled() is False

        transform_panel.new_column_name.setText("b")
        assert transform_panel.apply_btn.isEnabled() is False

        transform_panel.function_text.setPlainText("x * 2")
        assert transform_panel.apply_btn.isEnabled() is True

    def test_apply_stays_disabled_when_dataset_id_is_unavailable(self, transform_panel):
        """Regression: readiness used to only check that controls were
        enabled, not that current_dataset actually had a usable id -- so
        Apply could become clickable for a dataset apply_transform() was
        guaranteed to then reject."""
        transform_panel.current_dataset = Mock(id=None)
        transform_panel.enable_controls(enabled=True)
        transform_panel._populate_column_list(["a"])
        transform_panel.source_column_list.item(0).setSelected(True)
        transform_panel.new_column_name.setText("b")
        transform_panel.function_text.setPlainText("x * 2")

        assert transform_panel.apply_btn.isEnabled() is False

    def test_clearing_the_function_disables_apply_again(self, transform_panel):
        transform_panel.current_dataset = Mock(id="dataset-1")
        transform_panel.enable_controls(enabled=True)
        transform_panel._populate_column_list(["a"])
        transform_panel.source_column_list.item(0).setSelected(True)
        transform_panel.new_column_name.setText("b")
        transform_panel.function_text.setPlainText("x * 2")
        assert transform_panel.apply_btn.isEnabled() is True

        transform_panel.function_text.clear()

        assert transform_panel.apply_btn.isEnabled() is False

    def test_disabling_controls_disables_apply_regardless_of_filled_fields(self, transform_panel):
        transform_panel.current_dataset = Mock(id="dataset-1")
        transform_panel.enable_controls(enabled=True)
        transform_panel._populate_column_list(["a"])
        transform_panel.source_column_list.item(0).setSelected(True)
        transform_panel.new_column_name.setText("b")
        transform_panel.function_text.setPlainText("x * 2")
        assert transform_panel.apply_btn.isEnabled() is True

        transform_panel.enable_controls(enabled=False)

        assert transform_panel.apply_btn.isEnabled() is False


class TestSourceColumnMarkers:
    """Regression (#203): which column `x` refers to is marked directly on
    the source_column_list's own items, rather than in a separate summary
    label duplicating what the list already shows."""

    def test_unselected_items_show_the_plain_column_name(self, transform_panel):
        transform_panel._populate_column_list(["temp"])

        assert transform_panel.source_column_list.item(0).text() == "temp"

    def test_selecting_a_column_marks_it_as_the_x_variable(self, transform_panel):
        transform_panel._populate_column_list(["temp"])

        transform_panel.source_column_list.item(0).setSelected(True)

        item = transform_panel.source_column_list.item(0)
        assert item.text() == "temp  →  x"
        assert item.font().bold() is True
        # The real name used for the transform must stay exactly "temp",
        # unaffected by the decorated display text.
        assert transform_panel.get_selected_columns() == ["temp"]

    def test_extra_selected_columns_are_marked_as_not_used(self, transform_panel):
        """Only the first selected column is ever used
        (_execute_column_operation), so selecting more must not silently
        look like they all feed the expression."""
        transform_panel._populate_column_list(["a", "b"])

        transform_panel.source_column_list.item(0).setSelected(True)
        transform_panel.source_column_list.item(1).setSelected(True)

        assert transform_panel.source_column_list.item(0).text() == "a  →  x"
        assert transform_panel.source_column_list.item(1).text() == "b  (not used)"
        assert transform_panel.get_selected_columns() == ["a", "b"]

    def test_marker_clears_when_selection_is_cleared(self, transform_panel):
        transform_panel._populate_column_list(["a"])
        transform_panel.source_column_list.item(0).setSelected(True)
        assert transform_panel.source_column_list.item(0).text() == "a  →  x"

        transform_panel.source_column_list.item(0).setSelected(False)

        assert transform_panel.source_column_list.item(0).text() == "a"

    def test_marker_works_for_a_column_name_with_a_space(self, transform_panel):
        """A column name with a space (or any other non-identifier name)
        marks and selects exactly like any other -- unlike bare-identifier
        binding, cols["name"] (see TransformColumnCommand) has no
        restrictions on the real column name."""
        transform_panel._populate_column_list(["my col"])

        transform_panel.source_column_list.item(0).setSelected(True)

        assert transform_panel.source_column_list.item(0).text() == "my col  →  x"
        assert transform_panel.get_selected_columns() == ["my col"]


class TestFormulaColumnCheckboxes:
    """Issue #154: live recompute is opt-in per column, so the panel offers
    "save as formula" and, only then, "live"."""

    def test_both_options_are_off_by_default(self, transform_panel):
        assert transform_panel.formula_column_check.isChecked() is False
        assert transform_panel.live_recompute_check.isChecked() is False

    def test_live_option_is_hidden_until_a_formula_column_is_requested(self, transform_panel):
        # isHidden(), not isVisible(): the panel itself is never shown in a
        # test, which would make isVisible() False either way.
        assert transform_panel.live_recompute_check.isHidden() is True

        transform_panel.formula_column_check.setChecked(True)
        assert transform_panel.live_recompute_check.isHidden() is False

    def test_live_option_tells_the_user_the_column_becomes_read_only(self, transform_panel):
        assert "read-only" in transform_panel.live_recompute_check.toolTip()

    def test_unchecking_formula_also_clears_live(self, transform_panel):
        transform_panel.formula_column_check.setChecked(True)
        transform_panel.live_recompute_check.setChecked(True)

        transform_panel.formula_column_check.setChecked(False)

        assert transform_panel.live_recompute_check.isChecked() is False

    def test_clear_panel_resets_both_options(self, transform_panel):
        transform_panel.formula_column_check.setChecked(True)
        transform_panel.live_recompute_check.setChecked(True)

        transform_panel.clear_panel()

        assert transform_panel.formula_column_check.isChecked() is False
        assert transform_panel.live_recompute_check.isChecked() is False


def test_column_rename_refreshes_active_dataset_column_list(transform_panel, app_context):
    from pandaplot.models.events import DatasetOperationEvents

    handlers = [call.args[1] for call in app_context.event_bus.subscribe.call_args_list
                if call.args[0] == DatasetOperationEvents.DATASET_COLUMN_RENAMED]
    assert len(handlers) == 1
    transform_panel.current_dataset = Mock(id="dataset-1")
    transform_panel.refresh_column_list = Mock()

    handlers[0]({"dataset_id": "other"})
    transform_panel.refresh_column_list.assert_not_called()
    handlers[0]({"dataset_id": "dataset-1", "old_name": "a", "new_name": "alpha"})
    transform_panel.refresh_column_list.assert_called_once_with(keep=[])


class TestColumnEventsKeepSourceSelection:
    """Column add/remove/rename rebuild the source list; the user's source column
    must stay selected (following a rename) so Apply stays ready."""

    @staticmethod
    def _ready_panel(transform_panel, app_context, selected):
        import pandas as pd

        from pandaplot.models.events import DatasetOperationEvents

        dataset = Mock(id="dataset-1", data=pd.DataFrame({"a": [1.0], "b": [2.0], "c": [3.0]}))
        dataset.name = "dataset"
        transform_panel.set_active_dataset(dataset)
        transform_panel.refresh_column_list()
        items = {
            transform_panel.source_column_list.item(i).data(Qt.ItemDataRole.UserRole): transform_panel.source_column_list.item(i)
            for i in range(transform_panel.source_column_list.count())
        }
        for name in selected:  # in order: the first selected column is the one `x` refers to
            items[name].setSelected(True)
        assert transform_panel.get_selected_columns() == selected
        transform_panel.new_column_name.setText("result")
        transform_panel.function_text.setPlainText("x * 2")
        assert transform_panel.apply_btn.isEnabled() is True
        handlers = {
            event: call.args[1]
            for call in app_context.event_bus.subscribe.call_args_list
            for event in (DatasetOperationEvents.DATASET_COLUMN_RENAMED, DatasetOperationEvents.DATASET_COLUMN_REMOVED)
            if call.args[0] == event
        }
        return dataset, handlers

    def test_renaming_another_column_keeps_source_selection(self, transform_panel, app_context):
        from pandaplot.models.events import DatasetOperationEvents

        dataset, handlers = self._ready_panel(transform_panel, app_context, ["b"])
        dataset.data.rename(columns={"a": "alpha"}, inplace=True)
        handlers[DatasetOperationEvents.DATASET_COLUMN_RENAMED]({"dataset_id": "dataset-1", "old_name": "a", "new_name": "alpha"})

        assert transform_panel.get_selected_columns() == ["b"]
        assert transform_panel.apply_btn.isEnabled() is True

    def test_renaming_the_source_column_follows_it(self, transform_panel, app_context):
        from pandaplot.models.events import DatasetOperationEvents

        dataset, handlers = self._ready_panel(transform_panel, app_context, ["b"])
        dataset.data.rename(columns={"b": "beta"}, inplace=True)
        handlers[DatasetOperationEvents.DATASET_COLUMN_RENAMED]({"dataset_id": "dataset-1", "old_name": "b", "new_name": "beta"})

        assert transform_panel.get_selected_columns() == ["beta"]
        assert transform_panel.source_column_list.item(1).text() == "beta  →  x"

    def test_removing_another_column_keeps_source_selection(self, transform_panel, app_context):
        from pandaplot.models.events import DatasetOperationEvents

        dataset, handlers = self._ready_panel(transform_panel, app_context, ["c"])
        dataset.data.drop(columns=["a"], inplace=True)
        handlers[DatasetOperationEvents.DATASET_COLUMN_REMOVED]({"dataset_id": "dataset-1"})

        assert transform_panel.get_selected_columns() == ["c"]
        assert transform_panel.apply_btn.isEnabled() is True

    def test_removing_the_x_column_clears_source_selection_and_preview(self, transform_panel, app_context):
        """Regression (PR #535 review): a "(not used)" column must not silently become `x`."""
        from pandaplot.models.events import DatasetOperationEvents

        dataset, handlers = self._ready_panel(transform_panel, app_context, ["b", "c"])
        transform_panel._set_preview_message("Source (b): 2.0")
        dataset.data.drop(columns=["b"], inplace=True)
        handlers[DatasetOperationEvents.DATASET_COLUMN_REMOVED]({"dataset_id": "dataset-1"})

        assert transform_panel.get_selected_columns() == []
        assert transform_panel.apply_btn.isEnabled() is False
        assert transform_panel.preview_text.toPlainText() == ""

    def test_removing_a_not_used_column_keeps_x_and_the_preview(self, transform_panel, app_context):
        """Only `x` (the first selected column) feeds the transform, so losing an extra selection changes nothing."""
        from pandaplot.models.events import DatasetOperationEvents

        dataset, handlers = self._ready_panel(transform_panel, app_context, ["b", "c"])
        transform_panel._set_preview_message("Source (b): 2.0")
        dataset.data.drop(columns=["c"], inplace=True)
        handlers[DatasetOperationEvents.DATASET_COLUMN_REMOVED]({"dataset_id": "dataset-1"})

        assert transform_panel.get_selected_columns() == ["b"]
        assert transform_panel.apply_btn.isEnabled() is True
        assert transform_panel.preview_text.toPlainText() == "Source (b): 2.0"

    def test_selection_order_survives_a_rename_so_x_does_not_change(self, transform_panel, app_context):
        from pandaplot.models.events import DatasetOperationEvents

        dataset, handlers = self._ready_panel(transform_panel, app_context, ["c", "b"])
        dataset.data.rename(columns={"a": "alpha"}, inplace=True)
        handlers[DatasetOperationEvents.DATASET_COLUMN_RENAMED]({"dataset_id": "dataset-1", "old_name": "a", "new_name": "alpha"})

        assert transform_panel.get_selected_columns() == ["c", "b"]
        assert transform_panel.source_column_list.item(2).text() == "c  →  x"


def test_int_column_labels_are_listed_and_follow_renames(transform_panel, app_context):
    """Excel imports keep numeric headers as int labels; the list must show them and follow their renames."""
    import pandas as pd

    from pandaplot.models.events import DatasetOperationEvents

    dataset = Mock(id="dataset-1", data=pd.DataFrame({2020: [1.0], "b": [2.0]}))
    dataset.name = "dataset"
    transform_panel.set_active_dataset(dataset)
    transform_panel.refresh_column_list()
    assert transform_panel.source_column_list.item(0).text() == "2020"
    transform_panel.source_column_list.item(0).setSelected(True)
    assert transform_panel.get_selected_columns() == [2020]
    handler = next(call.args[1] for call in app_context.event_bus.subscribe.call_args_list
                   if call.args[0] == DatasetOperationEvents.DATASET_COLUMN_RENAMED)

    dataset.data.rename(columns={2020: "y2020"}, inplace=True)
    handler({"dataset_id": "dataset-1", "old_name": 2020, "new_name": "y2020"})
    assert transform_panel.get_selected_columns() == ["y2020"]

    dataset.data.rename(columns={"y2020": 2020}, inplace=True)  # undo
    handler({"dataset_id": "dataset-1", "old_name": "y2020", "new_name": 2020})
    assert transform_panel.get_selected_columns() == [2020]
