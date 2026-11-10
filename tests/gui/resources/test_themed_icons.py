"""Tests for the theme-token icon helpers used by toolbars and buttons."""

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QSize
from PySide6.QtGui import QAction, QColor, QIcon
from PySide6.QtWidgets import QApplication, QPushButton

from pandaplot.gui.components.common.p_button import PButton
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


def test_on_danger_role_maps_to_the_on_danger_token():
    assert IconRole.ON_DANGER.value == "text_on_danger"


def test_action_icons_bind_role_overrides_the_registry_role(qapp):
    ctx = Mock(spec=AppContext)
    ctx.get_manager.return_value.get_design_tokens.return_value = fresh_icon_tokens()
    icons = ActionIcons(ctx, size=32)
    plain = QPushButton("Plain")
    danger = QPushButton("Danger")

    icons.bind(plain, "trash")
    icons.bind(danger, "trash", role=IconRole.ERROR)

    assert_tinted(strongest_pixel(plain.icon()), ICON_TOKENS["text_primary"])
    assert_tinted(strongest_pixel(danger.icon()), ICON_TOKENS["status_danger"])


def test_action_icons_hover_role_swaps_the_icon_on_enter_and_leave(qapp):
    ctx = Mock(spec=AppContext)
    ctx.get_manager.return_value.get_design_tokens.return_value = fresh_icon_tokens()
    icons = ActionIcons(ctx, size=32)
    button = PButton("Delete", role="destructive")

    icons.bind(button, "trash", role=IconRole.ERROR, hover_role=IconRole.ON_DANGER)

    assert_tinted(strongest_pixel(button.icon()), ICON_TOKENS["status_danger"])
    QApplication.sendEvent(button, QEvent(QEvent.Type.Enter))
    assert_tinted(strongest_pixel(button.icon()), ICON_TOKENS["text_on_danger"])
    QApplication.sendEvent(button, QEvent(QEvent.Type.Leave))
    assert_tinted(strongest_pixel(button.icon()), ICON_TOKENS["status_danger"])


def test_action_icons_retint_renders_the_normal_and_hover_icons_from_the_new_tokens(qapp):
    tokens = fresh_icon_tokens()
    ctx = Mock(spec=AppContext)
    ctx.get_manager.return_value.get_design_tokens.side_effect = lambda: dict(tokens)
    icons = ActionIcons(ctx, size=32)
    button = PButton("Delete", role="destructive")
    icons.bind(button, "trash", role=IconRole.ERROR, hover_role=IconRole.ON_DANGER)

    tokens.update(status_danger="#C24141", text_on_danger="#102030")
    icons.retint()

    assert_tinted(strongest_pixel(button.icon()), "#C24141")
    QApplication.sendEvent(button, QEvent(QEvent.Type.Enter))
    assert_tinted(strongest_pixel(button.icon()), "#102030")


def test_action_icons_hover_role_is_ignored_for_targets_without_hover_support(qapp, app_context):
    icons = ActionIcons(app_context, size=32)
    action = QAction("Open")

    icons.bind(action, "folder-simple", hover_role=IconRole.ON_DANGER)

    assert not action.icon().isNull()
