"""About dialog shows the licence attribution required by bundled third-party icons."""

from unittest.mock import Mock

from pandaplot.gui.dialogs.about_dialog import AboutDialog
from pandaplot.gui.resources import icon_library
from pandaplot.models.state.app_context import AppContext


def test_about_dialog_credits_the_bundled_icon_libraries(qtbot):
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    ctx.get_manager.return_value.get_surface_palette.return_value = {}

    dialog = AboutDialog(ctx)
    qtbot.addWidget(dialog)

    sources = icon_library._load_bundle()["sources"]
    expected = ", ".join(f"{meta['title']} {meta['version']} ({meta['license']})" for _, meta in sorted(sources.items()))
    text = dialog.attribution_label.text()
    assert f"Icons: {expected}" in text
    assert "Phosphor Icons" in text
