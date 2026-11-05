"""Tests for the shared item-type label prefixes."""
import pytest

from pandaplot.utils.item_labels import ITEM_TYPE_PREFIXES, item_label, strip_item_prefix


@pytest.mark.parametrize("item_type", sorted(ITEM_TYPE_PREFIXES))
def test_strip_reverses_label_for_every_type(item_type):
    assert strip_item_prefix(item_label(item_type, "My Item")) == "My Item"


def test_unknown_type_gets_the_default_prefix():
    assert item_label("unknown", "Thing") == "📄 Thing"


def test_multi_character_prefixes_are_stripped_whole():
    assert strip_item_prefix("🖼️ Album") == "Album"
    assert strip_item_prefix("✏️ Diagram") == "Diagram"


def test_text_without_a_prefix_is_only_trimmed():
    assert strip_item_prefix("  Plain name ") == "Plain name"


def test_a_prefix_without_its_space_is_part_of_the_name():
    assert strip_item_prefix("📝Notes") == "📝Notes"
