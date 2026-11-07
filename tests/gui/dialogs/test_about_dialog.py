"""About dialog shows the licence attribution required by bundled third-party icons."""

from unittest.mock import Mock

from pandaplot.gui.dialogs.about_dialog import AboutDialog
from pandaplot.models.state.app_context import AppContext


def test_about_dialog_credits_the_bundled_icon_libraries(qtbot):
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    ctx.get_manager.return_value.get_surface_palette.return_value = {}

    dialog = AboutDialog(ctx)
    qtbot.addWidget(dialog)

    assert "Icons: Phosphor Icons 2.1.1 (MIT)" in dialog.attribution_label.text()
