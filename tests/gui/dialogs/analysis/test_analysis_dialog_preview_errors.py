"""A failing preview in an analysis dialog shows a plain reason and logs the failure."""
import logging
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.analysis.smoothing_dialog import SmoothingDialog
from pandaplot.models.project.items.dataset import Dataset


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_smoothing_preview_failure_is_plain_and_logged(caplog):
    t = np.linspace(0.0, 10.0, 101)
    dialog = SmoothingDialog(None, Dataset(id="ds-1", name="Data", data=pd.DataFrame({"t": t, "sq": t ** 2})))

    with (
        patch("pandaplot.gui.dialogs.analysis.smoothing_dialog.AnalysisEngine.smooth_data", side_effect=np.linalg.LinAlgError("Singular matrix")),
        caplog.at_level(logging.ERROR),
    ):
        dialog.preview_analysis()

    text = dialog.preview_text.toPlainText()
    assert text.startswith("Preview error: The calculation cannot be solved for this data")
    assert "Singular matrix" not in text
    assert "Smoothing preview failed" in caplog.text
