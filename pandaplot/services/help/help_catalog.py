"""Help topic catalog and search."""

from collections.abc import Iterable
from functools import cache
from types import ModuleType

from pandaplot.services.help.help_types import HelpCategory, HelpTopic

CONTENT_MODULES: tuple[str, ...] = (
    "pandaplot.services.help.content.panels",
    "pandaplot.services.help.content.statistics",
    "pandaplot.services.help.content.descriptive",
    "pandaplot.services.help.content.preprocessing",
    "pandaplot.services.help.content.analysis",
    "pandaplot.services.help.content.signal",
    "pandaplot.services.help.content.fitting",
    "pandaplot.services.help.content.transforms",
    "pandaplot.services.help.content.measurements",
)

_MIN_TERM_LENGTH = 2


class HelpCatalog:
    """An ordered collection of help topics with lookup and search."""

    def __init__(self, topics: Iterable[HelpTopic]) -> None:
        """Create a catalog.

        Args:
            topics: Topics in catalog order.

        Raises:
            ValueError: If two topics share an id.
        """
        self._topics: tuple[HelpTopic, ...] = tuple(topics)
        self._by_id: dict[str, HelpTopic] = {}
        for topic in self._topics:
            if topic.id in self._by_id:
                raise ValueError(f"Duplicate help topic id: {topic.id}")
            self._by_id[topic.id] = topic

    def get(self, topic_id: str) -> HelpTopic | None:
        """Return the topic with the given id, or None if unknown."""
        return self._by_id.get(topic_id)

    def topics(self) -> tuple[HelpTopic, ...]:
        """Return all topics in catalog order."""
        return self._topics

    def by_category(self) -> dict[HelpCategory, tuple[HelpTopic, ...]]:
        """Group topics by category.

        Returns:
            Mapping in category definition order; categories without topics are omitted.
        """
        grouped: dict[HelpCategory, tuple[HelpTopic, ...]] = {}
        for category in HelpCategory:
            members = tuple(t for t in self._topics if t.category is category)
            if members:
                grouped[category] = members
        return grouped

    def search(self, query: str) -> tuple[HelpTopic, ...]:
        """Find topics matching every term of the query.

        Terms are whitespace-separated, case-insensitive substrings; terms shorter
        than two characters are ignored. An empty query returns every topic.
        Topics matching all terms in their title or keywords rank first; ties keep
        catalog order.

        Args:
            query: The user's search text.

        Returns:
            The matching topics, best matches first.
        """
        terms = [term for term in query.strip().lower().split() if len(term) >= _MIN_TERM_LENGTH]
        if not terms:
            return self._topics
        primary: list[HelpTopic] = []
        secondary: list[HelpTopic] = []
        for topic in self._topics:
            haystack = _searchable_text(topic)
            if not all(term in haystack for term in terms):
                continue
            head = _head_text(topic)
            if all(term in head for term in terms):
                primary.append(topic)
            else:
                secondary.append(topic)
        return tuple(primary + secondary)


def _head_text(topic: HelpTopic) -> str:
    """Return the lower-cased title and keywords of a topic."""
    return "\n".join((topic.title, *topic.keywords)).lower()


def _searchable_text(topic: HelpTopic) -> str:
    """Return the lower-cased text a search query is matched against."""
    parts = [
        topic.title,
        *topic.keywords,
        topic.category.value,
        topic.summary,
        topic.explanation,
        topic.assumptions,
        topic.formula,
        topic.example,
        *topic.steps,
        *(text for parameter in topic.parameters for text in parameter),
    ]
    return "\n".join(parts).lower()


def _content_modules() -> tuple[ModuleType, ...]:
    """Import the content modules lazily, in ``CONTENT_MODULES`` order.

    Static imports keep the modules discoverable by the Nuitka onefile build.
    """
    from pandaplot.services.help.content import (
        analysis,
        descriptive,
        fitting,
        measurements,
        panels,
        preprocessing,
        signal,
        statistics,
        transforms,
    )

    return (panels, statistics, descriptive, preprocessing, analysis, signal, fitting, transforms, measurements)


def build_help_catalog() -> HelpCatalog:
    """Assemble the catalog from all content modules.

    Returns:
        A catalog holding every module's topics, in ``CONTENT_MODULES`` order.
    """
    topics: list[HelpTopic] = []
    for module in _content_modules():
        topics.extend(module.topics())
    return HelpCatalog(topics)


@cache
def get_help_catalog() -> HelpCatalog:
    """Return the shared, lazily built help catalog."""
    return build_help_catalog()
