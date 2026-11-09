"""Tests for the help topics derived from the operation catalogs.

These build a catalog from the five derived-content modules only, so they do not depend on the hand-written modules.
"""

import pytest

from pandaplot.analysis.descriptive_types import DESCRIPTIVE_STATS
from pandaplot.analysis.preprocessing_types import PREPROCESSING_METHODS, PreprocessingMethod
from pandaplot.analysis.signal.signal_types import SIGNAL_ANALYSES, SignalAnalysisType
from pandaplot.analysis.stats_types import STAT_TESTS, InputMode, StatTestType
from pandaplot.services.fit.fit_service import CUSTOM_FUNCTION_NAMES, FIT_DEFINITIONS
from pandaplot.services.help.content import descriptive, fitting, preprocessing, signal, statistics
from pandaplot.services.help.help_catalog import HelpCatalog
from pandaplot.services.help.help_types import (
    FIT_TOPIC_CUSTOM,
    FIT_TOPIC_OVERVIEW,
    PANEL_TOPIC_IDS,
    HelpCategory,
    fit_topic_id,
)

MODULES = (statistics, descriptive, preprocessing, signal, fitting)


@pytest.fixture(scope="module")
def catalog() -> HelpCatalog:
    return HelpCatalog([topic for module in MODULES for topic in module.topics()])


def _expected_ids() -> set[str]:
    ids: set[str] = set()
    ids.update(statistics.STAT_TEST_TOPIC_IDS.values())
    ids.update(preprocessing.PREPROCESSING_TOPIC_IDS.values())
    ids.update(signal.SIGNAL_TOPIC_IDS.values())
    ids.update(fitting.FIT_MODEL_TOPIC_IDS.values())
    ids.update({FIT_TOPIC_OVERVIEW, descriptive.DESCRIPTIVE_OVERVIEW_TOPIC_ID})
    return ids


class TestMappings:
    def test_stat_tests_mapping_is_complete(self, catalog):
        assert set(statistics.STAT_TEST_TOPIC_IDS) == set(StatTestType)
        for test_type, topic_id in statistics.STAT_TEST_TOPIC_IDS.items():
            assert topic_id == f"stats.{test_type.value}"
            assert catalog.get(topic_id) is not None

    def test_preprocessing_mapping_is_complete(self, catalog):
        assert set(preprocessing.PREPROCESSING_TOPIC_IDS) == set(PreprocessingMethod)
        for method, topic_id in preprocessing.PREPROCESSING_TOPIC_IDS.items():
            assert topic_id == f"preprocessing.{method.value}"
            assert catalog.get(topic_id) is not None

    def test_signal_mapping_is_complete(self, catalog):
        assert set(signal.SIGNAL_TOPIC_IDS) == set(SignalAnalysisType)
        for analysis_type, topic_id in signal.SIGNAL_TOPIC_IDS.items():
            assert topic_id == f"signal.{analysis_type.value}"
            assert catalog.get(topic_id) is not None

    def test_fit_mapping_covers_every_model_and_the_custom_function(self, catalog):
        assert set(fitting.FIT_MODEL_TOPIC_IDS) == {*FIT_DEFINITIONS, "Custom Function"}
        for name, topic_id in fitting.FIT_MODEL_TOPIC_IDS.items():
            assert catalog.get(topic_id) is not None
            if name != "Custom Function":
                assert topic_id == fit_topic_id(name)
        assert fitting.FIT_MODEL_TOPIC_IDS["Custom Function"] == FIT_TOPIC_CUSTOM
        assert catalog.get(FIT_TOPIC_OVERVIEW) is not None

    def test_topic_ids_are_exactly_the_expected_ones(self, catalog):
        assert {topic.id for topic in catalog.topics()} == _expected_ids()

    def test_categories(self, catalog):
        assert {t.category for t in statistics.topics()} == {HelpCategory.STATISTICS}
        assert {t.category for t in descriptive.topics()} == {HelpCategory.DESCRIPTIVE}
        assert {t.category for t in preprocessing.topics()} == {HelpCategory.PREPROCESSING}
        assert {t.category for t in signal.topics()} == {HelpCategory.SIGNAL}
        assert {t.category for t in fitting.topics()} == {HelpCategory.FITTING}


