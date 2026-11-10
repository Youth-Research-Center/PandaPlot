"""Example settings of a project: the metadata the examples browser shows (#608)."""

import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

MAX_FEATURED_CHARTS = 3


class ExampleSection(StrEnum):
    """Learning-goal section an example is listed under. The value is persisted."""

    GETTING_STARTED = "getting_started"
    ANALYSING_DATA = "analysing_data"
    CHARTS = "charts"

    @property
    def label(self) -> str:
        return _SECTION_LABELS[self]


class ExampleLevel(StrEnum):
    """Difficulty of an example. The value is persisted."""

    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"

    @property
    def label(self) -> str:
        return _LEVEL_LABELS[self]


class TagGroup(StrEnum):
    TOPIC = "topic"
    TECHNIQUE = "technique"


_SECTION_LABELS = {
    ExampleSection.GETTING_STARTED: "Getting started",
    ExampleSection.ANALYSING_DATA: "Analysing data",
    ExampleSection.CHARTS: "Charts",
}

_LEVEL_LABELS = {
    ExampleLevel.BEGINNER: "Beginner",
    ExampleLevel.INTERMEDIATE: "Intermediate",
}


@dataclass(frozen=True)
class ExampleTag:
    id: str
    label: str
    group: TagGroup


EXAMPLE_TAGS: tuple[ExampleTag, ...] = (
    ExampleTag("physics", "Physics", TagGroup.TOPIC),
    ExampleTag("mathematics", "Mathematics", TagGroup.TOPIC),
    ExampleTag("statistics", "Statistics", TagGroup.TOPIC),
    ExampleTag("signal_processing", "Signal processing", TagGroup.TOPIC),
    ExampleTag("business", "Business data", TagGroup.TOPIC),
    ExampleTag("curve_fitting", "Curve fitting", TagGroup.TECHNIQUE),
    ExampleTag("smoothing", "Smoothing", TagGroup.TECHNIQUE),
    ExampleTag("derivatives", "Derivatives and integrals", TagGroup.TECHNIQUE),
    ExampleTag("statistical_tests", "Statistical tests", TagGroup.TECHNIQUE),
    ExampleTag("descriptive_statistics", "Descriptive statistics", TagGroup.TECHNIQUE),
    ExampleTag("charts", "Charts and styling", TagGroup.TECHNIQUE),
    ExampleTag("data_import", "Importing data", TagGroup.TECHNIQUE),
)

_TAGS_BY_ID = {tag.id: tag for tag in EXAMPLE_TAGS}


def example_tag(tag_id: str) -> ExampleTag | None:
    """Return the vocabulary tag with this id, or None if it is unknown."""
    return _TAGS_BY_ID.get(tag_id)


def _string_ids(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, str)]


@dataclass(frozen=True)
class ExampleInfo:
    """Typed example settings stored with a project.

    Turning ``is_example`` off keeps the other values.

    Raises:
        ValueError: If a tag id is not in ``EXAMPLE_TAGS`` or more than 3 featured charts are given.
    """

    is_example: bool = False
    summary: str = ""
    section: ExampleSection = ExampleSection.GETTING_STARTED
    level: ExampleLevel = ExampleLevel.BEGINNER
    tag_ids: tuple[str, ...] = ()
    featured_chart_ids: tuple[str, ...] = ()
    start_note_id: str | None = None
    data_credit: str = ""

    def __post_init__(self) -> None:
        unknown = [tag_id for tag_id in self.tag_ids if tag_id not in _TAGS_BY_ID]
        if unknown:
            raise ValueError(f"Unknown example tag ids: {unknown}")
        if len(self.featured_chart_ids) > MAX_FEATURED_CHARTS:
            raise ValueError(f"At most {MAX_FEATURED_CHARTS} featured charts are allowed, got {len(self.featured_chart_ids)}")

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dictionary."""
        return {
            "is_example": self.is_example,
            "summary": self.summary,
            "section": self.section.value,
            "level": self.level.value,
            "tags": list(self.tag_ids),
            "featured_chart_ids": list(self.featured_chart_ids),
            "start_note_id": self.start_note_id,
            "data_credit": self.data_credit,
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "ExampleInfo":
        """Build from file data. Never raises: invalid values fall back to defaults.

        Unknown tag ids are dropped with a warning, and featured chart ids beyond 3 are truncated.
        """
        if not isinstance(data, dict):
            return cls()

        tag_ids: list[str] = []
        for tag_id in _string_ids(data.get("tags")):
            if tag_id not in _TAGS_BY_ID:
                logger.warning("Ignoring unknown example tag '%s'", tag_id)
            elif tag_id not in tag_ids:
                tag_ids.append(tag_id)

        featured = _string_ids(data.get("featured_chart_ids"))[:MAX_FEATURED_CHARTS]
        start_note_id = data.get("start_note_id")
        summary = data.get("summary")
        data_credit = data.get("data_credit")
        try:
            section = ExampleSection(data.get("section"))
        except ValueError:
            section = ExampleSection.GETTING_STARTED
        try:
            level = ExampleLevel(data.get("level"))
        except ValueError:
            level = ExampleLevel.BEGINNER

        return cls(
            is_example=data.get("is_example") is True,
            summary=summary if isinstance(summary, str) else "",
            section=section,
            level=level,
            tag_ids=tuple(tag_ids),
            featured_chart_ids=tuple(featured),
            start_note_id=start_note_id if isinstance(start_note_id, str) else None,
            data_credit=data_credit if isinstance(data_credit, str) else "",
        )


_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+")
_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_EMPHASIS_RE = re.compile(r"(\*\*|__|\*|_|~~|`)")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


def summary_from_description(text: str, max_chars: int = 160) -> str:
    """Return the first sentence of a Markdown description as plain text.

    Markdown markers (heading ``#``, emphasis, code ticks, links ``[t](u)`` -> ``t``) are removed. Heading
    lines are skipped when the text has other content. A sentence longer than ``max_chars`` is cut at a word
    boundary and ends with an ellipsis.

    Args:
        text: Markdown text.
        max_chars: Maximum length of the result, ellipsis included.

    Returns:
        The summary, or an empty string for empty input.
    """
    if not isinstance(text, str) or not text.strip():
        return ""
    lines = text.splitlines()
    body = [line for line in lines if line.strip() and not _HEADING_RE.match(line)]
    chosen = body or [_HEADING_RE.sub("", line) for line in lines if line.strip()]

    paragraph: list[str] = []
    for line in chosen:
        paragraph.append(line.strip())
        # Stop at the first line that completes a sentence; otherwise keep joining wrapped lines.
        if _SENTENCE_END_RE.search(" ".join(paragraph) + " ") or paragraph[-1].endswith((".", "!", "?")):
            break
    plain = _LINK_RE.sub(r"\1", " ".join(paragraph))
    plain = _EMPHASIS_RE.sub("", plain)
    plain = re.sub(r"\s+", " ", plain).strip()
    sentence = _SENTENCE_END_RE.split(plain, maxsplit=1)[0]

    if len(sentence) <= max_chars:
        return sentence
    cut = sentence[: max_chars - 1]
    if not sentence[max_chars - 1].isspace() and " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:") + "…"
