"""Tests for icon_bundle.svg."""

import pytest
from icon_bundle.svg import sanitize_svg

from tests.scripts.icons.conftest import MOUNTAIN_SVG


def test_sanitize_svg_strips_comments_and_root_size_and_adds_current_color():
    raw = b'<svg xmlns="x" width="256" height="256" viewBox="0 0 256 256"><!-- c --><path d="M0 0"/></svg>'

    svg = sanitize_svg(raw, label="folder")

    assert "<!--" not in svg
    assert 'width="256"' not in svg
    assert 'fill="currentColor"' in svg
    assert 'viewBox="0 0 256 256"' in svg


def test_sanitize_svg_keeps_stroke_icons_untouched():
    svg = sanitize_svg(MOUNTAIN_SVG.encode(), label="mountain")

    assert 'stroke="currentColor"' in svg
    assert svg.count("currentColor") == 1


def test_sanitize_svg_rejects_non_svg():
    with pytest.raises(ValueError, match="not an SVG"):
        sanitize_svg(b"<html></html>", label="folder")


def test_sanitize_svg_rejects_icons_that_cannot_be_tinted():
    with pytest.raises(ValueError, match="currentColor"):
        sanitize_svg(b'<svg viewBox="0 0 1 1" fill="#000000"><path d="M0 0"/></svg>', label="folder")
