"""Tests for ChartDataPage."""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.dialogs.chart.chart_data_page import ChartDataPage
from pandaplot.services.theme.theme_manager import ThemeManager


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


_FAKE_TOKENS = {
    "text_primary": "#1C1E26", "text_secondary": "#3F4350",
    "text_muted": "#6B7280", "text_hint": "#9AA0AB",
    "border_panel": "#E5E6EA", "border_control": "#DCDEE4",
    "border_subtle": "#ECEEF2",
    "surface_white": "#FFFFFF", "surface_chrome": "#FBFBFC",
    "surface_inset": "#F4F5F8",
    "accent": "#4A56C6", "accent_active_text": "#3A45A8", "accent_disabled": "#AAB1E3",
    "accent_selected_bg": "#EEF0FB",
    "status_modified_dot": "#E09A1F", "status_modified_text": "#B06A00",
    "status_success": "#3FA46A",
    "y2_accent": "#8A4BB8", "y2_accent_bg": "#F5EEFB",
    "series_palette": ["#A01818", "#4A56C6", "#2B7A8C", "#3FA46A", "#E09A1F"],
    "radius_swatch": 4, "radius_control": 5, "radius_card": 6, "radius_chip": 12,
}


def _fake_app_context():
    app_context = Mock()
    app_context.event_bus = Mock()

    theme_manager = Mock()
    theme_manager.get_design_tokens.return_value = dict(_FAKE_TOKENS)

    def _get_manager(manager_type, *args, **kwargs):
        if manager_type is ThemeManager:
            return theme_manager
        return Mock()

    app_context.get_manager.side_effect = _get_manager
    return app_context


def _columns_for(dataset_id: str) -> list[tuple[str, str]]:
    return [("col-date", "Date"), ("col-rev", "Revenue")]


def _make_page() -> ChartDataPage:
    page = ChartDataPage(app_context=_fake_app_context())
    page.set_chart_type("line")
    page.set_datasets([("ds-1", "Sales")])
    page.set_dataset_columns_provider(_columns_for)
    return page


def test_starts_with_exactly_one_series_card():
    page = _make_page()

    assert len(page.cards) == 1


def test_add_series_button_appends_a_card():
    page = _make_page()

    page.add_series_button.click()

    assert len(page.cards) == 2


def test_removing_a_card_via_its_signal_shrinks_the_list():
    page = _make_page()
    page.add_series_button.click()
    first_card = page.cards[0]

    first_card.removeRequested.emit()

    assert len(page.cards) == 1
    assert first_card not in page.cards


def test_incomplete_until_the_only_cards_required_role_is_filled():
    page = _make_page()

    assert page.isComplete() is False

    page.cards[0].y_column_combo.setCurrentIndex(page.cards[0].y_column_combo.findData("col-rev"))

    assert page.isComplete() is True


def test_series_configs_returns_one_dict_per_card():
    page = _make_page()
    page.cards[0].y_column_combo.setCurrentIndex(page.cards[0].y_column_combo.findData("col-rev"))

    configs = page.series_configs()

    assert len(configs) == 1
    assert configs[0]["dataset_id"] == "ds-1"
    assert configs[0]["y_column_id"] == "col-rev"


def test_empty_button_emits_empty_requested():
    page = _make_page()
    received = []
    page.emptyRequested.connect(lambda: received.append(True))

    page.empty_button.click()

    assert received == [True]


def test_changing_chart_type_resets_to_a_single_card_of_the_new_type():
    page = _make_page()
    page.add_series_button.click()
    assert len(page.cards) == 2

    page.set_chart_type("hist")

    assert len(page.cards) == 1
    assert page.cards[0].error_bars_check is None


def test_new_cards_start_expanded():
    page = _make_page()

    assert page.cards[0].is_collapsed() is False


def test_second_added_card_also_starts_expanded_first_card_untouched():
    page = _make_page()
    page.cards[0].y_column_combo.setCurrentIndex(page.cards[0].y_column_combo.findData("col-rev"))
    page.cards[0].set_collapsed(collapsed=True)

    page.add_series_button.click()

    assert page.cards[1].is_collapsed() is False
    assert page.cards[0].is_collapsed() is True  # untouched by adding a sibling


def test_cards_container_is_wrapped_in_a_scroll_area():
    page = _make_page()

    assert page.cards_scroll_area is not None
    assert page.cards_scroll_area.widgetResizable() is True


def test_page_exposes_a_step_rail_and_footer():
    page = _make_page()

    assert page.step_rail is not None
    assert page.footer is not None


def test_two_collapsed_cards_show_different_swatch_colors():
    """Regression: `_refresh_summary` always used series_palette[0] regardless
    of which series the card represents, so every collapsed card showed the
    same swatch color."""
    page = _make_page()
    page.add_series_button.click()
    for card in page.cards:
        card.set_tokens({"series_palette": ["#111111", "#222222", "#333333"]})
        card.set_collapsed(collapsed=True)

    colors = [card._swatch.styleSheet() for card in page.cards]

    assert colors[0] != colors[1]


def test_removing_a_card_reindexes_remaining_cards_swatch_colors():
    page = _make_page()
    page.add_series_button.click()
    page.add_series_button.click()
    for card in page.cards:
        card.set_tokens({"series_palette": ["#111111", "#222222", "#333333"]})

    first_card = page.cards[0]
    first_card.removeRequested.emit()

    remaining = page.cards
    for card in remaining:
        card.set_collapsed(collapsed=True)
    # After removal, remaining cards should be re-indexed 0, 1 (not 1, 2).
    assert remaining[0]._index == 0
    assert remaining[1]._index == 1


def test_add_series_button_uses_shared_secondary_button_style():
    """Regression: `add_series_button` used to be a raw QPushButton with
    hand-rolled, token-driven inline styling (dark-button-face + invisible
    text under a dark theme before that fix). It is now a `PButton` whose
    "secondary" role is applied via the shared global QSS, so no per-widget
    stylesheet or manual token wiring is needed."""
    page = _make_page()

    page._apply_theme()

    assert isinstance(page.add_series_button, PButton)
    assert page.add_series_button.property("secondary") is True
    assert page.add_series_button.styleSheet() == ""


def test_a_freshly_added_card_is_tokened_immediately():
    """Regression: cards added mid-session (via + Add series) picked up no
    styling until the next theme-change event."""
    page = _make_page()

    page.add_series_button.click()
    new_card = page.cards[-1]

    assert new_card._tokens != {}


def test_next_button_enabled_state_tracks_iscomplete():
    """Regression: after Task 3 removed QWizard's native buttons, nothing
    wired isComplete()/completeChanged to the footer's Next button, so users
    could advance past an incomplete page."""
    page = _make_page()

    # Default card has no Y column picked yet -> incomplete -> disabled.
    assert page.isComplete() is False
    assert page.footer.next_button.isEnabled() is False

    page.cards[0].y_column_combo.setCurrentIndex(page.cards[0].y_column_combo.findData("col-rev"))

    assert page.isComplete() is True
    assert page.footer.next_button.isEnabled() is True
