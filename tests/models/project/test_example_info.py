import json

import pytest

from pandaplot.models.project.example_info import (
    EXAMPLE_TAGS,
    ExampleInfo,
    ExampleLevel,
    ExampleSection,
    TagGroup,
    example_tag,
    summary_from_description,
)
from pandaplot.models.project.project import Project


def _full() -> ExampleInfo:
    return ExampleInfo(
        is_example=True,
        summary="Fit a decay curve.",
        section=ExampleSection.ANALYSING_DATA,
        level=ExampleLevel.INTERMEDIATE,
        tag_ids=("physics", "curve_fitting"),
        featured_chart_ids=("c1", "c2"),
        start_note_id="n1",
        data_credit="Measured in class.",
    )


class TestVocabulary:
    def test_labels(self):
        assert ExampleSection.ANALYSING_DATA.label == "Analysing data"
        assert ExampleSection.GETTING_STARTED.label == "Getting started"
        assert ExampleSection.CHARTS.label == "Charts"
        assert ExampleLevel.BEGINNER.label == "Beginner"
        assert ExampleLevel.INTERMEDIATE.label == "Intermediate"

    def test_tags_unique_and_both_groups_present(self):
        ids = [t.id for t in EXAMPLE_TAGS]
        assert len(ids) == len(set(ids)) == 12
        assert {t.group for t in EXAMPLE_TAGS} == set(TagGroup)

    def test_example_tag_lookup(self):
        assert example_tag("derivatives").label == "Derivatives and integrals"
        assert example_tag("nope") is None


class TestExampleInfo:
    def test_round_trip(self):
        info = _full()
        assert ExampleInfo.from_dict(info.to_dict()) == info

    def test_default_round_trip(self):
        assert ExampleInfo.from_dict(ExampleInfo().to_dict()) == ExampleInfo()

    def test_to_dict_is_json_safe(self):
        data = json.loads(json.dumps(_full().to_dict()))
        assert data["tags"] == ["physics", "curve_fitting"]
        assert data["section"] == "analysing_data"
        assert ExampleInfo.from_dict(data) == _full()

    def test_turning_off_is_example_keeps_values(self):
        data = _full().to_dict()
        data["is_example"] = False
        info = ExampleInfo.from_dict(data)
        assert not info.is_example
        assert info.summary == "Fit a decay curve."

    def test_unknown_section_and_level_fall_back(self):
        info = ExampleInfo.from_dict({"section": "bogus", "level": 5})
        assert info.section is ExampleSection.GETTING_STARTED
        assert info.level is ExampleLevel.BEGINNER

    def test_unknown_tags_dropped_with_warning(self, caplog):
        with caplog.at_level("WARNING"):
            info = ExampleInfo.from_dict({"tags": ["physics", "bogus", 3, "physics", "smoothing"]})
        assert info.tag_ids == ("physics", "smoothing")
        assert "bogus" in caplog.text

    def test_featured_truncated_to_three(self):
        assert ExampleInfo.from_dict({"featured_chart_ids": ["a", "b", "c", "d"]}).featured_chart_ids == ("a", "b", "c")

    @pytest.mark.parametrize("bad", [None, "x", 3, [], ["a"]])
    def test_garbage_gives_default(self, bad):
        assert ExampleInfo.from_dict(bad) == ExampleInfo()

    def test_wrong_field_types_give_defaults(self):
        info = ExampleInfo.from_dict({
            "is_example": "yes", "summary": 4, "tags": "physics", "featured_chart_ids": {"a": 1},
            "start_note_id": 7, "data_credit": ["x"],
        })
        assert info == ExampleInfo()

    def test_post_init_validation(self):
        with pytest.raises(ValueError, match="Unknown example tag"):
            ExampleInfo(tag_ids=("bogus",))
        with pytest.raises(ValueError, match="featured"):
            ExampleInfo(featured_chart_ids=("a", "b", "c", "d"))


class TestProjectField:
    def test_project_round_trip(self):
        project = Project(name="P")
        project.example_info = _full()
        restored = Project.from_dict(json.loads(json.dumps(project.to_dict())))
        assert restored.example_info == _full()

    def test_old_project_dict_loads_with_defaults(self):
        restored = Project.from_dict({"name": "Old", "description": "d", "schema_version": 6})
        assert restored.example_info == ExampleInfo()
        assert restored.cover_image is None

    def test_cover_image_not_in_to_dict(self):
        project = Project()
        project.cover_image = b"png"
        assert "cover_image" not in project.to_dict()


class TestSummaryFromDescription:
    def test_empty(self):
        assert summary_from_description("") == ""
        assert summary_from_description("  \n ") == ""

    def test_first_sentence(self):
        assert summary_from_description("First one. Second one.") == "First one."

    def test_strips_markdown(self):
        text = "# Title\n\nSee **bold** and *em* with [a link](http://x.y) and `code`. More."
        assert summary_from_description(text) == "See bold and em with a link and code."

    def test_heading_only_uses_heading_text(self):
        assert summary_from_description("## Just a heading") == "Just a heading"

    def test_wrapped_lines_join(self):
        assert summary_from_description("A sentence that\nwraps here. Next.") == "A sentence that wraps here."

    def test_truncates_at_word_boundary(self):
        text = "word " * 100
        result = summary_from_description(text, max_chars=22)
        assert result.endswith("…")
        assert len(result) <= 22
        assert result == "word word word word…"

    def test_short_text_without_period_unchanged(self):
        assert summary_from_description("No period here") == "No period here"
