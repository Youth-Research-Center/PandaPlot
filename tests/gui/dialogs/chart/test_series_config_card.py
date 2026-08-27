"""Tests for SeriesConfigCard."""
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.chart.series_config_card import SeriesConfigCard
from pandaplot.models.chart.chart_type_spec import get_chart_type_spec


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _line_card() -> SeriesConfigCard:
    card = SeriesConfigCard(role_spec=get_chart_type_spec("line"))
    card.set_datasets([("ds-1", "Sales")])
    card.set_dataset_columns("ds-1", [("col-date", "Date"), ("col-rev", "Revenue")])
    card.show()
    return card


def test_incomplete_until_required_role_is_filled():
    card = _line_card()
    assert card.is_complete() is False


def test_complete_once_y_role_is_selected():
    card = _line_card()
    card.y_column_combo.setCurrentIndex(card.y_column_combo.findData("col-rev"))

    assert card.is_complete() is True


def test_x_role_is_optional_for_line():
    card = _line_card()
    card.y_column_combo.setCurrentIndex(card.y_column_combo.findData("col-rev"))

    config = card.get_series_config()
    assert config["x_column_id"] == ""
    assert config["y_column_id"] == "col-rev"
    assert config["dataset_id"] == "ds-1"


def test_histogram_card_has_no_error_bar_toggle():
    card = SeriesConfigCard(role_spec=get_chart_type_spec("hist"))
    assert card.error_bars_check is None


def test_error_bars_hidden_until_toggled_on():
    card = _line_card()
    assert card.error_bars_check.isChecked() is False

    config = card.get_series_config()
    assert config["x_error_column_id"] == ""
    assert config["y_error_column_id"] == ""


def test_error_bars_columns_used_once_toggled_on():
    card = _line_card()
    card.error_bars_check.setChecked(True)
    card.y_error_column_combo.setCurrentIndex(card.y_error_column_combo.findData("col-rev"))

    config = card.get_series_config()
    assert config["y_error_column_id"] == "col-rev"
    assert config["error_symmetric"] is True


def test_apply_picked_columns_sets_the_named_role():
    card = _line_card()

    card.apply_picked_columns("y", ["col-rev"])

    assert card.y_column_combo.currentData() == "col-rev"


def test_apply_picked_columns_uses_only_the_first_id():
    card = _line_card()

    card.apply_picked_columns("y", ["col-rev", "col-date"])

    assert card.y_column_combo.currentData() == "col-rev"


def test_remove_button_emits_remove_requested():
    card = _line_card()
    received = []
    card.removeRequested.connect(lambda: received.append(True))

    card.remove_button.click()

    assert received == [True]


def test_histogram_values_role_maps_to_y_column_id():
    card = SeriesConfigCard(role_spec=get_chart_type_spec("hist"))
    card.set_datasets([("ds-1", "Sales")])
    card.set_dataset_columns("ds-1", [("col-date", "Date"), ("col-rev", "Revenue")])
    card.values_column_combo.setCurrentIndex(card.values_column_combo.findData("col-rev"))

    config = card.get_series_config()

    assert config["y_column_id"] == "col-rev"
    assert "values_column_id" not in config


def test_switching_dataset_resets_column_selections():
    card = _line_card()
    card.y_column_combo.setCurrentIndex(card.y_column_combo.findData("col-rev"))
    assert card.y_column_combo.currentData() == "col-rev"

    card.set_datasets([("ds-1", "Sales"), ("ds-2", "Marketing")])
    card.dataset_combo.setCurrentIndex(card.dataset_combo.findData("ds-2"))
    card.set_dataset_columns("ds-2", [("col-cost", "Cost"), ("col-clicks", "Clicks")])

    assert card.dataset_combo.currentData() == "ds-2"
    assert card.y_column_combo.currentData() == ""
    assert card.x_column_combo.currentData() == ""
    assert [card.y_column_combo.itemData(i) for i in range(card.y_column_combo.count())] == [
        "",
        "col-cost",
        "col-clicks",
    ]


def test_display_names_empty_when_nothing_selected():
    card = _line_card()

    assert card.get_display_names() == {}


def test_display_names_includes_only_selected_roles():
    card = _line_card()
    card.y_column_combo.setCurrentIndex(card.y_column_combo.findData("col-rev"))

    assert card.get_display_names() == {"y": "Revenue"}


