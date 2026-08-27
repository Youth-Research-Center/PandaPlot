import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.common.dirty_footer import DirtyFooter, format_status_text


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_format_status_text_no_changes():
    assert format_status_text(is_modified=False, change_count=0) == "No changes"


def test_format_status_text_single_change():
    assert format_status_text(is_modified=True, change_count=1) == "Modified"


def test_format_status_text_multiple_changes():
    assert format_status_text(is_modified=True, change_count=3) == "3 unsaved changes"


def test_set_modified_false_disables_apply_and_revert():
    footer = DirtyFooter()
    footer.setModified(is_modified=False, change_count=0)
    assert not footer._apply_button.isEnabled()
    assert not footer._revert_button.isEnabled()


def test_set_modified_true_enables_apply_and_revert():
    footer = DirtyFooter()
    footer.setModified(is_modified=True, change_count=2)
    assert footer._apply_button.isEnabled()
    assert footer._revert_button.isEnabled()
    assert footer._status_label.text() == "2 unsaved changes"


def test_apply_button_click_emits_apply_clicked():
    footer = DirtyFooter()
    footer.setModified(is_modified=True, change_count=1)
    seen = []
    footer.applyClicked.connect(lambda: seen.append(True))
    footer._apply_button.click()
    assert seen == [True]


def test_revert_button_click_emits_revert_clicked():
    footer = DirtyFooter()
    footer.setModified(is_modified=True, change_count=1)
    seen = []
    footer.revertClicked.connect(lambda: seen.append(True))
    footer._revert_button.click()
    assert seen == [True]


def test_set_modified_true_with_zero_changes_disables_buttons():
    footer = DirtyFooter()
    footer.setModified(is_modified=True, change_count=0)
    assert not footer._apply_button.isEnabled()
    assert not footer._revert_button.isEnabled()
    assert footer._status_label.text() == "No changes"
