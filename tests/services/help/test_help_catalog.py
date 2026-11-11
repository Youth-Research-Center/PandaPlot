"""Tests for the help catalog and search."""

import pytest

from pandaplot.services.help.help_catalog import CONTENT_MODULES, HelpCatalog, _content_modules, build_help_catalog
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

    def test_matches_parameter_meanings(self, catalog):
        assert [t.id for t in catalog.search("height peak")] == ["fit.gauss"]

    def test_parameter_meaning_matches_rank_after_title_matches(self):
        cat = HelpCatalog([
            _topic("fit.overview", "Curve fitting", HelpCategory.FITTING, parameters=(("Fit Range", "The x interval of the curve"),)),
            _topic("fit.interval", "Interval picker", HelpCategory.FITTING),
        ])
        assert [t.id for t in cat.search("interval")] == ["fit.interval", "fit.overview"]

    def test_title_or_keyword_matches_rank_first(self, catalog):
        # "t-test" is in the title of stats.t and only in the summary of fit.linear.
        assert [t.id for t in catalog.search("t-test")] == ["stats.t", "fit.linear"]
        assert [t.id for t in catalog.search("student")] == ["stats.t"]

    def test_ties_keep_catalog_order(self):
        cat = HelpCatalog([_topic("a.1", "Alpha one"), _topic("a.2", "Alpha two"), _topic("a.3", "Alpha three")])
        assert [t.id for t in cat.search("alpha")] == ["a.1", "a.2", "a.3"]

    def test_no_match(self, catalog):
        assert catalog.search("zzzz") == ()

    @pytest.mark.parametrize(
        ("field", "term"),
        [("assumptions", "symmetric"), ("formula", "sigma"), ("example", "thermometer")],
    )
    def test_matches_assumptions_formula_and_example(self, field, term):
        cat = HelpCatalog([
            _topic("a.hit", "Alpha", **{field: f"Needs a {term} distribution."}),
            _topic("a.miss", "Beta"),
        ])
        assert [t.id for t in cat.search(term)] == ["a.hit"]

    def test_assumption_matches_rank_after_title_matches(self):
        cat = HelpCatalog([
            _topic("a.assumes", "Alpha", assumptions="Data are symmetric."),
            _topic("a.title", "Symmetric data"),
        ])
        assert [t.id for t in cat.search("symmetric")] == ["a.title", "a.assumes"]


class TestBuildCatalog:
    def test_content_modules_listed_in_order(self):
        assert [name.rsplit(".", 1)[-1] for name in CONTENT_MODULES] == [
            "panels", "charts", "chart_types", "statistics", "descriptive", "preprocessing", "analysis",
            "signal", "fitting", "transforms", "measurements",
        ]

    def test_content_modules_match_the_modules_the_builder_uses(self):
        assert tuple(module.__name__ for module in _content_modules()) == CONTENT_MODULES

    def test_build_returns_a_catalog_holding_every_content_modules_topics_in_order(self):
        catalog = build_help_catalog()

        expected_ids = [topic.id for module in _content_modules() for topic in module.topics()]
        assert isinstance(catalog, HelpCatalog)
        assert expected_ids
        assert [topic.id for topic in catalog.topics()] == expected_ids