class TestRelatedIds:
    def test_related_ids_only_point_at_these_modules_or_panels(self, catalog):
        allowed = _expected_ids() | set(PANEL_TOPIC_IDS)
        for topic in catalog.topics():
            assert topic.related, topic.id
            assert topic.id not in topic.related
            assert set(topic.related) <= allowed, topic.id
            assert len(set(topic.related)) == len(topic.related), topic.id

    def test_every_topic_has_keywords_and_steps(self, catalog):
        for topic in catalog.topics():
            if topic.id == descriptive.DESCRIPTIVE_OVERVIEW_TOPIC_ID or topic.category is not HelpCategory.STATISTICS:
                assert topic.steps, topic.id
            assert topic.keywords, topic.id


class TestStatisticsDerived:
    @pytest.mark.parametrize("test_type", list(StatTestType))
    def test_text_equals_source(self, catalog, test_type):
        info = STAT_TESTS[test_type]
        topic = catalog.get(statistics.STAT_TEST_TOPIC_IDS[test_type])
        assert topic.title == info.label
        assert topic.summary == info.description
        assert topic.explanation == info.explanation
        assert topic.assumptions == info.assumptions
        assert topic.formula == info.formula
        assert topic.example == info.example

    def test_derived_text_follows_the_source_catalog(self, monkeypatch):
        info = STAT_TESTS[StatTestType.PAIRED_T]
        monkeypatch.setattr(info, "explanation", "Changed explanation.")
        topic = next(t for t in statistics.topics() if t.id == "stats.paired_t")
        assert topic.explanation == "Changed explanation."

    @pytest.mark.parametrize("test_type", list(StatTestType))
    def test_parameters_match_the_panel_controls(self, catalog, test_type):
        info = STAT_TESTS[test_type]
        topic = catalog.get(statistics.STAT_TEST_TOPIC_IDS[test_type])
        labels = [label for label, _ in topic.parameters]
        assert all(meaning for _, meaning in topic.parameters)
        assert "Significance (α)" in labels
        assert ("Expected mean (μ₀)" in labels) is info.uses_popmean
        assert ("Alternative" in labels) is info.uses_alternative
        assert ("Assume equal variance (uncheck for Welch)" in labels) is info.uses_equal_var
        expected_inputs = {InputMode.ONE: ["Sample column"], InputMode.TWO: ["Column A", "Column B"], InputMode.MANY: ["Groups"]}
        assert labels[: len(expected_inputs[info.input_mode])] == expected_inputs[info.input_mode]

    def test_statistics_panel_is_related(self, catalog):
        assert all("panel.statistics" in t.related for t in statistics.topics())


class TestPreprocessingDerived:
    @pytest.mark.parametrize("method", list(PreprocessingMethod))
    def test_text_equals_source(self, catalog, method):
        info = PREPROCESSING_METHODS[method]
        topic = catalog.get(preprocessing.PREPROCESSING_TOPIC_IDS[method])
        assert topic.title == info.label
        assert topic.summary == info.description
        assert topic.formula == info.formula

    @pytest.mark.parametrize("method", list(PreprocessingMethod))
    def test_steps_and_parameters_follow_the_method(self, catalog, method):
        info = PREPROCESSING_METHODS[method]
        topic = catalog.get(preprocessing.PREPROCESSING_TOPIC_IDS[method])
        labels = [label for label, _ in topic.parameters]
        assert ("Output min" in labels) is info.uses_feature_range
        assert ("Output max" in labels) is info.uses_feature_range
        assert any(f"_{info.suffix}" in step for step in topic.steps)
        assert any(info.label in step for step in topic.steps)

    def test_derived_text_follows_the_source_catalog(self, monkeypatch):
        monkeypatch.setattr(PREPROCESSING_METHODS[PreprocessingMethod.CENTER], "description", "Changed description.")
        topic = next(t for t in preprocessing.topics() if t.id == "preprocessing.center")
        assert topic.summary == "Changed description."


