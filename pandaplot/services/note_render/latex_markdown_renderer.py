"""Render note source (Markdown + LaTeX math) into self-contained HTML.

Math delimited by ``$...$`` (inline) and ``$$...$$`` (display) is rendered to
PNG images via matplotlib's ``mathtext`` engine -- a LaTeX-math subset that
covers the notation typical of scientific notes (fractions, integrals, sums,
Greek letters, matrices, sub/superscripts, symbols). Each equation is embedded
as a base64 ``data:`` URI, so the resulting HTML is fully offline and portable
into both the Qt preview (``QTextBrowser``) and the PDF export
(``QTextDocument``).

This module is intentionally free of any Qt dependency so it can be unit
tested and reused headlessly.
"""

import base64
import io
import logging
import re
import struct
from dataclasses import dataclass

from markdown import markdown

logger = logging.getLogger(__name__)

# Render at a multiple of the display resolution so equations stay crisp on
# high-DPI screens; the <img> is then scaled back down by the same factor.
# 4x covers up to 400% OS display scaling before the PNG itself becomes the
# resolution bottleneck; equations are tiny so the extra pixels cost little.
_RENDER_SCALE = 16
_BASE_DPI = 100

# Placeholders swapped in for math while Markdown runs, so Markdown never sees
# (and never mangles) the LaTeX source. Pure alphanumerics survive Markdown
# untouched. \x00 guards escaped dollar signs.
_ESCAPED_DOLLAR = "\x00"
_MATH_TOKEN = "zzmathplaceholder{index}zz"
_MATH_TOKEN_RE = re.compile(r"zzmathplaceholder(\d+)zz")

_DISPLAY_MATH_RE = re.compile(r"\$\$(.+?)\$\$", re.DOTALL)
_INLINE_MATH_RE = re.compile(r"\$(.+?)\$", re.DOTALL)

# Cache rendered equations for the session; keyed on everything that affects
# the pixels. data: URIs are large but bounded by the number of distinct
# equations edited in a session.
_equation_cache: dict[tuple, "RenderedEquation"] = {}


@dataclass(frozen=True)
class RenderedEquation:
    """A single equation rendered to an embeddable image."""

    data_uri: str
    width: int
    height: int
    valign: float  # baseline offset in display px (negative sinks below baseline)
    ok: bool
    latex: str


def _png_dimensions(data: bytes) -> tuple[int, int]:
    """Read (width, height) from a PNG byte string's IHDR chunk."""
    width, height = struct.unpack(">II", data[16:24])
    return int(width), int(height)


def render_equation(latex: str, *, color: str, fontsize: float, display: bool) -> RenderedEquation:
    """Render a single LaTeX-math string to a base64 PNG data URI.

    On a parse error, returns a ``RenderedEquation`` with ``ok=False`` and an
    empty ``data_uri`` so the caller can fall back to showing the raw source
    instead of crashing the whole preview.
    """
    key = (latex, color, round(fontsize, 2), display)
    cached = _equation_cache.get(key)
    if cached is not None:
        return cached

    # Import lazily: matplotlib is heavy and not every session touches notes.
    from matplotlib import figure
    from matplotlib.font_manager import FontProperties
    from matplotlib.mathtext import MathTextParser

    # Display equations render a touch larger, matching common note styling.
    effective_size = fontsize * (1.3 if display else 1.0)
    buf = io.BytesIO()
    try:
        # Reimplements matplotlib.mathtext.math_to_image, but saves with a
        # transparent background instead of the opaque white figure facecolor
        # -- otherwise every equation shows as a white box in a dark theme.
        prop = FontProperties(size=effective_size)
        expr = f"${latex.strip()}$"
        parser = MathTextParser("path")
        width, height, depth, _, _ = parser.parse(expr, dpi=72, prop=prop)

        fig = figure.Figure(figsize=(width / 72.0, height / 72.0))
        fig.text(0, depth / height, expr, fontproperties=prop, color=color)
        fig.savefig(
            buf,
            dpi=_BASE_DPI * _RENDER_SCALE,
            format="png",
            transparent=True,
        )
    except Exception as exc:  # invalid syntax, unknown symbol, etc.
        logger.debug("mathtext failed to render %r: %s", latex, exc)
        result = RenderedEquation("", 0, 0, 0.0, ok=False, latex=latex)
        _equation_cache[key] = result
        return result

    data = buf.getvalue()
    px_w, px_h = _png_dimensions(data)
    data_uri = "data:image/png;base64," + base64.b64encode(data).decode("ascii")
    result = RenderedEquation(
        data_uri=data_uri,
        width=round(px_w / _RENDER_SCALE),
        height=round(px_h / _RENDER_SCALE),
        valign=-(float(depth) / _RENDER_SCALE),
        ok=True,
        latex=latex,
    )
    _equation_cache[key] = result
    return result


