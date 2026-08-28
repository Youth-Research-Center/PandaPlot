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
    transform_panel.source_column_list.addItem("a")
    transform_panel.source_column_list.item(0).setSelected(True)
    transform_panel.new_column_name.setText("b")
    transform_panel.function_text.setPlainText("x * 2")
    transform_panel.transform_controller.apply_transformation = Mock(return_value=False)

    transform_panel.apply_transform()

    assert transform_panel.preview_text.toPlainText() == "Transform failed - see logs for details"
