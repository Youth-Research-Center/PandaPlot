"""Tests for SeriesConfigCard."""
from typing import Any

import pytest
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.chart.series_config_card import (
    _FALLBACK_DISABLED_ICON_COLOR,
    _FALLBACK_ICON_COLOR,
    SeriesConfigCard,
)
from pandaplot.gui.resources.icon_library import build_icon
from pandaplot.models.chart.chart_type_spec import get_chart_type_spec
from pandaplot.models.state.config import Theme
from tests.gui.theme_testing import design_tokens


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


def test_box_card_asks_only_for_a_required_values_column_mapped_to_y():
    """Box reuses Histogram's ("values",) role shape, so the card needs no
    Box-specific wiring: one Values combo, no X, no error bars (#399)."""
    card = SeriesConfigCard(role_spec=get_chart_type_spec("box"))
    card.set_datasets([("ds-1", "Sales")])
    card.set_dataset_columns("ds-1", [("col-date", "Date"), ("col-rev", "Revenue")])
    assert card.error_bars_check is None
    assert not card.is_complete()

    card.values_column_combo.setCurrentIndex(card.values_column_combo.findData("col-rev"))

    assert card.is_complete()
    config = card.get_series_config()
    assert config["y_column_id"] == "col-rev"
    assert config.get("x_column_id", "") == ""


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
    # Distinct sentinel colours that appear nowhere else in the stylesheet, so the assertion can tell which entry was used.
    card.set_tokens(design_tokens(series_palette=["#111111", "#222222", "#333333"]))
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


def test_icon_only_expand_and_collapse_buttons_have_accessible_names():
    card = _line_card()

    assert card._expand_button.accessibleName() == "Expand series"
    assert card._collapse_button.accessibleName() == "Collapse series"
    assert card._expand_button.toolTip()
    assert card._collapse_button.toolTip()


def test_default_card_keeps_wizard_controls_and_collapsing():
    card = _line_card()

    assert card.remove_button.isVisible()
    assert card._collapse_button.isVisible()
    card.set_collapsed(collapsed=True)
    assert card.is_collapsed()
    assert card._summary_row.isVisible()
    assert not card._form_widget.isVisible()


def test_standalone_card_hides_remove_collapse_and_summary():
    card = SeriesConfigCard(role_spec=get_chart_type_spec("line"), standalone=True)
    card.show()

    assert not card.remove_button.isVisible()
    assert not card._collapse_button.isVisible()
    assert not card._summary_row.isVisible()
    assert card._form_widget.isVisible()


def test_standalone_card_ignores_set_collapsed():
    card = SeriesConfigCard(role_spec=get_chart_type_spec("line"), standalone=True)
    card.show()

    card.set_collapsed(collapsed=True)

    assert not card.is_collapsed()
    assert card._form_widget.isVisible()
    assert not card._summary_row.isVisible()


def test_every_role_label_has_its_combo_as_buddy():
    from PySide6.QtWidgets import QLabel

    card = SeriesConfigCard(role_spec=get_chart_type_spec("line"))
    buddies = {label.text(): label.buddy() for label in card.findChildren(QLabel) if label.buddy() is not None}

    assert buddies["Dataset:"] is card.dataset_combo
    assert buddies["X column:"] is card.x_column_combo
    assert buddies["Y column:"] is card.y_column_combo
    assert buddies["Y error (+) column:"] is card.y_error_column_combo


def test_missing_required_roles_lists_roles_without_a_column():
    card = SeriesConfigCard(role_spec=get_chart_type_spec("heatmap"))
    card.set_datasets([("ds-1", "Sales")])
    card.set_dataset_columns("ds-1", [("col-x", "X"), ("col-y", "Y"), ("col-z", "Z")])

    assert card.missing_required_roles() == ["x", "y", "z"]
    assert not card.is_complete()

    card.x_column_combo.setCurrentIndex(card.x_column_combo.findData("col-x"))
    card.z_column_combo.setCurrentIndex(card.z_column_combo.findData("col-z"))

    assert card.missing_required_roles() == ["y"]

    card.y_column_combo.setCurrentIndex(card.y_column_combo.findData("col-y"))

    assert card.missing_required_roles() == []
    assert card.is_complete()


def _icon_image(icon: QIcon, mode: QIcon.Mode = QIcon.Mode.Normal):
    return icon.pixmap(16, 16, mode).toImage()


def _expected_chevron(name: str, tokens: dict[str, Any]) -> QIcon:
    return build_icon(name, tokens["text_muted"], size=16, disabled_color=tokens["text_disabled"])


def test_expand_and_collapse_buttons_show_chevron_icons_without_glyph_text_once_tokens_are_set():
    card = _line_card()

    tokens = design_tokens()
    card.set_tokens(dict(tokens))

    for button, icon_name in ((card._expand_button, "caret-right"), (card._collapse_button, "caret-down")):
        assert button.text() == ""
        assert _icon_image(button.icon()) == _icon_image(_expected_chevron(icon_name, tokens))
        assert _icon_image(button.icon(), QIcon.Mode.Disabled) == _icon_image(_expected_chevron(icon_name, tokens), QIcon.Mode.Disabled)


def test_chevron_icons_follow_a_token_change():
    card = _line_card()
    card.set_tokens(design_tokens(Theme.LIGHT))
    dark = design_tokens(Theme.DARK)

    card.set_tokens(dark)

    assert _icon_image(card._expand_button.icon()) == _icon_image(_expected_chevron("caret-right", dark))
    assert _icon_image(card._collapse_button.icon()) == _icon_image(_expected_chevron("caret-down", dark))


def test_card_without_tokens_has_buttons_with_no_glyph_text_and_works():
    card = _line_card()

    fallback = {"text_muted": _FALLBACK_ICON_COLOR, "text_disabled": _FALLBACK_DISABLED_ICON_COLOR}
    for button, icon_name in ((card._expand_button, "caret-right"), (card._collapse_button, "caret-down")):
        assert button.text() == ""
        assert not button.icon().isNull()
        assert _icon_image(button.icon()) == _icon_image(_expected_chevron(icon_name, fallback))
        assert _icon_image(button.icon(), QIcon.Mode.Disabled) == _icon_image(_expected_chevron(icon_name, fallback), QIcon.Mode.Disabled)
    card._collapse_button.click()
    assert card.is_collapsed()
    card._expand_button.click()
    assert not card.is_collapsed()
