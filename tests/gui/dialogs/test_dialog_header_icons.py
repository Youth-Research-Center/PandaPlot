"""Dialog headers, option cards and window icons use bundled icons and the panda app icon instead of emoji."""

import re
from unittest.mock import Mock

import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QLabel, QPushButton

from pandaplot.app import build_app_context
from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.dialogs.about_dialog import AboutDialog
from pandaplot.gui.dialogs.create_or_open_project_dialog import CreateOrOpenProjectDialog
from pandaplot.gui.dialogs.create_visualization_dialog import CreateVisualizationDialog
from pandaplot.gui.dialogs.explore_data_dialog import ExploreDataDialog
from pandaplot.gui.dialogs.import_wizard_dialog import ImportWizardDialog
from pandaplot.gui.resources.app_icon import create_app_icon
from pandaplot.gui.resources.themed_icons import themed_icon
from pandaplot.models.state.app_context import AppContext
from tests.gui.icon_testing import assert_tinted, strongest_pixel
from tests.gui.theme_testing import design_tokens, surface_palette

NON_ASCII = re.compile(r"[^\x00-\x7f]")


def _context() -> Mock:
    context = Mock(spec=AppContext)
    context.event_bus = Mock()
    context.get_app_state.return_value.has_project = False
    context.get_manager.return_value.get_surface_palette.return_value = surface_palette()
    context.get_manager.return_value.get_design_tokens.return_value = design_tokens()
    return context


def _texts(widget) -> list[str]:
    return [label.text() for label in widget.findChildren(QLabel) if not isinstance(label, IconLabel)]


def test_about_header_shows_the_panda_app_icon_not_an_emoji(qtbot):
    dialog = AboutDialog(_context())
    qtbot.addWidget(dialog)

    pixmap = dialog.icon_label.pixmap()
    expected = create_app_icon().pixmap(QSize(64, 64))

    assert not pixmap.isNull()
    assert pixmap.deviceIndependentSize().toSize() == QSize(64, 64)
    assert pixmap.toImage() == expected.toImage()
    assert dialog.icon_label.text() == ""


@pytest.mark.parametrize(
    ("dialog_cls", "kwargs", "icon_name"),
    [
        (CreateVisualizationDialog, {"on_create_chart": Mock()}, "chart-bar"),
        (ExploreDataDialog, {"on_import_data": Mock(), "on_create_dataset": Mock()}, "table"),
    ],
    ids=["create-visualization", "explore-data"],
)
def test_dialog_header_is_a_tinted_icon_label_without_emoji(qtbot, dialog_cls, kwargs, icon_name):
    dialog = dialog_cls(_context(), parent=None, **kwargs)
    qtbot.addWidget(dialog)

    assert isinstance(dialog.icon_label, IconLabel)
    assert dialog.icon_label.icon_name == icon_name
    assert_tinted(strongest_pixel(dialog.icon_label.pixmap().toImage()), design_tokens()["text_primary"])
    for text in _texts(dialog):
        assert NON_ASCII.search(text) is None, f"{text!r} contains emoji or non-ASCII text"


def test_project_dialog_options_have_plain_titles_icons_and_plain_accessible_names(qtbot):
    dialog = CreateOrOpenProjectDialog(_context())
    qtbot.addWidget(dialog)

    options = dialog.findChildren(QPushButton, "OptionItemButton")

    expected = [("New Project", "plus-circle"), ("Open Project", "folder-open"), ("Browse Examples", "books")]
    assert [button.accessibleName() for button in options] == [title for title, _icon in expected]
    for button, (title, icon_name) in zip(options, expected, strict=True):
        assert title in _texts(button)
        (icon,) = button.findChildren(IconLabel)
        assert icon.icon_name == icon_name
        assert NON_ASCII.search(button.accessibleName()) is None


def test_import_wizard_window_title_is_plain_and_has_a_download_icon(qapp):
    dialog = ImportWizardDialog(build_app_context())
    try:
        assert dialog.windowTitle() == "Import Dataset"
        assert not dialog.windowIcon().isNull()
        expected = themed_icon(dialog.app_context, "download-simple")
        assert dialog.windowIcon().pixmap(QSize(16, 16)).toImage() == expected.pixmap(QSize(16, 16)).toImage()
    finally:
        dialog.deleteLater()
