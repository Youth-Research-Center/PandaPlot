"""Tests for the hand-written chart help topics."""

import pytest

from pandaplot.services.help.content import charts
from pandaplot.services.help.content.chart_types import CHART_TYPE_TOPIC_IDS
from pandaplot.services.help.help_catalog import HelpCatalog, build_help_catalog
from pandaplot.services.help.help_types import (
    CHART_TOPIC_CHOOSE_TYPE,
    CHART_TOPIC_ERROR_BARS,
    CHART_TOPIC_IDS,
    CHART_TOPIC_LEGEND,
    CHART_TOPIC_SAVE_IMAGE,
    CHART_TOPIC_SERIES,
    CHART_TOPIC_VIEW,
    CHART_TOPIC_WIZARD_DATA,
    HelpCategory,
    HelpTopic,
)

_PROCEDURE_TOPICS = ("charts.create", "charts.wizard_data", "charts.series", "charts.error_bars", "charts.save_image")


@pytest.fixture(scope="module")
def catalog() -> HelpCatalog:
    """Catalog built from the hand-written chart module only."""
    return HelpCatalog(charts.topics())


def _all_text(topic: HelpTopic) -> str:
    return " ".join([topic.title, topic.summary, *topic.steps, topic.explanation, topic.example, *topic.keywords])


def test_topics_are_the_eleven_ids_in_order() -> None:
    assert [topic.id for topic in charts.topics()] == list(CHART_TOPIC_IDS)
    assert len(CHART_TOPIC_IDS) == 11


@pytest.mark.parametrize("topic_id", CHART_TOPIC_IDS)
def test_topic_is_in_charts_category_with_summary(catalog: HelpCatalog, topic_id: str) -> None:
    topic = catalog.get(topic_id)

    assert topic is not None
    assert topic.category is HelpCategory.CHARTS
    assert topic.summary.strip()
    assert topic.keywords


@pytest.mark.parametrize("topic_id", _PROCEDURE_TOPICS)
def test_procedure_topics_have_steps(catalog: HelpCatalog, topic_id: str) -> None:
    topic = catalog.get(topic_id)

    assert topic is not None
    assert topic.steps
    assert all(step.strip() for step in topic.steps)


def test_view_topic_warns_reset_cannot_be_undone(catalog: HelpCatalog) -> None:
    text = _all_text(catalog.get(CHART_TOPIC_VIEW)).lower()

    assert "cannot be undone" in text or "can't be undone" in text
    assert '"Reset" puts all chart-level settings back to their defaults' in _all_text(catalog.get(CHART_TOPIC_VIEW))


def test_save_image_topic_names_save_dpi_and_size_without_export_command(catalog: HelpCatalog) -> None:
    text = _all_text(catalog.get(CHART_TOPIC_SAVE_IMAGE))

    assert "Save" in text
    assert "DPI" in text
    assert "Size" in text
    assert "Export Chart" not in text
    assert "no separate export" in text


def test_no_topic_says_changes_wait_for_apply(catalog: HelpCatalog) -> None:
    for topic in catalog.topics():
        text = _all_text(topic).lower()
        assert "only take effect" not in text, topic.id
        assert "until you click apply" not in text, topic.id


def test_topics_do_not_cite_issue_numbers(catalog: HelpCatalog) -> None:
    for topic in catalog.topics():
        assert "#583" not in _all_text(topic), topic.id


@pytest.mark.parametrize("topic_id", [CHART_TOPIC_CHOOSE_TYPE, CHART_TOPIC_WIZARD_DATA])
def test_type_and_data_topics_link_to_every_chart_type(catalog: HelpCatalog, topic_id: str) -> None:
    related = set(catalog.get(topic_id).related)

    assert set(CHART_TYPE_TOPIC_IDS.values()) <= related


def test_wizard_data_links_to_error_bars(catalog: HelpCatalog) -> None:
    assert CHART_TOPIC_ERROR_BARS in catalog.get(CHART_TOPIC_WIZARD_DATA).related


def test_create_links_to_the_agreed_topics(catalog: HelpCatalog) -> None:
    related = set(catalog.get("charts.create").related)

    assert {"charts.math_text", "charts.choose_type", "charts.wizard_data", "panel.chart_properties"} <= related


def test_error_bar_topic_names_exactly_the_supporting_types(catalog: HelpCatalog) -> None:
    text = _all_text(catalog.get(CHART_TOPIC_ERROR_BARS))

    assert "Line, Scatter, Bar, Stacked Bar" in text
    assert "Vector, Color Map or Heatmap chart" in text
    assert '"Series Type:"' in text


def test_every_related_id_resolves() -> None:
    full_catalog = build_help_catalog()
    unresolved = [(topic.id, related) for topic in charts.topics() for related in topic.related if full_catalog.get(related) is None]

    assert unresolved == []


def test_topics_returns_fresh_equal_lists() -> None:
    first = charts.topics()
    second = charts.topics()

    assert first == second
    assert first is not second


def test_create_topic_does_not_promise_filling_an_empty_chart_later(catalog: HelpCatalog) -> None:
    text = _all_text(catalog.get("charts.create"))
    assert "fill in later" not in text
    assert "press F1 (on a Mac, Cmd+?)" in text


def test_series_topic_does_not_claim_data_tab_x_blank_or_chart_analysis_fits(catalog: HelpCatalog) -> None:
    text = _all_text(catalog.get("charts.series"))
    assert "Chart Analysis panel" not in text
    assert "to plot against the row index" not in text
    assert "Curve Fitting" in text


def test_wizard_data_topic_does_not_say_every_column_is_required(catalog: HelpCatalog) -> None:
    assert "until every other column is chosen" not in _all_text(catalog.get("charts.wizard_data"))


def test_pie_legend_entries_come_from_the_labels_column(catalog: HelpCatalog) -> None:
    for topic_id in (CHART_TOPIC_LEGEND, CHART_TOPIC_SERIES):
        text = _all_text(catalog.get(topic_id))

        assert "Pie chart" in text
        assert '"Labels Column (optional):"' in text
