"""Tests for BaseAnalysisDialog segment index -> (x, y) preview labels."""
import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.analysis.base_analysis_dialog import BaseAnalysisDialog
from pandaplot.models.project.items.dataset import Dataset


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def dataset():
    t = np.linspace(0.0, 10.0, 101)
    return Dataset(id="ds-1", name="Data", data=pd.DataFrame({"t": t, "sq": t ** 2}))


@pytest.fixture
def dialog(dataset):
    return BaseAnalysisDialog(None, dataset)


class TestBaseAnalysisDialogRangeLabels:
    def test_start_label_updates_on_row_number_change(self, dialog):
        # Row 11 (1-based) is the 0-based index 10.
        dialog.start_index.setValue(11)

        assert dialog.start_value_label.text() == "x=1, y=1"

    def test_end_row_defaults_to_the_last_row(self, dialog):
        assert dialog.start_index.minimum() == 1
        assert dialog.end_index.minimum() == 1
        assert dialog.end_index.value() == 101
        assert dialog.end_value_label.text() == "x=10, y=100"

    def test_end_row_shrinks_the_segment_when_decreased(self, dialog):
        dialog.end_index.setValue(dialog.end_index.value() - 1)

        assert dialog.end_value_label.text() == "x=9.9, y=98.01"

    def test_get_analysis_config_converts_row_numbers_to_engine_indices(self, dialog):
        dialog.start_index.setValue(1)
        dialog.end_index.setValue(50)
        dialog.result_column_name.setText("result")

        params = dialog.get_analysis_config()["parameters"]
        assert params["start_index"] == 0
        assert params["end_index"] == 50

    def test_labels_update_on_column_change(self, dialog):
        # Row 21 (1-based) is the 0-based index 20.
        dialog.start_index.setValue(21)
        assert dialog.start_value_label.text() == "x=2, y=4"

        dialog.x_column_combo.setCurrentText("sq")
        dialog.y_column_combo.setCurrentText("t")

        assert dialog.start_value_label.text() == "x=4, y=2"

    def test_no_dataset_shows_placeholder(self):
        dialog = BaseAnalysisDialog(None, None)

        assert dialog.start_value_label.text() == "–"
        assert dialog.end_value_label.text() == "–"
