"""Tests for the help content model."""

import dataclasses

import pytest

from pandaplot.services.help.help_types import (
    PANEL_TOPIC_IDS,
    HelpCategory,
    HelpTopic,
    fit_topic_id,
)


def _topic(**overrides: object) -> HelpTopic:
    values: dict[str, object] = {"id": "a.b", "title": "T", "category": HelpCategory.PANELS, "summary": "S"}
    values.update(overrides)
    return HelpTopic(**values)  # type: ignore[arg-type]


class TestHelpTopicValidation:
    def test_valid_topic_has_defaults(self):
        topic = _topic()
        assert topic.steps == ()
        assert topic.related == ()
        assert topic.assumptions == ""

    @pytest.mark.parametrize("field", ["id", "title", "summary"])
    def test_empty_required_field_rejected(self, field):
        with pytest.raises(ValueError):
            _topic(**{field: ""})

    @pytest.mark.parametrize("field", ["title", "summary"])
    def test_blank_required_field_rejected(self, field):
        with pytest.raises(ValueError):
            _topic(**{field: "   "})

    @pytest.mark.parametrize("topic_id", ["a b", "a\tb", "a.b\n"])
    def test_whitespace_in_id_rejected(self, topic_id):
        with pytest.raises(ValueError):
            _topic(id=topic_id)

    def test_topic_is_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            _topic().title = "x"  # type: ignore[misc]


class TestCategoryOrder:
    def test_panels_first_and_measurements_last(self):
        members = list(HelpCategory)
        assert members[0] is HelpCategory.PANELS
        assert members[-1] is HelpCategory.MEASUREMENTS


class TestPanelTopicIds:
    def test_ten_unique_panel_ids(self):
        assert len(PANEL_TOPIC_IDS) == 10
        assert len(set(PANEL_TOPIC_IDS)) == 10
        assert all(topic_id.startswith("panel.") for topic_id in PANEL_TOPIC_IDS)


class TestFitTopicId:
    @pytest.mark.parametrize(("name", "expected"), [
        ("Exponential Growth to Maximum", "fit.exponential_growth_to_maximum"),
        ("Linear", "fit.linear"),
        ("  Gauss (Peak) ", "fit.gauss_peak"),
        ("a--b", "fit.a_b"),
    ])
    def test_slugs_model_name(self, name, expected):
        assert fit_topic_id(name) == expected
