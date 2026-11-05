"""Emoji prefixes that mark each item type in project-tree labels and tab titles.

A label is "<prefix> <name>". Some prefixes are more than one character
(an emoji plus a variation selector, e.g. "🖼️"), so code that strips a
prefix must use `strip_item_prefix()` rather than slicing a fixed length.
"""

ITEM_TYPE_PREFIXES: dict[str, str] = {
    "project": "📁",
    "folder": "📁",
    "collection": "📁",
    "note": "📝",
    "dataset": "📊",
    "chart": "📈",
    "imagegallery": "🖼️",
    "image": "🎞️",
    "sketch": "✏️",
}

DEFAULT_ITEM_PREFIX = "📄"

# Longest first, so a prefix that starts with another one is matched whole.
_PREFIXES_LONGEST_FIRST = sorted({*ITEM_TYPE_PREFIXES.values(), DEFAULT_ITEM_PREFIX}, key=len, reverse=True)


def item_label(item_type: str, name: str) -> str:
    """The label for an item of `item_type` named `name`."""
    return f"{ITEM_TYPE_PREFIXES.get(item_type, DEFAULT_ITEM_PREFIX)} {name}"


def strip_item_prefix(label: str) -> str:
    """The item name in `label`, without its type prefix if it has one."""
    for prefix in _PREFIXES_LONGEST_FIRST:
        if label.startswith(f"{prefix} "):
            return label[len(prefix) + 1:].strip()
    return label.strip()
