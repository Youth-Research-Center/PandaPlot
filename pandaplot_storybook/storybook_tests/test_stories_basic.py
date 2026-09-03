import pytest

import pandaplot_storybook.stories  # noqa: F401  (registers all stories)
from pandaplot_storybook.registry import all_story_names, get_story

EXPECTED_STORY_NAMES = [
    "PButton",
    "ToggleSwitch",
    "SegmentedControl",
    "ChipRow",
    "Card",
    "ColorSwatchRow",
    "DirtyFooter",
    "DropDownComboBox",
    "SectionHeader",
    "SliderWithSpinbox",
    "ValueComboBox",
    "LineStyleIcons",
    "FontFamilyOptions",
    "ImageGalleryTile",
    "BusySpinner",
]


def test_every_expected_story_is_registered():
    """Guards against a story module existing but never being imported from
    `stories/__init__.py` (in which case it wouldn't be in the registry at
    all, and the parametrized test below would silently skip it)."""
    assert set(all_story_names()) == set(EXPECTED_STORY_NAMES)


@pytest.mark.parametrize("name", [n for n in EXPECTED_STORY_NAMES if n not in ("LineStyleIcons", "FontFamilyOptions")])
def test_story_builds_a_widget(qtbot, name):
    story_def = get_story(name)
    values = {control.name: control.default for control in story_def.controls}
    widget = story_def.make_widget(values, tokens={})
    assert widget is not None
    qtbot.addWidget(widget)


def test_line_style_icons_story_builds_a_widget_with_no_controls(qtbot):
    story_def = get_story("LineStyleIcons")
    assert story_def.controls == []
    widget = story_def.make_widget({}, tokens={})
    assert widget is not None
    assert widget.count() > 0
    qtbot.addWidget(widget)


def test_font_family_options_story_builds_a_widget_with_no_controls(qtbot):
    story_def = get_story("FontFamilyOptions")
    assert story_def.controls == []
    widget = story_def.make_widget({}, tokens={})
    assert widget is not None
    assert widget.count() > 0
    qtbot.addWidget(widget)
