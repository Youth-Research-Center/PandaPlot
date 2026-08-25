"""Tests for the note LaTeX + Markdown renderer.

Covers the extract/render/restore pipeline: inline vs display math, error
fallback for invalid LaTeX, protection of escaped dollars, and that Markdown
structure survives around embedded math.
"""

from pandaplot.services.note_render.latex_markdown_renderer import (
    render_body_html,
    render_equation,
    wrap_document,
)


def test_inline_math_becomes_image():
    html = render_body_html(r"Energy $E = mc^2$ here.")
    assert 'class="math-inline"' in html
    assert "data:image/png;base64," in html
    # surrounding prose is preserved
    assert "Energy" in html and "here." in html


def test_display_math_is_block_centered():
    html = render_body_html(r"$$\int_0^1 x\,dx = \frac{1}{2}$$")
    assert 'class="math-display"' in html
    assert "display:block" in html


def test_invalid_math_falls_back_without_crashing():
    html = render_body_html(r"broken $\frac{$ math")
    assert 'class="math-error"' in html
    # raw source is shown so the user can fix it
    assert r"\frac{" in html


def test_escaped_dollar_is_literal_not_math():
    html = render_body_html(r"Price is \$5 and \$10.")
    assert "$5" in html
    assert "$10" in html
    assert "math-inline" not in html


def test_markdown_still_renders_around_math():
    html = render_body_html("# Heading\n\n| a | b |\n|---|---|\n| 1 | 2 |")
    assert "<h1" in html
    assert "<table>" in html


def test_multiple_equations_are_independent():
    html = render_body_html(r"$a$ and $b$ then $$c^2$$")
    assert html.count("math-inline") == 2
    assert html.count("math-display") == 1


def test_render_equation_caches_result():
    first = render_equation(r"x^2", color="#000000", fontsize=11, display=False)
    second = render_equation(r"x^2", color="#000000", fontsize=11, display=False)
    assert first is second  # returned from cache
    assert first.ok
    assert first.width > 0 and first.height > 0


def test_render_equation_error_flag():
    result = render_equation(r"\frac{", color="#000000", fontsize=11, display=False)
    assert result.ok is False
    assert result.data_uri == ""


def test_render_equation_has_transparent_background():
    """Equations must not carry an opaque background, or they show as a
    white box when embedded in a dark-themed note (issue #163)."""
    import base64
    import io

    from PIL import Image

    result = render_equation(r"x^2", color="#ffffff", fontsize=11, display=False)
    data = base64.b64decode(result.data_uri.split(",", 1)[1])
    image = Image.open(io.BytesIO(data))
    assert image.mode == "RGBA"
    alpha = image.getchannel("A")
    # The corners (outside the glyph strokes) should be fully transparent.
    assert alpha.getpixel((0, 0)) == 0
    assert alpha.getpixel((image.width - 1, 0)) == 0


def test_wrap_document_applies_colors():
    doc = wrap_document("<p>hi</p>", color="#123456", background="#abcdef")
    assert "#123456" in doc
    assert "#abcdef" in doc
    assert "<body>" in doc and "hi" in doc
