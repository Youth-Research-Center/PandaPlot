"""Tests for the theme-token icon helpers used by toolbars and buttons."""

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QSize
from PySide6.QtGui import QAction, QColor, QIcon
from PySide6.QtWidgets import QPushButton

from pandaplot.gui.resources.themed_icons import ActionIcons, IconRole, themed_icon
from pandaplot.models.state.app_context import AppContext
from tests.gui.icon_testing import ICON_TOKENS, assert_tinted, fresh_icon_tokens, strongest_pixel

LIGHT = {"text_primary": "#1C1E26", "text_muted": "#6B7280", "accent_icon_active": "#404BAC", "text_disabled": "#AEB2BC"}
DARK = {"text_primary": "#E2E2E2", "text_muted": "#9AA0AB", "accent_icon_active": "#8995FF", "text_disabled": "#5B6270"}


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.get_manager.return_value.get_design_tokens.return_value = LIGHT
    return ctx


def _strongest(icon, *, size: int = 32, mode=None) -> QColor:
    image = (icon.pixmap(QSize(size, size)) if mode is None else icon.pixmap(QSize(size, size), mode)).toImage()
    pixels = (image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height()))
    return max(pixels, key=lambda pixel: pixel.alpha())


def _assert_close(actual: QColor, expected: str) -> None:
    wanted = QColor(expected)
    assert abs(actual.red() - wanted.red()) < 12
    assert abs(actual.green() - wanted.green()) < 12
    assert abs(actual.blue() - wanted.blue()) < 12


def test_themed_icon_uses_the_text_token_by_default(qapp, app_context):
    _assert_close(_strongest(themed_icon(app_context, "folder", size=32)), LIGHT["text_primary"])


@pytest.mark.parametrize(("role", "token"), [(IconRole.MUTED, "text_muted"), (IconRole.ACTIVE, "accent_icon_active")])
def test_themed_icon_roles_map_to_their_tokens(qapp, app_context, role, token):
    _assert_close(_strongest(themed_icon(app_context, "folder", role=role, size=32)), LIGHT[token])


@pytest.mark.parametrize(
    ("role", "value"),
    [
        (IconRole.SUCCESS, "status_success"),
        (IconRole.ERROR, "status_danger"),
        (IconRole.WARNING, "status_modified_text"),
        (IconRole.INFO, "accent"),
    ],
)
def test_status_roles_map_to_their_tokens(qapp, role, value):
    ctx = Mock(spec=AppContext)
    ctx.get_manager.return_value.get_design_tokens.return_value = fresh_icon_tokens()

    assert role.value == value
    assert_tinted(strongest_pixel(themed_icon(ctx, "folder", role=role, size=32)), ICON_TOKENS[value])


def test_themed_icon_has_a_distinct_disabled_colour(qapp, app_context):
    icon = themed_icon(app_context, "folder", size=32)

    _assert_close(_strongest(icon, mode=QIcon.Mode.Disabled), LIGHT["text_disabled"])


def test_themed_icon_unknown_name_raises_a_helpful_error(qapp, app_context):
    with pytest.raises(KeyError, match="icon_manifest.toml"):
        themed_icon(app_context, "no-such-icon")


def test_action_icons_bind_sets_the_icon_on_actions_and_buttons(qapp, app_context):
    icons = ActionIcons(app_context, size=32)
    action = QAction("Open")
    button = QPushButton("Open")

    icons.bind(action, "folder-simple")
    icons.bind(button, "folder-simple")

    _assert_close(_strongest(action.icon()), LIGHT["text_primary"])
    _assert_close(_strongest(button.icon()), LIGHT["text_primary"])


def test_action_icons_retint_follows_the_new_theme_tokens(qapp, app_context):
    icons = ActionIcons(app_context, size=32)
    action = QAction("Open")
    button = QPushButton("Open")
    icons.bind(action, "folder-simple")
    icons.bind(button, "folder-simple")

    app_context.get_manager.return_value.get_design_tokens.return_value = DARK
    icons.retint()

    _assert_close(_strongest(action.icon()), DARK["text_primary"])
    _assert_close(_strongest(button.icon()), DARK["text_primary"])


def test_action_icons_retint_skips_deleted_targets(qapp, app_context):
    icons = ActionIcons(app_context)
    keep = QAction("Keep")
    doomed = QPushButton("Doomed")
    icons.bind(keep, "folder-simple")
    icons.bind(doomed, "folder-simple")
    doomed.deleteLater()

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    icons.retint()

    assert not keep.icon().isNull()


def test_on_accent_role_maps_to_the_on_accent_token(qapp, app_context):
    app_context.get_manager.return_value.get_design_tokens.return_value = {**LIGHT, "text_on_accent": "#FFFFFF"}

    _assert_close(_strongest(themed_icon(app_context, "folder", role=IconRole.ON_ACCENT, size=32)), "#FFFFFF")
