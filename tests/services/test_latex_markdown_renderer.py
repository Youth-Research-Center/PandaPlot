"""Tests for the note LaTeX + Markdown renderer.

Covers the extract/render/restore pipeline: inline vs display math, error
fallback for invalid LaTeX, protection of escaped dollars, and that Markdown
structure survives around embedded math.
"""

from pandaplot.services.note_render.latex_markdown_renderer import (
    is_escaped_at,
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


def test_image_size_modifier_applies_width_and_height():
    html = render_body_html("![Chart](chart.png =300x200)")
    assert 'src="chart.png"' in html
    assert 'width="300"' in html
    assert 'height="200"' in html
    assert "pandaimgsize" not in html


def test_image_size_modifier_width_only():
    html = render_body_html("![Chart](chart.png =300x)")
    assert 'width="300"' in html
    assert "height=" not in html


def test_image_size_modifier_height_only():
    html = render_body_html("![Chart](chart.png =x200)")
    assert 'height="200"' in html
    assert "width=" not in html


def test_image_without_size_modifier_is_unaffected():
    html = render_body_html("![Chart](chart.png)")
    assert 'src="chart.png"' in html
    assert "width=" not in html
    assert "height=" not in html


def test_image_size_modifier_supports_angle_bracket_target():
    """The angle-bracket target form is required Markdown syntax for a
    gallery path containing spaces, and must work together with sizing."""
    html = render_body_html("![Chart](<Gallery 1/sample.png> =300x200)")
    assert 'src="Gallery 1/sample.png"' in html
    assert 'width="300"' in html
    assert 'height="200"' in html
    assert "pandaimgsize" not in html


def test_image_size_modifier_ignored_inside_code_span():
    """Image-shaped text inside inline/fenced code is literal code, not a
    live image link -- the internal size-fragment marker must never leak
    into the rendered code."""
    html = render_body_html("Use `![Chart](img-id =300x200)` syntax.")
    assert "pandaimgsize" not in html
    assert "<code>![Chart](img-id =300x200)</code>" in html

    html = render_body_html("```\n![Chart](img-id =300x200)\n```")
    assert "pandaimgsize" not in html
    assert "<pre>" in html


def test_image_size_modifier_ignored_when_escaped():
    html = render_body_html(r"\![Chart](img-id =300x200)")
    assert "pandaimgsize" not in html


def test_code_placeholder_does_not_collide_with_literal_note_text():
    """The code-region placeholder token is randomized per render call, so a
    note that happens to contain literal text shaped like the placeholder
    isn't corrupted by `restore_code_regions` mistaking it for a real one."""
    html = render_body_html("zzcodeplaceholder-deadbeef-0zz and `real code`")
    assert "zzcodeplaceholder-deadbeef-0zz" in html
    assert "<code>real code</code>" in html


def test_is_escaped_at_respects_backslash_parity():
    # "\!" -- odd run of one backslash -- escapes the "!".
    assert is_escaped_at(r"\!", 1) is True
    # "\\!" -- even run of two backslashes -- is a literal backslash
    # followed by a live, unescaped "!".
    assert is_escaped_at(r"\\!", 2) is False
    # "\\\!" -- odd run of three -- escapes it again.
    assert is_escaped_at(r"\\\!", 3) is True
    assert is_escaped_at("!", 0) is False


def test_image_size_modifier_applies_despite_even_escaped_backslash():
    """"\\\\!" is a literal backslash followed by a live image -- the size
    modifier must still apply, not be skipped as if the "!" were escaped."""
    html = render_body_html(r"\\![Chart](img-id =300x200)")
    assert 'width="300"' in html
    assert 'height="200"' in html


def test_fenced_code_backreference_handles_nested_triple_backtick():
    """A longer fence (four backticks) whose content contains an unrelated,
    shorter run of the same character (a literal ```) must not close the
    protected region early -- only a fence of the same length does."""
    html = render_body_html("````\ntext with ``` inside\n![Chart](img-id =300x200)\n````")
    assert "pandaimgsize" not in html
    assert "<pre>" in html
    assert "text with ``` inside" in html


def test_tilde_fence_is_protected_like_backtick_fence():
    html = render_body_html("~~~\n![Chart](img-id =300x200)\n~~~")
    assert "pandaimgsize" not in html
    assert "<pre>" in html


def test_wrap_document_applies_colors():
    doc = wrap_document("<p>hi</p>", color="#123456", background="#abcdef")
    assert "#123456" in doc
    assert "#abcdef" in doc
    assert "<body>" in doc and "hi" in doc


def test_wrap_document_sets_tight_paragraph_margin():
    """Qt's QTextDocument doesn't collapse adjacent block margins like a
    browser does, so relying on its ~12px default <p> margin makes the gap
    between two consecutive paragraphs (e.g. an image on its own line
    followed by a blank line) look roughly double a normal line gap. Pin an
    explicit, smaller margin instead."""
    doc = wrap_document("<p>hi</p>")
    assert "p {" in doc
    assert "margin: 4px 0;" in doc


def test_wrap_document_uses_fixed_unit_line_height_not_a_multiplier():
    """A unitless (or percentage) line-height is a *multiplier* of each
    line's own natural height -- fine for a text line, but Qt applies the
    same multiplier to a paragraph containing only an image, whose "line" is
    the image's full pixel height. That inflates the gap below a large image
    far beyond normal paragraph spacing (Qt adds the extra space below the
    line, not split around it), producing a much bigger gap after an image
    than before it. A fixed absolute line-height sets every line's height to
    the same constant regardless of content, avoiding the inflation."""
    doc = wrap_document("<p>hi</p>", fontsize=11.0)
    assert "line-height: 16.5pt;" in doc
    assert "line-height: 1.5;" not in doc
    assert "line-height: 150%;" not in doc


def test_image_paragraph_gap_matches_text_paragraph_gap(qapp):
    """End-to-end regression for the line-height/image interaction above:
    the gap around an image paragraph must match the gap between two plain
    text paragraphs, not balloon after it."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QImage
    from PySide6.QtGui import QTextDocument as QtTextDocument
    from PySide6.QtWidgets import QTextEdit

    qimg = QImage(80, 80, QImage.Format.Format_RGB32)
    qimg.fill(0xFF0000)

    source = "Before text.\n\n![Chart](img-id =80x80)\n\nAfter text."
    body = render_body_html(source)
    html = wrap_document(body)

    edit = QTextEdit()
    doc = edit.document()
    doc.addResource(QtTextDocument.ResourceType.ImageResource, QUrl("img-id"), qimg)
    edit.setHtml(html)
    edit.resize(400, 400)
    doc.setTextWidth(400)
    layout_doc = doc.documentLayout()

    rects = []
    block = doc.begin()
    while block.isValid():
        r = layout_doc.blockBoundingRect(block)
        rects.append((r.top(), r.bottom()))
        block = block.next()

    gap_before_image = rects[1][0] - rects[0][1]
    gap_after_image = rects[2][0] - rects[1][1]
    assert gap_after_image == gap_before_image
