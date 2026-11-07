"""Content model for the in-app Help section.

Stdlib only, so panels can import topic ids without pulling in the catalog,
the content modules or any analysis library at startup.
"""

import re
from dataclasses import dataclass
from enum import Enum


class HelpCategory(Enum):
    """Help topic categories; display order is definition order."""

    PANELS = "Using the panels"
    STATISTICS = "Statistical tests"
    DESCRIPTIVE = "Descriptive statistics"
    PREPROCESSING = "Preprocessing"
    ANALYSIS = "Analysis operations"
    SIGNAL = "Signal analysis"
    FITTING = "Curve fitting"
    TRANSFORMS = "Transforms and formulas"
    MEASUREMENTS = "Measurement analysis"


@dataclass(frozen=True)
class HelpTopic:
    """One help topic.

    Attributes:
        id: Stable dotted identifier, e.g. ``stats.one_sample_t``.
        title: Display title.
        category: Category the topic is listed under.
        summary: One or two sentences, shown first and used in search.
        steps: Numbered how-to instructions.
        explanation: Fuller plain-language text; a blank line separates paragraphs.
        assumptions: When the method is valid (statistical tests).
        parameters: Pairs of (UI label, meaning).
        formula: Formula text; line breaks are kept.
        example: Worked example text.
        keywords: Extra search terms (synonyms, abbreviations).
        related: Ids of related topics.
    """

    id: str
    title: str
    category: HelpCategory
    summary: str
    steps: tuple[str, ...] = ()
    explanation: str = ""
    assumptions: str = ""
    parameters: tuple[tuple[str, str], ...] = ()
    formula: str = ""
    example: str = ""
    keywords: tuple[str, ...] = ()
    related: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate required fields.

        Raises:
            ValueError: If id, title or summary is empty, or id contains whitespace.
        """
        if not self.id:
            raise ValueError("HelpTopic id must not be empty")
        if any(ch.isspace() for ch in self.id):
            raise ValueError(f"HelpTopic id must not contain whitespace: {self.id!r}")
        if not self.title.strip():
            raise ValueError(f"HelpTopic {self.id!r} must have a title")
        if not self.summary.strip():
            raise ValueError(f"HelpTopic {self.id!r} must have a summary")


PANEL_TOPIC_TRANSFORM = "panel.transform"
PANEL_TOPIC_PREPROCESSING = "panel.preprocessing"
PANEL_TOPIC_ANALYSIS = "panel.analysis"
PANEL_TOPIC_DESCRIPTIVE = "panel.descriptive"
PANEL_TOPIC_STATISTICS = "panel.statistics"
PANEL_TOPIC_SIGNAL = "panel.signal"
PANEL_TOPIC_FIT = "panel.fit"
PANEL_TOPIC_CHART_ANALYSIS = "panel.chart_analysis"
PANEL_TOPIC_CHART_SIGNAL = "panel.chart_signal"
PANEL_TOPIC_CHART_TRANSFORM = "panel.chart_transform"

PANEL_TOPIC_IDS: tuple[str, ...] = (
    PANEL_TOPIC_TRANSFORM,
    PANEL_TOPIC_PREPROCESSING,
    PANEL_TOPIC_ANALYSIS,
    PANEL_TOPIC_DESCRIPTIVE,
    PANEL_TOPIC_STATISTICS,
    PANEL_TOPIC_SIGNAL,
    PANEL_TOPIC_FIT,
    PANEL_TOPIC_CHART_ANALYSIS,
    PANEL_TOPIC_CHART_SIGNAL,
    PANEL_TOPIC_CHART_TRANSFORM,
)

FIT_TOPIC_OVERVIEW = "fit.overview"
FIT_TOPIC_CUSTOM = "fit.custom"


def fit_topic_id(model_name: str) -> str:
    """Build the help topic id for a fit model.

    Args:
        model_name: The model name as used in ``FIT_DEFINITIONS``.

    Returns:
        The id, e.g. ``fit.exponential_growth_to_maximum``.
    """
    return "fit." + re.sub(r"[^a-z0-9]+", "_", model_name.lower()).strip("_")
