"""IconLabel renders a bundled icon in a theme colour and follows token changes."""

from unittest.mock import Mock

import pytest

from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.resources.themed_icons import IconRole
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.config import Theme
from tests.gui.icon_testing import assert_tinted, strongest_pixel
from tests.gui.theme_testing import design_tokens


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.get_manager.return_value.get_design_tokens.return_value = design_tokens(Theme.LIGHT)
    return ctx


def test_icon_label_shows_the_icon_in_the_role_colour(qapp, app_context):
    label = IconLabel(app_context, "folder", size=32)

    assert label.icon_name == "folder"
    assert not label.pixmap().isNull()
    assert_tinted(strongest_pixel(label.pixmap()), design_tokens(Theme.LIGHT)["text_primary"])


def test_icon_label_uses_the_requested_role(qapp, app_context):
    label = IconLabel(app_context, "folder", size=32, role=IconRole.MUTED)

    assert_tinted(strongest_pixel(label.pixmap()), design_tokens(Theme.LIGHT)["text_muted"])


def test_icon_label_retint_follows_the_new_tokens(qapp, app_context):
    label = IconLabel(app_context, "folder", size=32)
    app_context.get_manager.return_value.get_design_tokens.return_value = design_tokens(Theme.DARK)

    label.retint()

    assert_tinted(strongest_pixel(label.pixmap()), design_tokens(Theme.DARK)["text_primary"])


def test_icon_label_is_fixed_size_and_unknown_icons_fail_loudly(qapp, app_context):
    label = IconLabel(app_context, "folder", size=20)

    assert label.width() == 20 and label.height() == 20
    with pytest.raises(KeyError, match="icon_manifest.toml"):
        IconLabel(app_context, "no-such-icon")
