"""Normalisation of upstream SVG documents."""

import re

_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_ROOT_TAG = re.compile(r"<svg\b[^>]*>")
_ROOT_SIZE = re.compile(r'\s(?:width|height)="[^"]*"')


def sanitize_svg(raw: bytes, *, label: str) -> str:
    """Normalise an upstream SVG so it can be tinted and embedded.

    Strips comments and the root ``width``/``height``, and adds ``fill="currentColor"`` when the root
    sets neither ``fill`` nor ``stroke``.

    Raises:
        ValueError: If the document is not an SVG or contains no ``currentColor`` (it could not be tinted).
    """
    text = _COMMENT.sub("", raw.decode("utf-8")).strip()
    match = _ROOT_TAG.match(text)
    if match is None:
        raise ValueError(f"{label} is not an SVG document")
    root = _ROOT_SIZE.sub("", match.group(0))
    if "fill=" not in root and "stroke=" not in root:
        root = root.replace("<svg", '<svg fill="currentColor"', 1)
    svg = root + text[match.end():]
    if "currentColor" not in svg:
        raise ValueError(f"{label} has no currentColor, so it cannot be tinted by the theme")
    return svg
