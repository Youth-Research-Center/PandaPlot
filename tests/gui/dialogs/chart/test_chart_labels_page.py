"""Tests for ChartLabelsPage."""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from pandaplot.gui.dialogs.chart.chart_labels_page import ChartLabelsPage
from pandaplot.services.theme.theme_manager import ThemeManager
from tests.gui.theme_testing import design_tokens


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _fake_app_context():
    app_context = Mock()
    app_context.event_bus = Mock()

    theme_manager = Mock()
    theme_manager.get_design_tokens.return_value = design_tokens()

    def _get_manager(manager_type, *args, **kwargs):
        if manager_type is ThemeManager:
            return theme_manager
        return Mock()

    app_context.get_manager.side_effect = _get_manager
    return app_context


def test_fields_start_empty():
    page = ChartLabelsPage(app_context=_fake_app_context())

    assert page.get_title() == ""
    assert page.get_x_label() == ""
    assert page.get_y_label() == ""


def test_set_defaults_populates_all_three_fields():
    page = ChartLabelsPage(app_context=_fake_app_context())

    page.set_defaults("Chart from Sales", "Date", "Revenue")

    assert page.get_title() == "Chart from Sales"
    assert page.get_x_label() == "Date"
    assert page.get_y_label() == "Revenue"


def test_fields_stay_editable_after_defaults_are_set():
    page = ChartLabelsPage(app_context=_fake_app_context())
    page.set_defaults("Chart from Sales", "Date", "Revenue")

    page.title_edit.setText("My custom title")
    page.y_label_edit.clear()

    assert page.get_title() == "My custom title"
    assert page.get_y_label() == ""
    assert page.get_x_label() == "Date"


def test_set_defaults_overwrites_previous_defaults():
    """Re-seeding (e.g. after a chart-type change) replaces stale defaults."""
    page = ChartLabelsPage(app_context=_fake_app_context())
    page.set_defaults("Old title", "Old X", "Old Y")

    page.set_defaults("New title", "New X", "New Y")

    assert page.get_title() == "New title"
    assert page.get_x_label() == "New X"
    assert page.get_y_label() == "New Y"


def test_set_defaults_overwrites_an_untouched_field_even_on_a_second_call():
    """Seeding itself must not mark a field as touched (regression guard for
    the blockSignals wiring in set_defaults)."""
    page = ChartLabelsPage(app_context=_fake_app_context())
    page.set_defaults("Old title", "Old X", "Old Y")

    page.set_defaults("Newer title", "Newer X", "Newer Y")

    assert page.get_title() == "Newer title"
    assert page.get_x_label() == "Newer X"
    assert page.get_y_label() == "Newer Y"


def test_a_field_touched_by_the_user_is_never_overwritten_again():
    page = ChartLabelsPage(app_context=_fake_app_context())
    page.set_defaults("Old title", "Old X", "Old Y")

    page.x_label_edit.setText("user typed this")  # simulates a real user edit
    page.set_defaults("New title", "New X", "New Y")

    assert page.get_x_label() == "user typed this"
    assert page.get_title() == "New title"
    assert page.get_y_label() == "New Y"


def test_subtitle_starts_empty():
    page = ChartLabelsPage(app_context=_fake_app_context())

    assert page.get_subtitle() == ""


def test_subtitle_is_directly_editable():
    page = ChartLabelsPage(app_context=_fake_app_context())

    page.subtitle_edit.setText("A closer look")

    assert page.get_subtitle() == "A closer look"


def test_legend_and_grid_default_on():
    page = ChartLabelsPage(app_context=_fake_app_context())

    assert page.get_show_legend() is True
    assert page.get_show_grid() is True


def test_legend_and_grid_toggles_are_independent():
    page = ChartLabelsPage(app_context=_fake_app_context())

    page.show_legend_toggle.setChecked(checked=False)

    assert page.get_show_legend() is False
    assert page.get_show_grid() is True


def test_page_shows_the_wizard_step_rail_and_the_step_3_footer():
    page = ChartLabelsPage(app_context=_fake_app_context())

    assert [button.text() for button in page.step_rail.findChildren(QPushButton)] == ["Type", "Data", "Labels"]
    footer = page.footer
    assert footer.step_label.text() == "Step 3 of 3"
    assert footer.empty_link is None  # step 3: no "Create empty plot" link
    assert footer.back_button.isVisibleTo(page) is True
    assert footer.next_button.isVisibleTo(page) is False  # the last step finishes instead
    assert footer.finish_button.isVisibleTo(page) is True


def test_refresh_preview_with_no_project_or_series_falls_back_to_the_sample_chart():
    page = ChartLabelsPage(app_context=_fake_app_context())
    page.set_defaults("My title", "Date", "Revenue")
    assert page.preview_canvas is None

    page.refresh_preview(project=None, chart_type="line", series_configs=[])

    axes = page.preview_canvas.axes
    # One sample line, drawn from the same sample data the Type step previews.
    assert len(axes.lines) == 1
    assert list(axes.lines[0].get_xdata()) == [1, 2, 3, 4, 5]
    assert list(axes.lines[0].get_ydata()) == [2, 3, 1, 4, 3]
    assert axes.get_title() == "My title"
    assert axes.get_xlabel() == "Date"
    assert axes.get_ylabel() == "Revenue"
    assert axes.get_legend() is None  # the sample line carries no label
    assert axes.xaxis.get_gridlines()[0].get_visible() is True

    previous_canvas = page.preview_canvas
    page.show_grid_toggle.setChecked(checked=False)  # re-renders from the cached arguments

    assert page.preview_canvas is not previous_canvas
    assert len(page.preview_canvas.axes.lines) == 1
    assert page.preview_canvas.axes.get_title() == "My title"
    assert page.preview_canvas.axes.xaxis.get_gridlines()[0].get_visible() is False
