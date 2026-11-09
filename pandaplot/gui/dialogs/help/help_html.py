"""HTML rendering of help topics for the Help window."""

import html
from collections.abc import Callable, Mapping

from pandaplot.services.help.help_types import HelpTopic

HELP_LINK_SCHEME = "help"


def _prose(text: str) -> str:
    """Render plain text as escaped paragraphs; single newlines become line breaks.

    Args:
        text: Plain text where a blank line separates paragraphs.

    Returns:
        HTML paragraphs, or an empty string when the text is blank.
    """
    if not text.strip():
        return ""
    paragraphs = [p for p in text.strip().split("\n\n") if p.strip()]
    return "".join("<p>" + html.escape(p.strip()).replace("\n", "<br>") + "</p>" for p in paragraphs)


def render_help_topic_html(topic: HelpTopic, palette: Mapping[str, str], title_for: Callable[[str], str | None]) -> str:
    """Render a help topic as themed, escaped HTML.

    Sections (summary, How to use, What it does, Assumptions, Parameters, Formula,
    Example, Related topics) are omitted when empty. Related ids for which
    ``title_for`` returns ``None`` are dropped.

    Args:
        topic: The topic to render.
        palette: Surface palette (``base_fg``, ``secondary_fg``, ``accent``, ``card_bg``, ``card_border``).
        title_for: Maps a topic id to its title, or ``None`` when the id is unknown.

    Returns:
        An HTML document body for a ``QTextBrowser``.
    """
    base_fg = palette.get("base_fg", "#333333")
    secondary_fg = palette.get("secondary_fg", "#666666")
    accent = palette.get("accent", "#4A90E2")
    card_bg = palette.get("card_bg", "#ffffff")
    code_bg = palette.get("card_border", "#eef1f4")

    def heading(text: str) -> str:
        return f"<h3 style='color:{accent};'>{html.escape(text)}</h3>"

    sections = [
        f"<h2 style='color:{base_fg};margin:0 0 4px 0;'>{html.escape(topic.title)}</h2>",
        f"<div style='color:{base_fg};'>{_prose(topic.summary)}</div>",
    ]

    if topic.steps:
        items = "".join(f"<li>{html.escape(step).replace(chr(10), '<br>')}</li>" for step in topic.steps)
        sections.append(heading("How to use"))
        sections.append(f"<ol style='color:{base_fg};'>{items}</ol>")

    if topic.explanation.strip():
        sections.append(heading("What it does"))
        sections.append(f"<div style='color:{base_fg};'>{_prose(topic.explanation)}</div>")

    if topic.assumptions.strip():
        sections.append(heading("Assumptions"))
        sections.append(f"<div style='color:{secondary_fg};'>{_prose(topic.assumptions)}</div>")

    if topic.parameters:
        rows = "".join(
            f"<tr><td style='color:{base_fg};padding-right:12px;'><b>{html.escape(label)}</b></td>"
            f"<td style='color:{base_fg};'>{html.escape(meaning)}</td></tr>"
            for label, meaning in topic.parameters
        )
        sections.append(heading("Parameters"))
        sections.append(f"<table cellspacing='0' cellpadding='3'>{rows}</table>")

    if topic.formula.strip():
        formula_html = html.escape(topic.formula).replace("\n", "<br>")
        sections.append(heading("Formula"))
        sections.append(
            f"<div style='background-color:{code_bg};color:{base_fg};padding:10px;white-space:pre-wrap;"
            f"font-family:Menlo,Consolas,monospace;font-size:10pt;'>{formula_html}</div>"
        )

    if topic.example.strip():
        sections.append(heading("Example"))
        sections.append(f"<div style='color:{base_fg};'>{_prose(topic.example)}</div>")

    links = []
    for related_id in topic.related:
        related_title = title_for(related_id)
        if related_title is None:
            continue
        href = html.escape(f"{HELP_LINK_SCHEME}:{related_id}", quote=True)
        links.append(f"<li><a href=\"{href}\" style='color:{accent};'>{html.escape(related_title)}</a></li>")
    if links:
        sections.append(heading("Related topics"))
        sections.append(f"<ul>{''.join(links)}</ul>")

    return f"<body style='background-color:{card_bg};line-height:1.4;'>{''.join(sections)}</body>"
