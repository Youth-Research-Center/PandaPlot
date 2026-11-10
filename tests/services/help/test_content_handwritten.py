"""Tests for the hand-written help content (panels, analysis, transforms, measurements).

Only this task's modules are used here, so the tests do not depend on the other
content modules being finished.
"""

from types import ModuleType

import pytest

from pandaplot.analysis.analysis_types import AnalysisType, DerivativeMethod, InterpolationMethod, SmoothingMethod
from pandaplot.services.help.content import analysis, measurements, panels, transforms
from pandaplot.services.help.content import panel_defaults as defaults
from pandaplot.services.help.help_catalog import HelpCatalog
from pandaplot.services.help.help_types import PANEL_TOPIC_IDS, HelpCategory, HelpTopic
from pandaplot.services.transform.expression_engine import allowed_expression_names, get_transformation_templates

_MODULES = (panels, analysis, transforms, measurements)


@pytest.fixture(scope="module")
def catalog() -> HelpCatalog:
    """Catalog built from the hand-written modules only."""
    return HelpCatalog([topic for module in _MODULES for topic in module.topics()])


def _normalised(text: str) -> str:
    return text.lower().replace("_", " ")


class TestPanelTopics:
    @pytest.mark.parametrize("topic_id", PANEL_TOPIC_IDS)
    def test_panel_topic_exists_with_steps(self, catalog: HelpCatalog, topic_id: str) -> None:
        topic = catalog.get(topic_id)

        assert topic is not None
        assert topic.category is HelpCategory.PANELS
        assert topic.steps
        assert all(step.strip() for step in topic.steps)

    def test_only_panel_ids_are_in_the_panels_category(self) -> None:
        assert [topic.id for topic in panels.topics()] == list(PANEL_TOPIC_IDS)

    @pytest.mark.parametrize("topic_id", PANEL_TOPIC_IDS)
    def test_panel_topic_links_to_operation_topics(self, catalog: HelpCatalog, topic_id: str) -> None:
        topic = catalog.get(topic_id)

        assert topic is not None
        operation_links = [related_id for related_id in topic.related if related_id not in PANEL_TOPIC_IDS]
        assert operation_links, topic_id
        assert topic_id not in topic.related
        assert len(set(topic.related)) == len(topic.related)


class TestAnalysisTopics:
    @pytest.mark.parametrize(
        ("mapping", "enum_type"),
        [
            (analysis.ANALYSIS_TOPIC_IDS, AnalysisType),
            (analysis.SMOOTHING_TOPIC_IDS, SmoothingMethod),
            (analysis.DERIVATIVE_TOPIC_IDS, DerivativeMethod),
            (analysis.INTERPOLATION_TOPIC_IDS, InterpolationMethod),
        ],
    )
    def test_mapping_covers_every_enum_member(self, mapping: dict, enum_type: type) -> None:
        assert set(mapping) == set(enum_type)

    @pytest.mark.parametrize(
        "mapping",
        [
            analysis.ANALYSIS_TOPIC_IDS,
            analysis.SMOOTHING_TOPIC_IDS,
            analysis.DERIVATIVE_TOPIC_IDS,
            analysis.INTERPOLATION_TOPIC_IDS,
        ],
    )
    def test_mapped_ids_exist_in_the_catalog(self, catalog: HelpCatalog, mapping: dict) -> None:
        unknown = {member: topic_id for member, topic_id in mapping.items() if catalog.get(topic_id) is None}

        assert mapping
        assert unknown == {}
        categories = {topic.id: topic.category for topic in catalog.topics()}
        assert {categories[topic_id] for topic_id in mapping.values()} == {HelpCategory.ANALYSIS}

    @pytest.mark.parametrize(
        "mapping",
        [analysis.SMOOTHING_TOPIC_IDS, analysis.DERIVATIVE_TOPIC_IDS, analysis.INTERPOLATION_TOPIC_IDS],
    )
    def test_method_topics_mention_their_methods(self, catalog: HelpCatalog, mapping: dict) -> None:
        for member, topic_id in mapping.items():
            topic = catalog.get(topic_id)
            assert topic is not None
            head = _normalised("\n".join((topic.id, *topic.keywords)))
            assert _normalised(member.value) in head, f"{member} is not covered by the keywords or id of {topic_id}"

    def test_analysis_topics_are_in_the_analysis_category(self) -> None:
        assert all(topic.category is HelpCategory.ANALYSIS for topic in analysis.topics())

    def test_operation_topics_state_the_numbers_of_panel_defaults(self, catalog: HelpCatalog) -> None:
        savgol = catalog.get(analysis.SMOOTHING_TOPIC_IDS[SmoothingMethod.SAVGOL])
        rolling = catalog.get(analysis.SMOOTHING_TOPIC_IDS[SmoothingMethod.ROLLING_MEAN])
        interpolation = catalog.get(analysis.ANALYSIS_TOPIC_IDS[AnalysisType.INTERPOLATION])
        assert savgol is not None
        assert rolling is not None
        assert interpolation is not None

        assert f"starts at {defaults.SAVGOL_WINDOW_LENGTH.default} and can be set from 3 to 101" in savgol.explanation
        assert f"starts at {defaults.SAVGOL_POLYNOMIAL_ORDER.default} and can be set from 1 to 10" in savgol.explanation
        assert f"starts at {defaults.ROLLING_WINDOW_DATASET.default}." in rolling.explanation
        assert "from 2 to 50" in rolling.explanation
        assert "from 2 to 100" in rolling.explanation
        assert f"starts at {defaults.INTERPOLATION_POINTS_DATASET.default} " in interpolation.explanation
        assert "(10 to 10000)" in interpolation.explanation
        assert f"at {defaults.INTERPOLATION_POINTS_CHART.default} " in interpolation.explanation
        assert "(10 to 100000)" in interpolation.explanation

    def test_interpolation_topic_explains_how_the_dataset_result_is_written(self, catalog: HelpCatalog) -> None:
        interpolation = catalog.get(analysis.ANALYSIS_TOPIC_IDS[AnalysisType.INTERPOLATION])
        assert interpolation is not None

        assert "first row of the dataset" in interpolation.explanation
        assert "must not be larger than the number of rows" in interpolation.explanation

    def test_chart_analysis_preview_is_not_described_as_summary_statistics(self, catalog: HelpCatalog) -> None:
        for analysis_type in (AnalysisType.INTEGRAL, AnalysisType.ARC_LENGTH, AnalysisType.SMOOTHING):
            topic = catalog.get(analysis.ANALYSIS_TOPIC_IDS[analysis_type])
            assert topic is not None
            text = "\n".join((*topic.steps, topic.explanation))
            assert "Chart Analysis panel it shows the number of points and the first rows" in text
            assert "In the Analysis Operations panel the preview shows" in text

    def test_analysis_topics_are_found_by_common_synonyms(self, catalog: HelpCatalog) -> None:
        expectations = {
            "differentiate": "analysis.derivative",
            "slope": "analysis.derivative",
            "area under curve": "analysis.integral",
            "moving average": "analysis.smoothing_rolling_mean",
            "savitzky golay": "analysis.smoothing_savgol",
            "loess": "analysis.smoothing_lowess",
        }

        for query, topic_id in expectations.items():
            assert topic_id in [topic.id for topic in catalog.search(query)], query


