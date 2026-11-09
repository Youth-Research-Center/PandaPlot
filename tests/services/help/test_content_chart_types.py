"""Tests for the help topics derived from the chart type registry.

These build a catalog from ``chart_types`` only, so they do not depend on the hand-written chart topics.
"""

import pytest

from pandaplot.models.chart.chart_role_labels import ROLE_LABELS
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.project.items.chart import SWAPPABLE_CHART_TYPES
from pandaplot.services.help.content import chart_types
from pandaplot.services.help.content.panel_defaults import HIST_BINS
from pandaplot.services.help.help_catalog import HelpCatalog
from pandaplot.services.help.help_types import (
    CHART_TOPIC_CHOOSE_TYPE,
    CHART_TOPIC_CREATE,
    CHART_TOPIC_ERROR_BARS,
    FIT_TOPIC_OVERVIEW,
    HelpCategory,
)


@pytest.fixture(scope="module")
def catalog() -> HelpCatalog:
    return HelpCatalog(chart_types.topics())


@pytest.fixture(params=list(ChartType), ids=lambda chart_type: chart_type.value)
def chart_type(request) -> ChartType:
    return request.param


def _bins_sentence(topic) -> bool:
    return f"from {int(HIST_BINS.minimum)} to {int(HIST_BINS.maximum)} and starts at {int(HIST_BINS.default)}" in topic.explanation


class TestMappings:
    def test_mapping_covers_every_chart_type(self, catalog):
        assert set(chart_types.CHART_TYPE_TOPIC_IDS) == set(ChartType)
        for chart_type, topic_id in chart_types.CHART_TYPE_TOPIC_IDS.items():
            assert topic_id == f"charts.{chart_type.value}"
            assert catalog.get(topic_id) is not None

    def test_text_covers_every_chart_type(self):
        assert set(chart_types._CHART_TYPE_TEXT) == set(ChartType)

    def test_topics_are_in_spec_order(self):
        assert [topic.id for topic in chart_types.topics()] == [chart_types.CHART_TYPE_TOPIC_IDS[t] for t in CHART_TYPE_SPECS]


class TestTopicContent:
    def test_category_and_names(self, catalog, chart_type):
        spec = CHART_TYPE_SPECS[chart_type]
        topic = catalog.get(chart_types.CHART_TYPE_TOPIC_IDS[chart_type])
        assert topic.category is HelpCategory.CHARTS
        assert spec.display_name in topic.title
        assert spec.category.value in topic.explanation
        assert topic.summary
        assert topic.example

    def test_required_role_labels_appear(self, catalog, chart_type):
        spec = CHART_TYPE_SPECS[chart_type]
        topic = catalog.get(chart_types.CHART_TYPE_TOPIC_IDS[chart_type])
        for role in spec.required_roles:
            assert ROLE_LABELS[role] in topic.explanation
        assert "(optional) (optional)" not in topic.explanation

    def test_optional_roles_are_marked(self, catalog, chart_type):
        spec = CHART_TYPE_SPECS[chart_type]
        topic = catalog.get(chart_types.CHART_TYPE_TOPIC_IDS[chart_type])
        for role in spec.roles:
            if role not in spec.required_roles:
                label = ROLE_LABELS[role]
                assert (label if "(optional)" in label else f"{label} (optional)") in topic.explanation

    def test_fit_and_error_bar_sentences(self, catalog, chart_type):
        spec = CHART_TYPE_SPECS[chart_type]
        topic = catalog.get(chart_types.CHART_TYPE_TOPIC_IDS[chart_type])
        assert ("Curve fits are available" in topic.explanation) is spec.allows_fit
        assert ("Error bars are supported" in topic.explanation) is spec.supports_error_bars
        assert ("Error bars are not supported" in topic.explanation) is not spec.supports_error_bars

    def test_swap_sentence_matches_swappable_types(self, catalog, chart_type):
        topic = catalog.get(chart_types.CHART_TYPE_TOPIC_IDS[chart_type])
        assert ("Swap X/Y" in topic.explanation) is (chart_type in SWAPPABLE_CHART_TYPES)

    def test_bins_text_only_for_histogram_series_types(self, catalog, chart_type):
        spec = CHART_TYPE_SPECS[chart_type]
        topic = catalog.get(chart_types.CHART_TYPE_TOPIC_IDS[chart_type])
        expects_bins = SeriesType.HIST in spec.allowed_series_types
        assert ('"Bins:"' in topic.explanation) is expects_bins
        assert _bins_sentence(topic) is expects_bins

    def test_axes_and_3d_sentences(self, catalog, chart_type):
        spec = CHART_TYPE_SPECS[chart_type]
        topic = catalog.get(chart_types.CHART_TYPE_TOPIC_IDS[chart_type])
        assert ("has no axes" in topic.explanation) is (not spec.has_axes)
        assert ("Elevation and Azimuth" in topic.explanation) is spec.is_3d

    def test_related_and_keywords(self, catalog, chart_type):
        spec = CHART_TYPE_SPECS[chart_type]
        topic = catalog.get(chart_types.CHART_TYPE_TOPIC_IDS[chart_type])
        assert CHART_TOPIC_CHOOSE_TYPE in topic.related
        assert CHART_TOPIC_CREATE in topic.related
        assert (FIT_TOPIC_OVERVIEW in topic.related) is spec.allows_fit
        assert (CHART_TOPIC_ERROR_BARS in topic.related) is spec.supports_error_bars
        assert spec.display_name.lower() in topic.keywords
        assert chart_type.value in topic.keywords


class TestSpecificTopics:
    def test_titles(self, catalog):
        assert catalog.get("charts.box").title == "Box Plot"
        assert catalog.get("charts.line").title == "Line chart"

    def test_box_plot_mentions_one_series_per_group(self, catalog):
        assert "one box" in catalog.get("charts.box").explanation
        assert "one series for each group" in catalog.get("charts.box").explanation

    def test_row_number_note_for_types_with_optional_x(self, catalog):
        for chart_type, spec in CHART_TYPE_SPECS.items():
            if spec.required_roles == ("y",) and "x" in spec.roles:
                assert "row number" in catalog.get(chart_types.CHART_TYPE_TOPIC_IDS[chart_type]).explanation


class TestFreshness:
    def test_topics_returns_equal_fresh_lists(self):
        first = chart_types.topics()
        second = chart_types.topics()
        assert first == second
        assert first is not second
