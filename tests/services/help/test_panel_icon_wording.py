"""Help text names the sidebar icons in words, not with the old emoji."""
import re

import pytest

from pandaplot.services.help.content import panels, transforms
from pandaplot.services.help.help_catalog import build_help_catalog
from pandaplot.services.help.help_types import PANEL_TOPIC_CHART_PROPERTIES, HelpTopic

_SIDEBAR_EMOJI_ICON = re.compile("(🔧|⚖️|📊|📋|🧪|📡|📈|📐|🧮) icon")


def _text(topic: HelpTopic) -> str:
    return "\n".join((topic.title, topic.summary, *topic.steps, topic.explanation))


@pytest.mark.parametrize("topic", [*panels.topics(), *transforms.topics()], ids=lambda topic: topic.id)
def test_hand_written_panel_and_transform_topics_have_no_emoji_icon(topic: HelpTopic) -> None:
    assert _SIDEBAR_EMOJI_ICON.search(_text(topic)) is None


def test_no_topic_in_the_full_catalog_has_an_emoji_icon() -> None:
    """No topic in the assembled help catalog refers to a sidebar icon by its old emoji."""
    for topic in build_help_catalog().topics():
        assert _SIDEBAR_EMOJI_ICON.search(_text(topic)) is None, topic.id


def test_chart_properties_topic_describes_apply_and_undo_correctly() -> None:
    topic = next(t for t in panels.topics() if t.id == PANEL_TOPIC_CHART_PROPERTIES)
    text = _text(topic)

    assert "Apply" in text
    assert "undo" in text.lower()
    assert "only take effect" not in text
    assert "until you click Apply" not in text


_OLD_BUTTON_AND_PANEL_NAMES = ("📐 Curve Fitting", "♻️ Refresh", "🔍 Reset Zoom", "⇄ Swap X/Y", "🔄 Reset", "📎 Artefacts", "ℹ️ button", "📊 Insert Chart...")


def test_no_topic_names_a_button_or_panel_with_its_old_emoji() -> None:
    """Panels and toolbar buttons are named by their text; their icons are bundled SVGs, not emoji."""
    for topic in build_help_catalog().topics():
        text = _text(topic)
        for old_name in _OLD_BUTTON_AND_PANEL_NAMES:
            assert old_name not in text, f"{topic.id} still says {old_name!r}"


_OLD_GLYPH_BUTTON_NAMES = ("▾", "▸", "▲", "▼", "↺", "↻")


def test_no_topic_names_a_button_by_its_old_glyph() -> None:
    """Icon buttons are described in words: the glyphs they used to show are not quoted in the help."""
    for topic in build_help_catalog().topics():
        text = _text(topic)
        for glyph in _OLD_GLYPH_BUTTON_NAMES:
            assert glyph not in text, f"{topic.id} still quotes {glyph!r}"