class TestTransformTopics:
    def test_names_topic_lists_every_allowed_name_and_math(self, catalog: HelpCatalog) -> None:
        topic = catalog.get(transforms.TOPIC_NAMES)

        assert topic is not None
        assert ", ".join((*allowed_expression_names(), "math")) in topic.explanation

    def test_insert_function_topic_lists_every_template(self, catalog: HelpCatalog) -> None:
        topic = catalog.get(transforms.TOPIC_INSERT_FUNCTION)

        assert topic is not None
        expected = sum(len(entries) for entries in get_transformation_templates().values())
        assert len(topic.parameters) == expected
        assert all(code for _label, code in topic.parameters)

    def test_transform_topics_are_in_the_transforms_category(self) -> None:
        topics = transforms.topics()

        assert topics
        assert all(topic.category is HelpCategory.TRANSFORMS for topic in topics)

    def test_formula_columns_topic_uses_the_panel_labels(self, catalog: HelpCatalog) -> None:
        topic = catalog.get(transforms.TOPIC_FORMULA_COLUMNS)

        assert topic is not None
        text = "\n".join(topic.steps) + topic.explanation
        assert "Save as formula column" in text
        assert "Live (recompute when sources change)" in text
        assert "Recompute formula column(s)" in text


class TestMeasurementTopics:
    def test_analyze_topic_exists(self, catalog: HelpCatalog) -> None:
        topic = catalog.get(measurements.TOPIC_ANALYZE)

        assert topic is not None
        assert topic.id == "measurements.analyze"
        assert topic.category is HelpCategory.MEASUREMENTS
        assert topic.steps

    def test_analyze_topic_says_where_the_wizard_is_opened(self, catalog: HelpCatalog) -> None:
        topic = catalog.get(measurements.TOPIC_ANALYZE)

        assert topic is not None
        assert "Analyze Measurements" in topic.steps[0]
        assert "Project Explorer" in topic.steps[0]


class TestAllModules:
    def test_catalog_builds_without_duplicate_ids(self, catalog: HelpCatalog) -> None:
        assert len(catalog.topics()) == sum(len(module.topics()) for module in _MODULES)

    @pytest.mark.parametrize("module", _MODULES)
    def test_topics_returns_fresh_valid_topics(self, module: ModuleType) -> None:
        result = module.topics()

        assert result
        assert all(isinstance(topic, HelpTopic) for topic in result)
        assert result == module.topics()

    def test_related_ids_within_these_modules_resolve(self, catalog: HelpCatalog) -> None:
        own_prefixes = ("analysis.", "transforms.", "measurements.", "panel.")
        own_links = {
            (topic.id, related_id)
            for topic in catalog.topics()
            for related_id in topic.related
            if related_id.startswith(own_prefixes)
        }
        unresolved = sorted(link for link in own_links if catalog.get(link[1]) is None)

        assert own_links
        assert unresolved == []

    def test_related_ids_to_other_modules_follow_the_agreed_naming(self, catalog: HelpCatalog) -> None:
        agreed_prefixes = ("stats.", "preprocessing.", "signal.", "fit.", "descriptive.", "charts.")
        own_prefixes = ("analysis.", "transforms.", "measurements.", "panel.")
        for topic in catalog.topics():
            for related_id in topic.related:
                assert related_id.startswith(own_prefixes + agreed_prefixes), f"{topic.id} links to {related_id}"
