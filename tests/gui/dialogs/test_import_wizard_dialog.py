"""Tests for ImportWizardDialog file loading."""
import sys

from PySide6.QtWidgets import QApplication

import pandaplot.gui.dialogs.import_wizard_dialog as import_wizard_module
from pandaplot.app import build_app_context
from pandaplot.gui.dialogs.import_wizard_dialog import ImportWizardDialog


def _qapp():
    return QApplication.instance() or QApplication(sys.argv)


def test_failed_inspection_of_a_new_file_disables_import(tmp_path, monkeypatch):
    """Import stayed enabled with the previous file's options after the
    next file failed inspection, so Import would read the new file with
    options detected for another one."""
    _qapp()
    good = tmp_path / "good.csv"
    good.write_text("a,b\n1,2\n3,4\n")
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b\n1,2\n")
    dialog = ImportWizardDialog(build_app_context())
    try:
        dialog._load_file(str(good))
        assert dialog.import_button.isEnabled()

        def _raise(_path):
            raise ValueError("cannot inspect")

        monkeypatch.setattr(import_wizard_module, "default_options", _raise)
        dialog._load_file(str(bad))

        assert not dialog.import_button.isEnabled()
        assert "Could not inspect file" in dialog.status_label.text()
        assert dialog.preview_table.rowCount() == 0
    finally:
        dialog.deleteLater()