def _equation_img(latex: str, *, color: str, fontsize: float, display: bool) -> str:
    """Build the HTML fragment for one equation (image, or error fallback)."""
    eq = render_equation(latex, color=color, fontsize=fontsize, display=display)
    if not eq.ok:
        # Show the offending source so the user can fix it, rather than a blank.
        safe = _escape_html(latex)
        return f'<code class="math-error" style="color:#dc3545;">${safe}$</code>'

    if display:
        return (
            f'<img class="math-display" src="{eq.data_uri}" '
            f'width="{eq.width}" height="{eq.height}" alt="{_escape_html(latex)}" '
            f'style="display:block;margin:8px auto;">'
        )
    return (
        f'<img class="math-inline" src="{eq.data_uri}" '
        f'width="{eq.width}" height="{eq.height}" alt="{_escape_html(latex)}" '
        f'style="vertical-align:{eq.valign:.1f}px;">'
    )


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_body_html(source: str, *, color: str = "#000000", fontsize: float = 11.0) -> str:
    """Render note ``source`` (Markdown + LaTeX) to an HTML body fragment.

    ``color`` and ``fontsize`` control how the equation images are rasterised
    so the math visually matches the surrounding text.
    """
    # 1. Protect escaped dollars so they are never treated as math delimiters.
    text = source.replace(r"\$", _ESCAPED_DOLLAR)

    equations: list[str] = []
    display_flags: list[bool] = []

    def _stash(latex: str, *, display: bool) -> str:
        equations.append(latex)
        display_flags.append(display)
        return _MATH_TOKEN.format(index=len(equations) - 1)

    # 2. Extract display math first (so $$ is never split by the inline $ pass),
    #    then inline math. Each becomes an inert alphanumeric placeholder token
    #    that Markdown passes through untouched.
    text = _DISPLAY_MATH_RE.sub(lambda m: _stash(m.group(1), display=True), text)
    text = _INLINE_MATH_RE.sub(lambda m: _stash(m.group(1), display=False), text)

    # 3. Run Markdown on the now math-free text.
    html = markdown(text, extensions=["tables", "fenced_code"])

    # 4. Swap placeholders back out for rendered equation images.
    def _restore(match: re.Match) -> str:
        idx = int(match.group(1))
        return _equation_img(
            equations[idx], color=color, fontsize=fontsize, display=display_flags[idx]
        )

    html = _MATH_TOKEN_RE.sub(_restore, html)

    # 5. Restore any literal (escaped) dollar signs.
    html = html.replace(_ESCAPED_DOLLAR, "$")
    return html


def wrap_document(
    body_html: str,
    *,
    color: str = "#000000",
    background: str = "#ffffff",
    border: str = "#dddddd",
    fontsize: float = 11.0,
) -> str:
    """Wrap a rendered body fragment in a styled, self-contained HTML document.

    Used for both the live preview (theme colours) and PDF export (print
    colours). Styling is kept inline and simple because it is consumed by Qt's
    limited HTML rendering (``QTextBrowser`` / ``QTextDocument``), not a full
    browser.
    """
    return f"""<html><head><style>
body {{ color: {color}; background-color: {background};
       font-family: 'Segoe UI', Arial, sans-serif; font-size: {fontsize}pt;
       line-height: 1.5; }}
h1, h2, h3, h4 {{ color: {color}; }}
a {{ color: #4A90E2; }}
code, pre {{ background-color: rgba(128,128,128,0.15); border-radius: 4px;
            font-family: 'Consolas', 'Courier New', monospace; }}
pre {{ padding: 8px; }}
code {{ padding: 1px 4px; }}
table {{ border-collapse: collapse; }}
th, td {{ border: 1px solid {border}; padding: 4px 8px; }}
blockquote {{ border-left: 3px solid {border}; margin-left: 0;
             padding-left: 12px; color: {color}; }}
</style></head><body>{body_html}</body></html>"""
