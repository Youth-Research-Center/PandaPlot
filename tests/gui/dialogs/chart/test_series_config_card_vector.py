"""Tests for SeriesConfigCard with the vector chart type's role spec."""
import sys

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QLabel

from pandaplot.gui.dialogs.chart.series_config_card import SeriesConfigCard
from pandaplot.models.chart.chart_role_labels import ROLE_LABELS
from pandaplot.models.chart.chart_type_spec import get_chart_type_spec


@pytest.fixture(scope="module", autouse=True)
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


def test_vector_card_exposes_labelled_u_v_magnitude_combos_filled_from_the_dataset_columns():
    card = SeriesConfigCard(role_spec=get_chart_type_spec("vector"))
    card.set_datasets([("ds-1", "Dataset 1")])
    card.set_dataset_columns("ds-1", [("col-u", "U"), ("col-v", "V")])

    labels = card.findChildren(QLabel)
    for role, combo in (("u", card.u_column_combo), ("v", card.v_column_combo), ("magnitude", card.magnitude_column_combo)):
        assert isinstance(combo, QComboBox)
        assert [combo.itemData(index) for index in range(combo.count())] == ["", "col-u", "col-v"]
        assert any(label.buddy() is combo and label.text() == f"{ROLE_LABELS[role]}:" for label in labels)
    assert not hasattr(card, "z_column_combo")  # a 2-D vector field has no Z role


def test_vector_card_series_config_has_u_v_magnitude_keys():
    card = SeriesConfigCard(role_spec=get_chart_type_spec("vector"))
    card.set_datasets([("ds-1", "Dataset 1")])
    card.set_dataset_columns("ds-1", [("col-u", "U"), ("col-v", "V"), ("col-m", "M")])

    card.u_column_combo.setCurrentIndex(card.u_column_combo.findData("col-u"))
    card.v_column_combo.setCurrentIndex(card.v_column_combo.findData("col-v"))
    card.magnitude_column_combo.setCurrentIndex(card.magnitude_column_combo.findData("col-m"))

    config = card.get_series_config()
    assert config["u_column_id"] == "col-u"
    assert config["v_column_id"] == "col-v"
    assert config["magnitude_column_id"] == "col-m"


def test_vector_card_is_complete_requires_u_and_v_not_magnitude():
    card = SeriesConfigCard(role_spec=get_chart_type_spec("vector"))
    card.set_datasets([("ds-1", "Dataset 1")])
    card.dataset_combo.setCurrentIndex(0)
    card.set_dataset_columns("ds-1", [("col-x", "X"), ("col-y", "Y"), ("col-u", "U"), ("col-v", "V")])

    assert card.is_complete() is False

    card.x_column_combo.setCurrentIndex(card.x_column_combo.findData("col-x"))
    card.y_column_combo.setCurrentIndex(card.y_column_combo.findData("col-y"))
    card.u_column_combo.setCurrentIndex(card.u_column_combo.findData("col-u"))
    card.v_column_combo.setCurrentIndex(card.v_column_combo.findData("col-v"))

    assert card.is_complete() is True
