"""Tests for the theme-token icon helpers used by menus, toolbars and buttons."""

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QSize
from PySide6.QtGui import QAction, QColor, QIcon
from PySide6.QtWidgets import QPushButton

from pandaplot.gui.resources.themed_icons import ActionIcons, IconRole, themed_icon
from pandaplot.models.state.app_context import AppContext

LIGHT = {"text_primary": "#1C1E26", "text_muted": "#6B7280", "accent_icon_active": "#404BAC", "text_disabled": "#AEB2BC"}
DARK = {"text_primary": "#E2E2E2", "text_muted": "#9AA0AB", "accent_icon_active": "#8995FF", "text_disabled": "#5B6270"}
LIGHT_WITH_ON_ACCENT = {**LIGHT, "text_on_accent": "#FFFFFF"}
DARK_WITH_ON_ACCENT = {**DARK, "text_on_accent": "#101010"}


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

    icons.bind(action, "folder-open")
    icons.bind(button, "folder-open")

    _assert_close(_strongest(action.icon()), LIGHT["text_primary"])
    _assert_close(_strongest(button.icon()), LIGHT["text_primary"])


def test_action_icons_retint_follows_the_new_theme_tokens(qapp, app_context):
    icons = ActionIcons(app_context, size=32)
    action = QAction("Open")
    button = QPushButton("Open")
    icons.bind(action, "folder-open")
    icons.bind(button, "folder-open")

    app_context.get_manager.return_value.get_design_tokens.return_value = DARK
    icons.retint()

    _assert_close(_strongest(action.icon()), DARK["text_primary"])
    _assert_close(_strongest(button.icon()), DARK["text_primary"])


def test_action_icons_retint_skips_deleted_targets(qapp, app_context):
    icons = ActionIcons(app_context)
    keep = QAction("Keep")
    doomed = QPushButton("Doomed")
    icons.bind(keep, "folder-open")
    icons.bind(doomed, "folder-open")
    doomed.deleteLater()

    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    icons.retint()

    assert not keep.icon().isNull()


def test_themed_icon_on_accent_tints_the_active_mode_with_the_on_accent_token(qapp, app_context):
    app_context.get_manager.return_value.get_design_tokens.return_value = LIGHT_WITH_ON_ACCENT

    icon = themed_icon(app_context, "folder", size=32, on_accent=True)

    _assert_close(_strongest(icon, mode=QIcon.Mode.Active), "#FFFFFF")
    _assert_close(_strongest(icon, mode=QIcon.Mode.Normal), LIGHT["text_primary"])


def test_themed_icon_active_mode_equals_normal_by_default(qapp, app_context):
    app_context.get_manager.return_value.get_design_tokens.return_value = LIGHT_WITH_ON_ACCENT

    icon = themed_icon(app_context, "folder", size=32)

    _assert_close(_strongest(icon, mode=QIcon.Mode.Active), LIGHT["text_primary"])


def test_themed_icon_on_accent_without_the_token_adds_no_active_pixmap(qapp, app_context):
    icon = themed_icon(app_context, "folder", size=32, on_accent=True)

    _assert_close(_strongest(icon, mode=QIcon.Mode.Active), LIGHT["text_primary"])


def test_action_icons_on_accent_retint_rerenders_the_active_pixmap(qapp, app_context):
    app_context.get_manager.return_value.get_design_tokens.return_value = LIGHT_WITH_ON_ACCENT
    icons = ActionIcons(app_context, size=32, on_accent=True)
    action = QAction("Open")
    icons.bind(action, "folder-open")
    _assert_close(_strongest(action.icon(), mode=QIcon.Mode.Active), "#FFFFFF")

    app_context.get_manager.return_value.get_design_tokens.return_value = DARK_WITH_ON_ACCENT
    icons.retint()

    _assert_close(_strongest(action.icon(), mode=QIcon.Mode.Active), "#101010")
    _assert_close(_strongest(action.icon(), mode=QIcon.Mode.Normal), DARK["text_primary"])


def test_action_icons_active_mode_equals_normal_by_default(qapp, app_context):
    app_context.get_manager.return_value.get_design_tokens.return_value = LIGHT_WITH_ON_ACCENT
    icons = ActionIcons(app_context, size=32)
    action = QAction("Open")

    icons.bind(action, "folder-open")

    _assert_close(_strongest(action.icon(), mode=QIcon.Mode.Active), LIGHT["text_primary"])
