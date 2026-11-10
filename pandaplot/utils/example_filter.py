"""Search and tag filtering for the examples browser (no Qt)."""

from collections.abc import Iterable

from pandaplot.models.project.example_info import EXAMPLE_TAGS, TagGroup
from pandaplot.utils.examples import ExampleProject

_TAG_GROUPS = {tag.id: tag.group for tag in EXAMPLE_TAGS}


def _matches_query(example: ExampleProject, words: list[str]) -> bool:
    """Whether every word occurs (case-insensitively) in the name, summary, description or a tag label."""
    haystack = " ".join([example.name, example.summary, example.description, *(tag.label for tag in example.tags)]).casefold()
    return all(word in haystack for word in words)


def _matches_tags(example: ExampleProject, selected_tag_ids: frozenset[str]) -> bool:
    """Whether the example has, in every group that has a selection, at least one selected tag."""
    own_tag_ids = {tag.id for tag in example.tags}
    selected_by_group: dict[TagGroup, set[str]] = {}
    for tag_id in selected_tag_ids:
        group = _TAG_GROUPS.get(tag_id)
        if group is not None:
            selected_by_group.setdefault(group, set()).add(tag_id)
    return all(own_tag_ids & group_ids for group_ids in selected_by_group.values())


def filter_examples(examples: Iterable[ExampleProject], *, query: str, selected_tag_ids: frozenset[str]) -> list[ExampleProject]:
    """Return the examples that match the search text and the selected tags, in their original order.

    Every whitespace-separated word of ``query`` must occur in the name, summary, description or a tag label
    (case-insensitive). Selected tags combine with OR inside a group and AND across groups; a group with nothing
    selected does not filter. Ids that are not in the tag vocabulary are ignored.

    Args:
        examples: The examples to filter.
        query: Search text; blank means no text filter.
        selected_tag_ids: Ids of the selected tags.

    Returns:
        The matching examples.
    """
    words = query.casefold().split()
    return [example for example in examples if _matches_query(example, words) and _matches_tags(example, selected_tag_ids)]


def tag_counts(examples: Iterable[ExampleProject], *, query: str, selected_tag_ids: frozenset[str]) -> dict[str, int]:
    """Return, for each vocabulary tag, how many examples would match if that tag were added to the selection.

    The search text is applied. For an already selected tag the count is the current number of results.

    Args:
        examples: The examples to count over.
        query: Search text; blank means no text filter.
        selected_tag_ids: Ids of the currently selected tags.

    Returns:
        A mapping of every vocabulary tag id to its count.
    """
    example_list = list(examples)
    return {
        tag.id: len(filter_examples(example_list, query=query, selected_tag_ids=selected_tag_ids | {tag.id})) for tag in EXAMPLE_TAGS
    }
