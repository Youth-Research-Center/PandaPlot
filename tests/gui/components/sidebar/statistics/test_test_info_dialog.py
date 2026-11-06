"""InfoDialogHelper's Close button simply rejects the dialog."""
from unittest.mock import Mock

from PySide6.QtWidgets import QDialog, QDialogButtonBox

from pandaplot.analysis import STAT_TESTS
from pandaplot.gui.components.sidebar.statistics.test_info_dialog import InfoDialogHelper


def test_close_button_rejects_once(qtbot):
    context = Mock()
    context.get_manager.return_value.get_surface_palette.return_value = {}
    dialog = InfoDialogHelper(context, next(iter(STAT_TESTS.values())))
    qtbot.addWidget(dialog)
    dialog.show()
    results = []
    dialog.finished.connect(results.append)

    box = dialog.findChild(QDialogButtonBox)
    box.button(QDialogButtonBox.StandardButton.Close).click()

    assert results == [QDialog.DialogCode.Rejected.value]
    assert dialog.result() == QDialog.DialogCode.Rejected.value