def test_display_names_uses_display_text_not_column_id():
    card = _line_card()
    card.x_column_combo.setCurrentIndex(card.x_column_combo.findData("col-date"))
    card.y_column_combo.setCurrentIndex(card.y_column_combo.findData("col-rev"))

    names = card.get_display_names()
    assert names == {"x": "Date", "y": "Revenue"}
    assert "col-date" not in names.values()
    assert "col-rev" not in names.values()


def test_display_names_for_histogram_uses_the_values_role():
    card = SeriesConfigCard(role_spec=get_chart_type_spec("hist"))
    card.set_datasets([("ds-1", "Sales")])
    card.set_dataset_columns("ds-1", [("col-rev", "Revenue")])
    card.values_column_combo.setCurrentIndex(card.values_column_combo.findData("col-rev"))

    assert card.get_display_names() == {"values": "Revenue"}


def test_display_names_never_includes_error_roles():
    card = _line_card()
    card.error_bars_check.setChecked(True)
    card.y_error_column_combo.setCurrentIndex(card.y_error_column_combo.findData("col-rev"))

    assert "y_error" not in card.get_display_names()


def test_starts_expanded():
    card = _line_card()

    assert card.is_collapsed() is False
    assert card.dataset_combo.isVisible() is True


def test_collapsing_hides_the_form_and_shows_a_summary():
    card = _line_card()
    card.y_column_combo.setCurrentIndex(card.y_column_combo.findData("col-rev"))

    card.set_collapsed(collapsed=True)

    assert card.is_collapsed() is True
    assert card.dataset_combo.isVisible() is False
    assert "Revenue" in card.summary_label.text()


def test_expanding_again_restores_the_form():
    card = _line_card()
    card.set_collapsed(collapsed=True)

    card.set_collapsed(collapsed=False)

    assert card.is_collapsed() is False
    assert card.dataset_combo.isVisible() is True


def test_collapsed_state_does_not_affect_series_config():
    card = _line_card()
    card.y_column_combo.setCurrentIndex(card.y_column_combo.findData("col-rev"))
    card.set_collapsed(collapsed=True)

    assert card.get_series_config()["y_column_id"] == "col-rev"


def test_remove_button_is_not_fixed_width():
    card = _line_card()

    assert card.remove_button.minimumWidth() == 0


def test_expanded_card_has_a_collapse_button_that_collapses_it():
    """Regression: the collapsible-card feature was unreachable -- only the
    collapsed summary row had an expand button; the expanded form had no
    way to collapse."""
    card = _line_card()
    assert card.is_collapsed() is False

    card._collapse_button.click()

    assert card.is_collapsed() is True


def test_remove_button_is_a_destructive_pbutton():
    """Series removal is an irreversible data-removal action, so it gets the
    destructive role instead of the neutral/secondary look used elsewhere on
    this card. Styling itself is now handled by PButton's dynamic properties
    plus the global QSS, not per-widget stylesheets built from tokens."""
    card = _line_card()

    assert card.remove_button.property("destructive") is True
    assert card.remove_button.property("secondary") is False


def test_expand_and_collapse_chevrons_are_secondary_icon_pbuttons():
    card = _line_card()

    assert card._expand_button.property("secondary") is True
    assert card._expand_button.property("iconButton") is True
    assert card._collapse_button.property("secondary") is True
    assert card._collapse_button.property("iconButton") is True


def test_swatch_color_reflects_the_cards_index():
    card = _line_card()
    card.set_tokens({"series_palette": ["#111111", "#222222", "#333333"]})
    card.set_index(1)

    card.set_collapsed(collapsed=True)

    assert "#222222" in card._swatch.styleSheet()


def test_enabling_asymmetric_error_bars_exposes_minus_columns_and_defaults_them_to_plus():
    """Mirrors data_tab.py's already-shipped "default minus to plus"
    behavior (see _on_error_symmetry_toggled), applied to the wizard's
    per-series card so the wizard doesn't reintroduce the same
    None-default gap in a second place."""
    card = _line_card()
    card.error_bars_check.setChecked(True)
    plus_index = card.x_error_column_combo.findData("col-rev")
    card.x_error_column_combo.setCurrentIndex(plus_index)

    card.error_asymmetric_check.setChecked(True)

    assert card.x_error_minus_column_combo.isVisible() is True
    assert card.x_error_minus_column_combo.currentData() == "col-rev"


def test_series_config_includes_minus_columns_and_symmetric_flag():
    card = _line_card()
    card.error_bars_check.setChecked(True)
    card.error_asymmetric_check.setChecked(True)

    config = card.get_series_config()

    assert "x_error_minus_column_id" in config
    assert "y_error_minus_column_id" in config
    assert config["error_symmetric"] is False
