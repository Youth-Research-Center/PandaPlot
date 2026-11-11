"""Tests for the examples browser's search and tag filtering."""

from pandaplot.models.project.example_info import ExampleLevel, ExampleSection, example_tag
from pandaplot.utils.example_filter import filter_examples, tag_counts
from pandaplot.utils.examples import ExampleProject


def _example(name: str, *, summary: str = "", description: str = "", tags: tuple[str, ...] = ()) -> ExampleProject:
    return ExampleProject(
        path=f"/examples/{name}.pplot", name=name, summary=summary, description=description, section=ExampleSection.GETTING_STARTED,
        level=ExampleLevel.BEGINNER, tags=tuple(example_tag(tag_id) for tag_id in tags), featured_chart_ids=(), start_note_id=None,
        data_credit="", cover_image=None, dataset_count=0, chart_count=0, note_count=0,
    )


PENDULUM = _example("Pendulum", summary="Swinging mass.", description="Damped oscillation of a pendulum.", tags=("physics", "curve_fitting"))
SPRING = _example("Spring", summary="Hooke's law.", tags=("physics", "smoothing"))
SURVEY = _example("Survey", summary="Class marks.", tags=("statistics", "curve_fitting"))
PLAIN = _example("Plain")
ALL = [PENDULUM, SPRING, SURVEY, PLAIN]
NO_TAGS = frozenset()


def _names(examples: list[ExampleProject]) -> list[str]:
    return [example.name for example in examples]


def test_blank_query_and_no_tags_keep_everything_in_order():
    assert filter_examples(ALL, query="  ", selected_tag_ids=NO_TAGS) == ALL


def test_search_is_case_insensitive_and_covers_name_summary_description_and_tag_labels():
    assert _names(filter_examples(ALL, query="PENDULUM", selected_tag_ids=NO_TAGS)) == ["Pendulum"]
    assert _names(filter_examples(ALL, query="hooke", selected_tag_ids=NO_TAGS)) == ["Spring"]
    assert _names(filter_examples(ALL, query="oscillation", selected_tag_ids=NO_TAGS)) == ["Pendulum"]
    assert _names(filter_examples(ALL, query="statistics", selected_tag_ids=NO_TAGS)) == ["Survey"]


def test_every_search_word_must_match_in_any_field():
    assert _names(filter_examples(ALL, query="damped physics", selected_tag_ids=NO_TAGS)) == ["Pendulum"]
    assert filter_examples(ALL, query="damped hooke", selected_tag_ids=NO_TAGS) == []


def test_tags_in_one_group_combine_with_or():
    result = filter_examples(ALL, query="", selected_tag_ids=frozenset({"physics", "statistics"}))
    assert _names(result) == ["Pendulum", "Spring", "Survey"]


def test_tags_across_groups_combine_with_and():
    result = filter_examples(ALL, query="", selected_tag_ids=frozenset({"physics", "curve_fitting"}))
    assert _names(result) == ["Pendulum"]
    result = filter_examples(ALL, query="", selected_tag_ids=frozenset({"physics", "statistics", "curve_fitting"}))
    assert _names(result) == ["Pendulum", "Survey"]  # (physics OR statistics) AND curve_fitting


def test_unknown_tag_ids_do_not_filter():
    assert filter_examples(ALL, query="", selected_tag_ids=frozenset({"nope"})) == ALL


def test_tag_counts_are_the_results_if_the_tag_were_added():
    counts = tag_counts(ALL, query="", selected_tag_ids=frozenset({"physics"}))
    assert counts["physics"] == 2  # already selected: the current result count
    assert counts["statistics"] == 3  # same group: OR adds Survey
    assert counts["curve_fitting"] == 1  # other group: AND with physics leaves Pendulum
    assert counts["smoothing"] == 1
    assert counts["data_import"] == 0


def test_tag_counts_apply_the_query_and_cover_only_vocabulary_tags():
    counts = tag_counts(ALL, query="damped", selected_tag_ids=NO_TAGS)
    assert counts["physics"] == 1
    assert counts["statistics"] == 0
    assert len(counts) == 12


def test_empty_inputs():
    assert filter_examples([], query="x", selected_tag_ids=frozenset({"physics"})) == []
    assert set(tag_counts([], query="", selected_tag_ids=NO_TAGS).values()) == {0}


def test_search_text_is_built_once_per_example_across_repeated_filtering():
    from pandaplot.utils import example_filter

    example_filter._haystack.cache_clear()

    for _ in range(3):
        filter_examples(ALL, query="physics", selected_tag_ids=NO_TAGS)
        tag_counts(ALL, query="physics", selected_tag_ids=NO_TAGS)

    info = example_filter._haystack.cache_info()
    assert info.misses == len(ALL)
    assert info.hits > 0


def test_tag_groups_come_from_the_tag_vocabulary():
    assert not hasattr(__import__("pandaplot.utils.example_filter", fromlist=["x"]), "_TAG_GROUPS")
    assert _names(filter_examples(ALL, query="", selected_tag_ids=frozenset({"physics", "not_a_tag"}))) == ["Pendulum", "Spring"]


def test_search_covers_the_level_and_section_labels():
    advanced = ExampleProject(
        path="/examples/Fit.pplot", name="Fit", summary="", description="", section=ExampleSection.ANALYSING_DATA,
        level=ExampleLevel.INTERMEDIATE, tags=(), featured_chart_ids=(), start_note_id=None,
        data_credit="", cover_image=None, dataset_count=0, chart_count=0, note_count=0,
    )
    examples = [PENDULUM, advanced]

    assert _names(filter_examples(examples, query=ExampleLevel.BEGINNER.label, selected_tag_ids=NO_TAGS)) == ["Pendulum"]
    assert _names(filter_examples(examples, query=ExampleLevel.INTERMEDIATE.label, selected_tag_ids=NO_TAGS)) == ["Fit"]
    assert _names(filter_examples(examples, query=ExampleSection.ANALYSING_DATA.label, selected_tag_ids=NO_TAGS)) == ["Fit"]


def test_search_matches_the_text_of_markdown_but_not_its_link_and_image_markup():
    linked = _example(
        "Linked",
        description="## Sources\n\nSee [the **NOAA** archive](https://noaa.example/data.csv) and ![a photo](cover.png).",
    )

    for word in ("http", "noaa.example", "png", "##", "**"):
        assert filter_examples([linked], query=word, selected_tag_ids=NO_TAGS) == [], word
    for word in ("sources", "NOAA archive", "photo"):
        assert filter_examples([linked], query=word, selected_tag_ids=NO_TAGS) == [linked], word
