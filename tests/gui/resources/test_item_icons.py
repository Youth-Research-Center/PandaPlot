"""Item types map to bundled icons that `item_icon` renders in the theme's text colour."""

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon

from pandaplot.gui.resources.icon_library import build_icon, icon_svg
from pandaplot.gui.resources.item_icons import DEFAULT_ITEM_ICON_NAME, ITEM_TYPE_ICON_NAMES, item_icon, item_icon_name
from pandaplot.models.state.app_context import AppContext
from tests.gui.icon_testing import ICON_TOKENS, assert_tinted, fresh_icon_tokens, strongest_pixel

EXPECTED_NAMES = {
    "project": "folder",
    "folder": "folder-simple",
    "collection": "folder-simple",
    "note": "note-pencil",
    "dataset": "table",
    "chart": "chart-line",
    "imagegallery": "images",
    "image": "image",
    "sketch": "pencil-simple-line",
}


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.get_manager.return_value.get_design_tokens.return_value = fresh_icon_tokens()
    return ctx


def test_mapping_matches_the_icon_assignment_table():
    assert ITEM_TYPE_ICON_NAMES == EXPECTED_NAMES
    assert DEFAULT_ITEM_ICON_NAME == "file"


@pytest.mark.parametrize("name", [*EXPECTED_NAMES.values(), DEFAULT_ITEM_ICON_NAME])
def test_every_mapped_icon_is_bundled(name):
    assert icon_svg(name)


def test_unknown_item_types_fall_back_to_the_default_icon():
    assert item_icon_name("no-such-type") == "file"
    assert item_icon_name("dataset") == "table"


def test_item_icon_renders_the_mapped_icon_in_the_text_colour(qapp, app_context):
    expected = build_icon("table", ICON_TOKENS["text_primary"], size=16, disabled_color=ICON_TOKENS["text_disabled"])

    actual = item_icon(app_context, "dataset")

    assert actual.pixmap(QSize(16, 16)).toImage() == expected.pixmap(QSize(16, 16)).toImage()


def test_item_icon_honours_the_requested_size(qapp, app_context):
    assert item_icon(app_context, "chart", size=24).pixmap(QSize(24, 24)).width() >= 24


def test_item_icon_renders_the_selected_pixmap_in_the_requested_colour(qapp, app_context):
    icon = item_icon(app_context, "dataset", selected_color="#ffffff")

    assert_tinted(strongest_pixel(icon.pixmap(QSize(16, 16), QIcon.Mode.Selected)), "#ffffff")
    assert_tinted(strongest_pixel(icon.pixmap(QSize(16, 16), QIcon.Mode.Normal)), ICON_TOKENS["text_primary"])