class TestSignalDerived:
    @pytest.mark.parametrize("analysis_type", list(SignalAnalysisType))
    def test_text_equals_source(self, catalog, analysis_type):
        info = SIGNAL_ANALYSES[analysis_type]
        topic = catalog.get(signal.SIGNAL_TOPIC_IDS[analysis_type])
        assert topic.title == info.label
        assert topic.summary == info.description

    @pytest.mark.parametrize("analysis_type", list(SignalAnalysisType))
    def test_parameters_follow_the_analysis_flags(self, catalog, analysis_type):
        info = SIGNAL_ANALYSES[analysis_type]
        topic = catalog.get(signal.SIGNAL_TOPIC_IDS[analysis_type])
        labels = [label for label, _ in topic.parameters]
        assert labels[0] == "Signal column"
        expected = {
            "Sampling rate": info.uses_sampling_rate,
            "FFT size": info.uses_nfft,
            "Window": info.uses_window,
            "Segment size": info.uses_nperseg,
            "Overlap": info.uses_overlap,
            "Minimum height": info.uses_height,
            "Minimum distance": info.uses_distance,
            "Prominence": info.uses_prominence,
            "Threshold": info.uses_threshold,
        }
        for label, used in expected.items():
            assert (label in labels) is used, label

    def test_default_values_come_from_the_catalog(self, catalog):
        info = SIGNAL_ANALYSES[SignalAnalysisType.FFT]
        fft = dict(catalog.get("signal.fft").parameters)
        assert str(info.default_nfft) in fft["FFT size"]
        assert info.windows[0] in fft["Window"]
        stft = dict(catalog.get("signal.stft").parameters)
        assert str(SIGNAL_ANALYSES[SignalAnalysisType.STFT].default_nperseg) in stft["Segment size"]
        assert str(SIGNAL_ANALYSES[SignalAnalysisType.STFT].default_overlap) in stft["Overlap"]


class TestDescriptive:
    def test_overview_lists_every_statistic_label(self, catalog):
        topic = catalog.get(descriptive.DESCRIPTIVE_OVERVIEW_TOPIC_ID)
        labels = {label for label, _ in topic.parameters}
        assert set(DESCRIPTIVE_STATS.values()) <= labels
        assert dict(topic.parameters)["Median (Q2)"]

    def test_every_statistic_has_a_meaning(self):
        assert set(descriptive.STAT_MEANINGS) == set(DESCRIPTIVE_STATS)
        assert all(meaning.strip() for meaning in descriptive.STAT_MEANINGS.values())

    def test_statistic_labels_follow_the_source_catalog(self, monkeypatch):
        monkeypatch.setitem(DESCRIPTIVE_STATS, "mean", "Average value")
        topic = descriptive.topics()[0]
        assert "Average value" in {label for label, _ in topic.parameters}


class TestFitting:
    @pytest.mark.parametrize("name", list(FIT_DEFINITIONS))
    def test_one_parameter_entry_per_model_parameter(self, catalog, name):
        topic = catalog.get(fit_topic_id(name))
        assert [label for label, _ in topic.parameters] == FIT_DEFINITIONS[name]["parameters"]
        assert all(meaning.strip() for _, meaning in topic.parameters)

    @pytest.mark.parametrize("name", list(FIT_DEFINITIONS))
    def test_equation_comes_from_the_definition(self, catalog, name):
        topic = catalog.get(fit_topic_id(name))
        assert FIT_DEFINITIONS[name]["equation"] in topic.formula
        assert topic.title.startswith(name)
        assert FIT_DEFINITIONS[name]["category"] in " ".join(topic.steps)

    def test_model_text_has_no_unknown_models(self):
        assert set(fitting._MODEL_TEXT) == set(FIT_DEFINITIONS)
        for text in fitting._MODEL_TEXT.values():
            assert set(text.related) <= set(FIT_DEFINITIONS)

    def test_equation_follows_the_source_catalog(self, monkeypatch):
        monkeypatch.setitem(FIT_DEFINITIONS["Linear"], "equation", "m*x + n")
        topic = next(t for t in fitting.topics() if t.id == "fit.linear")
        assert "m*x + n" in topic.formula

    def test_custom_topic_lists_every_allowed_function(self, catalog):
        topic = catalog.get(FIT_TOPIC_CUSTOM)
        for function_name in CUSTOM_FUNCTION_NAMES:
            assert function_name in topic.explanation

    def test_custom_topic_follows_the_function_list(self, monkeypatch):
        monkeypatch.setattr(fitting, "CUSTOM_FUNCTION_NAMES", ("sin", "newfunc"))
        topic = next(t for t in fitting.topics() if t.id == FIT_TOPIC_CUSTOM)
        assert "newfunc" in topic.explanation

    def test_overview_mentions_the_main_concepts(self, catalog):
        topic = catalog.get(FIT_TOPIC_OVERVIEW)
        text = topic.explanation
        for term in ("R²", "Confidence Bands", "Fit Range", "error bars"):
            assert term in text
        assert "panel.fit" in topic.related
