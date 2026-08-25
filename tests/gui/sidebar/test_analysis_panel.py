"""Tests for AnalysisPanel segment index -> (x, y) preview labels."""
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.sidebar.analysis.analysis_panel import AnalysisPanel
from pandaplot.models.project.items.dataset import Dataset
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
def dataset():
    t = np.linspace(0.0, 10.0, 101)
    return Dataset(id="ds-1", name="Data", data=pd.DataFrame({"t": t, "sq": t ** 2}))


@pytest.fixture
def panel(app_context, dataset):
    panel = AnalysisPanel(app_context)
    panel.current_dataset = dataset
    panel.current_dataset_id = "ds-1"
    panel.update_column_choices()
    return panel


class TestAnalysisPanelRangeLabels:
    def test_labels_show_placeholder_without_dataset(self, app_context):
        panel = AnalysisPanel(app_context)

        assert panel.start_value_label.text() == "–"
        assert panel.end_value_label.text() == "–"

    def test_end_row_defaults_to_the_last_row(self, panel):
        assert panel.start_index.minimum() == 1
        assert panel.end_index.minimum() == 1
        assert panel.end_index.value() == 101
        assert panel.end_value_label.text() == "x=10, y=100"

    def test_start_label_updates_on_row_number_change(self, panel):
        # Row 11 (1-based) is the 0-based index 10.
        panel.start_index.setValue(11)

        assert panel.start_value_label.text() == "x=1, y=1"

    def test_end_row_shrinks_the_segment_when_decreased(self, panel):
        panel.end_index.setValue(panel.end_index.value() - 1)

        assert panel.end_value_label.text() == "x=9.9, y=98.01"

    def test_get_analysis_config_converts_row_numbers_to_engine_indices(self, panel):
        panel.start_index.setValue(1)
        panel.end_index.setValue(50)
        panel.result_column_name.setText("result")

        params = panel.get_analysis_config()["parameters"]
        assert params["start_index"] == 0
        assert params["end_index"] == 50
