"""Tests for the pure help topic HTML renderer."""

from pandaplot.gui.dialogs.help.help_html import render_help_topic_html
from pandaplot.services.help.help_types import HelpCategory, HelpTopic

_PALETTE = {"base_fg": "#111111", "secondary_fg": "#666666", "accent": "#0055aa", "card_bg": "#ffffff", "card_border": "#eeeeee"}


def _topic(**overrides) -> HelpTopic:
    fields = {"id": "t.one", "title": "One", "category": HelpCategory.STATISTICS, "summary": "A summary."}
    fields.update(overrides)
    return HelpTopic(**fields)


def _render(topic: HelpTopic, titles: dict[str, str] | None = None) -> str:
    titles = titles or {}
    return render_help_topic_html(topic, _PALETTE, titles.get)


def test_all_text_is_escaped():
    topic = _topic(
        title="<b>Title</b>",
        summary="x < y & z",
        steps=("click <Run>",),
        explanation="<script>alert(1)</script>",
        assumptions="a > b",
        parameters=(("<lbl>", "m&m"),),
        formula="a < b",
        example="<i>e</i>",
    )

    result = _render(topic)

    assert "<script>" not in result
    assert "<b>Title</b>" not in result
    assert "&lt;b&gt;Title&lt;/b&gt;" in result
    assert "x &lt; y &amp; z" in result
    assert "click &lt;Run&gt;" in result
    assert "&lt;lbl&gt;" in result
    assert "m&amp;m" in result
    assert "a &lt; b" in result


def test_empty_sections_are_omitted():
    result = _render(_topic())

    for heading in ("How to use", "What it does", "Assumptions", "Parameters", "Formula", "Example", "Related topics"):
        assert heading not in result
    assert "A summary." in result


def test_populated_sections_are_rendered_in_order():
    topic = _topic(
        steps=("first", "second"),
        explanation="Because.",
        assumptions="Normal data.",
        parameters=(("Alpha", "Significance level"),),
        formula="t = x",
        example="Try it.",
        related=("t.two",),
    )

    result = _render(topic, {"t.two": "Two"})

    headings = ["How to use", "What it does", "Assumptions", "Parameters", "Formula", "Example", "Related topics"]
    positions = [result.index(h) for h in headings]
    assert positions == sorted(positions)
    assert "<ol" in result
    assert result.index("first") < result.index("second")
    assert "Alpha" in result
    assert "Significance level" in result


def test_prose_paragraphs_and_line_breaks():
    result = _render(_topic(explanation="para one\nline two\n\npara two"))

    assert "<p>para one<br>line two</p>" in result
    assert "<p>para two</p>" in result


def test_formula_keeps_every_line_break():
    result = _render(_topic(formula="line1\nline2\n\nline4"))

    assert "line1<br>line2<br><br>line4" in result
    assert "monospace" in result


def test_related_link_uses_help_scheme_and_title():
    result = _render(_topic(related=("stats.other",)), {"stats.other": "Other <test>"})

    assert 'href="help:stats.other"' in result
    assert "Other &lt;test&gt;" in result


def test_unresolved_related_ids_are_dropped():
    result = _render(_topic(related=("missing.id",)))

    assert "missing.id" not in result
    assert "Related topics" not in result


def test_unresolved_related_dropped_while_resolved_kept():
    result = _render(_topic(related=("missing.id", "t.two")), {"t.two": "Two"})

    assert "missing.id" not in result
    assert 'href="help:t.two"' in result


def test_missing_palette_keys_fall_back_to_defaults():
    result = render_help_topic_html(_topic(formula="x"), {}, lambda _id: None)

    assert "#333333" in result
