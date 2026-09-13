"""Smoke tests for TransformPanel construction.

TransformPanel moved its `apply_btn`/`clear_btn`/`preview_btn` `.clicked.connect(...)`
calls into the constructor via PButton's `on_click=` param. Nothing previously
constructed TransformPanel in tests, so a future construction-order regression would
go unnoticed. These tests just build the panel and check the buttons exist.
"""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.sidebar.transform.transform_panel import TransformPanel
from pandaplot.models.state.app_context import AppContext


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
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

    assert transform_panel.preview_text.toPlainText() == (
        "Transform failed: Column 'a_x2' already exists. Choose a different name or enable replace option."
    )


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

    assert transform_panel.preview_text.toPlainText() == "Transform failed - see logs for details"


class TestApplyValidationFeedback:
    """Regression (#227): clicking Apply without first clicking Preview
    used to silently do nothing on a validation failure -- only a
    logger.warning(), no visible feedback at all."""

    def test_no_source_column_selected_writes_a_visible_message(self, transform_panel):
        transform_panel.current_dataset = Mock(id="dataset-1", data=Mock(columns=["a"]))
        transform_panel._populate_column_list(["a"])
        # No item selected.

        transform_panel.apply_transform()

        assert transform_panel.preview_text.toPlainText() == "Select a source column before applying."

    def test_empty_new_column_name_writes_a_visible_message(self, transform_panel):
        transform_panel.current_dataset = Mock(id="dataset-1", data=Mock(columns=["a"]))
        transform_panel._populate_column_list(["a"])
        transform_panel.source_column_list.item(0).setSelected(True)
        transform_panel.function_text.setPlainText("x * 2")
        # Selecting a column auto-suggests a name; clear it back out to
        # exercise the "no name" branch specifically.
        transform_panel.new_column_name.clear()

        transform_panel.apply_transform()

        assert transform_panel.preview_text.toPlainText() == "Enter a name for the new column before applying."

    def test_empty_function_writes_a_visible_message(self, transform_panel):
        transform_panel.current_dataset = Mock(id="dataset-1", data=Mock(columns=["a"]))
        transform_panel._populate_column_list(["a"])
        transform_panel.source_column_list.item(0).setSelected(True)
        transform_panel.new_column_name.setText("b")
        # function_text left empty.

        transform_panel.apply_transform()

        assert transform_panel.preview_text.toPlainText() == "Enter a function before applying."

    def test_missing_dataset_id_writes_a_visible_message(self, transform_panel):
        transform_panel.current_dataset = Mock(id=None, data=Mock(columns=["a"]))
        transform_panel._populate_column_list(["a"])
        transform_panel.source_column_list.item(0).setSelected(True)
        transform_panel.new_column_name.setText("b")
        transform_panel.function_text.setPlainText("x * 2")

        transform_panel.apply_transform()

        assert transform_panel.preview_text.toPlainText() == "No dataset selected."


class TestApplyButtonEnablement:
    """Regression (#227 broader UX ask): disable Apply until the fields it
    needs are actually filled in, instead of leaving it clickable for a
    guaranteed-to-fail click."""

    def test_apply_disabled_with_no_dataset(self, transform_panel):
        assert transform_panel.apply_btn.isEnabled() is False

    def test_apply_stays_disabled_until_every_field_is_filled(self, transform_panel):
        transform_panel.enable_controls(enabled=True)
        assert transform_panel.apply_btn.isEnabled() is False

        transform_panel._populate_column_list(["a"])
        transform_panel.source_column_list.item(0).setSelected(True)
        assert transform_panel.apply_btn.isEnabled() is False

        transform_panel.new_column_name.setText("b")
        assert transform_panel.apply_btn.isEnabled() is False

        transform_panel.function_text.setPlainText("x * 2")
        assert transform_panel.apply_btn.isEnabled() is True

    def test_clearing_the_function_disables_apply_again(self, transform_panel):
        transform_panel.enable_controls(enabled=True)
        transform_panel._populate_column_list(["a"])
        transform_panel.source_column_list.item(0).setSelected(True)
        transform_panel.new_column_name.setText("b")
        transform_panel.function_text.setPlainText("x * 2")
        assert transform_panel.apply_btn.isEnabled() is True

        transform_panel.function_text.clear()

        assert transform_panel.apply_btn.isEnabled() is False

    def test_disabling_controls_disables_apply_regardless_of_filled_fields(self, transform_panel):
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
