"""Tests for the help catalog and search."""

import pytest

from pandaplot.services.help.help_catalog import CONTENT_MODULES, HelpCatalog, build_help_catalog
from pandaplot.services.help.help_types import HelpCategory, HelpTopic


def _topic(topic_id: str, title: str, category: HelpCategory = HelpCategory.STATISTICS, **kwargs: object) -> HelpTopic:
    kwargs.setdefault("summary", "Plain summary.")
    return HelpTopic(id=topic_id, title=title, category=category, **kwargs)  # type: ignore[arg-type]


@pytest.fixture
def catalog() -> HelpCatalog:
    return HelpCatalog([
        _topic("stats.t", "T-test", keywords=("student",), summary="Compares means."),
        _topic("fit.linear", "Linear fit", HelpCategory.FITTING, summary="Straight line through a t-test of sorts."),
        _topic("prep.norm", "Normalize", HelpCategory.PREPROCESSING, explanation="Rescales values.", steps=("Pick a column",)),
        _topic("fit.gauss", "Gaussian", HelpCategory.FITTING, parameters=(("Amplitude", "Height of the peak"),), keywords=("bell",)),
    ])


class TestLookup:
    def test_get_known_and_unknown(self, catalog):
        assert catalog.get("stats.t").title == "T-test"
        assert catalog.get("nope") is None

    def test_topics_keep_order(self, catalog):
        assert [t.id for t in catalog.topics()] == ["stats.t", "fit.linear", "prep.norm", "fit.gauss"]

    def test_duplicate_id_raises_naming_id(self):
        with pytest.raises(ValueError, match="stats.t"):
            HelpCatalog([_topic("stats.t", "A"), _topic("stats.t", "B")])


class TestByCategory:
    def test_enum_order_and_empty_categories_omitted(self, catalog):
        grouped = catalog.by_category()
        assert list(grouped) == [HelpCategory.STATISTICS, HelpCategory.PREPROCESSING, HelpCategory.FITTING]
        assert [t.id for t in grouped[HelpCategory.FITTING]] == ["fit.linear", "fit.gauss"]

    def test_empty_catalog(self):
        assert HelpCatalog([]).by_category() == {}


class TestSearch:
    def test_empty_query_returns_all(self, catalog):
        assert catalog.search("") == catalog.topics()
        assert catalog.search("   ") == catalog.topics()

    def test_short_terms_ignored(self, catalog):
        assert catalog.search("a") == catalog.topics()
        assert [t.id for t in catalog.search("a norm")] == ["prep.norm"]

    def test_case_insensitive(self, catalog):
        assert [t.id for t in catalog.search("NORMALIZE")] == ["prep.norm"]

    def test_multi_term_is_and(self, catalog):
        assert [t.id for t in catalog.search("rescales column")] == ["prep.norm"]
        assert catalog.search("rescales gaussian") == ()

    def test_keyword_match(self, catalog):
        assert [t.id for t in catalog.search("bell")] == ["fit.gauss"]

    def test_matches_parameter_labels_and_category(self, catalog):
        assert [t.id for t in catalog.search("amplitude")] == ["fit.gauss"]
        assert [t.id for t in catalog.search("preprocessing")] == ["prep.norm"]

    def test_title_or_keyword_matches_rank_first(self, catalog):
        # "t-test" is in the title of stats.t and only in the summary of fit.linear.
        assert [t.id for t in catalog.search("t-test")] == ["stats.t", "fit.linear"]
        assert [t.id for t in catalog.search("student")] == ["stats.t"]

    def test_ties_keep_catalog_order(self):
        cat = HelpCatalog([_topic("a.1", "Alpha one"), _topic("a.2", "Alpha two"), _topic("a.3", "Alpha three")])
        assert [t.id for t in cat.search("alpha")] == ["a.1", "a.2", "a.3"]

    def test_no_match(self, catalog):
        assert catalog.search("zzzz") == ()


class TestBuildCatalog:
    def test_content_modules_listed_in_order(self):
        assert [name.rsplit(".", 1)[-1] for name in CONTENT_MODULES] == [
            "panels", "statistics", "descriptive", "preprocessing", "analysis",
            "signal", "fitting", "transforms", "measurements",
        ]

    def test_build_returns_catalog(self):
        assert isinstance(build_help_catalog(), HelpCatalog)
