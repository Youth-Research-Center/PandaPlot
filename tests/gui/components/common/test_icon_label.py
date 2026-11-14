"""IconLabel renders a bundled icon in a theme colour and follows token changes."""

from unittest.mock import Mock

import pytest
from PySide6.QtGui import QColor

from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.resources.themed_icons import IconRole
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.config import Theme
from tests.gui.theme_testing import design_tokens


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.get_manager.return_value.get_design_tokens.return_value = design_tokens(Theme.LIGHT)
    return ctx


def _strongest(label: IconLabel) -> QColor:
    image = label.pixmap().toImage()
    pixels = (image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height()))
    return max(pixels, key=lambda pixel: pixel.alpha())


def _assert_close(actual: QColor, expected: str) -> None:
    wanted = QColor(expected)
    assert abs(actual.red() - wanted.red()) < 12
    assert abs(actual.green() - wanted.green()) < 12
    assert abs(actual.blue() - wanted.blue()) < 12


def test_icon_label_shows_the_icon_in_the_role_colour(qapp, app_context):
    label = IconLabel(app_context, "folder", size=32)

    assert label.icon_name == "folder"
    assert not label.pixmap().isNull()
    _assert_close(_strongest(label), design_tokens(Theme.LIGHT)["text_primary"])


def test_icon_label_uses_the_requested_role(qapp, app_context):
    label = IconLabel(app_context, "folder", size=32, role=IconRole.MUTED)

    _assert_close(_strongest(label), design_tokens(Theme.LIGHT)["text_muted"])


def test_icon_label_retint_follows_the_new_tokens(qapp, app_context):
    label = IconLabel(app_context, "folder", size=32)
    app_context.get_manager.return_value.get_design_tokens.return_value = design_tokens(Theme.DARK)

    label.retint()

    _assert_close(_strongest(label), design_tokens(Theme.DARK)["text_primary"])


def test_icon_label_is_fixed_size_and_unknown_icons_fail_loudly(qapp, app_context):
    label = IconLabel(app_context, "folder", size=20)

    assert label.width() == 20 and label.height() == 20
    with pytest.raises(KeyError, match="icon_manifest.toml"):
        IconLabel(app_context, "no-such-icon")
