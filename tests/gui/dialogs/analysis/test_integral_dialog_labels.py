import sys

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.analysis.integral_dialog import IntegralDialog


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def test_method_label_does_not_hardcode_a_static_color():
    """Was setStyleSheet("color: #666666; ...") once at construction and
    never refreshed -- illegible against a dark background."""
    import pandas as pd

    from pandaplot.models.project.items.dataset import Dataset

    dataset = Dataset(name="d", data=pd.DataFrame({"x": [1, 2, 3], "y": [1, 2, 3]}))
    dialog = IntegralDialog(None, dataset)
    assert "#666666" not in dialog.method_label.styleSheet()
    assert "italic" in dialog.method_label.styleSheet()
